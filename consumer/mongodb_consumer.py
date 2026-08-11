import base64
import json
import logging
import math
import os
import re
import signal
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from bson.errors import InvalidDocument
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    DocumentTooLarge,
    ExecutionTimeout,
    NetworkTimeout,
    NotPrimaryError,
    PyMongoError,
    ServerSelectionTimeoutError,
    WTimeoutError,
)

from flight_common.logging import configure_json_logging


logger = logging.getLogger(__name__)
ICAO24_PATTERN = re.compile(r"^[0-9a-f]{6}$")

TRANSIENT_MONGO_ERRORS = (
    AutoReconnect,
    ConnectionFailure,
    ExecutionTimeout,
    NetworkTimeout,
    NotPrimaryError,
    ServerSelectionTimeoutError,
    WTimeoutError,
)
PERMANENT_MONGO_ERRORS = (InvalidDocument, DocumentTooLarge)


def parse_int(name, value, *, minimum):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} tam sayı olmalı.") from error

    if parsed < minimum:
        raise ValueError(f"{name} en az {minimum} olmalı.")
    return parsed


@dataclass(frozen=True)
class ConsumerSettings:
    kafka_bootstrap_servers: str
    kafka_topic: str
    kafka_dlq_topic: str
    consumer_group: str
    mongodb_uri: str
    database_name: str
    raw_retention_hours: int
    live_retention_hours: int
    max_attempts: int
    retry_backoff_seconds: int


def load_settings(environ=None):
    values = os.environ if environ is None else environ
    return ConsumerSettings(
        kafka_bootstrap_servers=values.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        ),
        kafka_topic=values.get(
            "KAFKA_TOPIC", "aircraft.positions.raw.v1"
        ),
        kafka_dlq_topic=values.get(
            "KAFKA_DLQ_TOPIC", "aircraft.positions.dlq.v1"
        ),
        consumer_group=values.get(
            "KAFKA_CONSUMER_GROUP", "flight-mongodb-writer-v1"
        ),
        mongodb_uri=values.get("MONGODB_URI", "mongodb://localhost:27017"),
        database_name=values.get("MONGODB_DATABASE", "flightdb"),
        raw_retention_hours=parse_int(
            "RAW_POSITIONS_RETENTION_HOURS",
            values.get("RAW_POSITIONS_RETENTION_HOURS", "48"),
            minimum=1,
        ),
        live_retention_hours=parse_int(
            "LIVE_POSITIONS_RETENTION_HOURS",
            values.get("LIVE_POSITIONS_RETENTION_HOURS", "168"),
            minimum=1,
        ),
        max_attempts=parse_int(
            "CONSUMER_MAX_ATTEMPTS",
            values.get("CONSUMER_MAX_ATTEMPTS", "3"),
            minimum=1,
        ),
        retry_backoff_seconds=parse_int(
            "CONSUMER_RETRY_BACKOFF_SECONDS",
            values.get("CONSUMER_RETRY_BACKOFF_SECONDS", "1"),
            minimum=1,
        ),
    )


def create_consumer(settings):
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.consumer_group,
            "client.id": "flight-mongodb-writer",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )


def create_dlq_producer(settings):
    return Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "flight-mongodb-writer-dlq",
            "acks": "all",
            "enable.idempotence": True,
        }
    )


def create_mongo_client(settings):
    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )


def parse_iso_datetime(value, field_name):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{field_name} geçerli ISO-8601 olmalı.") from error
    else:
        raise ValueError(f"{field_name} alanı bulunmuyor veya tarih değil.")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_number(event, field_name, *, minimum=None, maximum=None):
    value = event.get(field_name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} sayısal olmalı.")
    if not math.isfinite(value):
        raise ValueError(f"{field_name} sonlu sayı olmalı.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field_name} en az {minimum} olmalı.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field_name} en fazla {maximum} olmalı.")


def decode_event(message):
    try:
        event = json.loads(message.value().decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PermanentMessageError("Kafka payload geçerli UTF-8 JSON değil.") from error

    if not isinstance(event, dict):
        raise PermanentMessageError("Kafka payload JSON nesnesi olmalı.")

    icao24 = str(event.get("icao24", "")).lower()
    if not ICAO24_PATTERN.fullmatch(icao24):
        raise PermanentMessageError("icao24 altı karakter hexadecimal olmalı.")

    try:
        validate_number(event, "latitude", minimum=-90, maximum=90)
        validate_number(event, "longitude", minimum=-180, maximum=180)
        observed_at = parse_iso_datetime(event.get("observed_at"), "observed_at")
        ingested_value = event.get("ingested_at")
        ingested_at = (
            parse_iso_datetime(ingested_value, "ingested_at")
            if ingested_value is not None
            else datetime.now(timezone.utc)
        )
    except ValueError as error:
        raise PermanentMessageError(str(error)) from error

    event["icao24"] = icao24
    event["observed_at"] = observed_at
    event["ingested_at"] = ingested_at

    if "schema_version" in event and event["schema_version"] != 1:
        raise PermanentMessageError("schema_version desteklenen 1 değeri olmalı.")

    if "event_id" in event:
        try:
            event["event_id"] = str(uuid.UUID(event["event_id"]))
        except (AttributeError, TypeError, ValueError) as error:
            raise PermanentMessageError("event_id geçerli UUID olmalı.") from error

    if "on_ground" in event and event["on_ground"] not in (True, False, None):
        raise PermanentMessageError("on_ground true, false veya null olmalı.")

    return event


class PermanentMessageError(Exception):
    """Aynı payload tekrar okunduğunda düzelmeyecek hata."""


class TransientProcessingError(Exception):
    """Altyapı iyileştiğinde aynı mesajın yeniden denenmesi gereken hata."""


class MongoRepository:
    def __init__(self, client, database_name):
        self.client = client
        self.database = client[database_name]
        self.raw_collection = self.database["raw_positions"]
        self.live_collection = self.database["live_positions"]

    def ping(self):
        self.client.admin.command("ping")

    def ensure_ttl_index(self, collection, name, retention_hours):
        expire_seconds = retention_hours * 60 * 60
        existing = next(
            (index for index in collection.list_indexes() if index["name"] == name),
            None,
        )

        if existing is not None and list(existing["key"].items()) != [
            ("ingested_at", ASCENDING)
        ]:
            raise RuntimeError(
                f"{collection.name}.{name} beklenen ingested_at TTL index'i değil."
            )

        if existing is None:
            collection.create_index(
                [("ingested_at", ASCENDING)],
                name=name,
                expireAfterSeconds=expire_seconds,
            )
        elif existing.get("expireAfterSeconds") != expire_seconds:
            self.database.command(
                {
                    "collMod": collection.name,
                    "index": {
                        "name": name,
                        "expireAfterSeconds": expire_seconds,
                    },
                }
            )

        verified = next(
            (index for index in collection.list_indexes() if index["name"] == name),
            None,
        )
        if (
            verified is None
            or list(verified["key"].items()) != [("ingested_at", ASCENDING)]
            or verified.get("expireAfterSeconds") != expire_seconds
        ):
            raise RuntimeError(
                f"{collection.name}.{name} TTL index doğrulaması başarısız."
            )

        return True

    def prepare_indexes(self, raw_retention_hours, live_retention_hours):
        now = datetime.now(timezone.utc)

        for collection in (self.raw_collection, self.live_collection):
            collection.update_many(
                {
                    "ingested_at": {"$exists": False},
                    "observed_at": {"$type": "date"},
                },
                [{"$set": {"ingested_at": "$observed_at"}}],
            )
            collection.update_many(
                {"ingested_at": {"$exists": False}},
                {"$set": {"ingested_at": now}},
            )

        raw_ttl_ready = self.ensure_ttl_index(
            self.raw_collection,
            "idx_raw_ingested_at_ttl",
            raw_retention_hours,
        )
        live_ttl_ready = self.ensure_ttl_index(
            self.live_collection,
            "idx_live_ingested_at_ttl",
            live_retention_hours,
        )

        raw_index_names = {
            index["name"] for index in self.raw_collection.list_indexes()
        }
        live_index_names = {
            index["name"] for index in self.live_collection.list_indexes()
        }
        raw_missing = self.raw_collection.count_documents(
            {"ingested_at": {"$exists": False}}, limit=1
        )
        live_missing = self.live_collection.count_documents(
            {"ingested_at": {"$exists": False}}, limit=1
        )
        if raw_missing == 0 and live_missing == 0:
            if raw_ttl_ready and "idx_raw_observed_at_ttl" in raw_index_names:
                self.raw_collection.drop_index("idx_raw_observed_at_ttl")
            if live_ttl_ready and "idx_live_observed_at_ttl" in live_index_names:
                self.live_collection.drop_index("idx_live_observed_at_ttl")

        self.raw_collection.create_index(
            [("icao24", ASCENDING), ("observed_at", DESCENDING)],
            name="idx_raw_aircraft_time",
        )
        self.live_collection.create_index(
            [("observed_at", DESCENDING)],
            name="idx_live_observed_at",
        )

    def write_event(self, message, event):
        event_id = event.get("event_id") or (
            f"{message.topic()}:{message.partition()}:{message.offset()}"
        )
        metadata = {
            "kafka_topic": message.topic(),
            "kafka_partition": message.partition(),
            "kafka_offset": message.offset(),
        }
        document = {**event, **metadata}

        raw_result = self.raw_collection.update_one(
            {"_id": event_id},
            {"$setOnInsert": document},
            upsert=True,
        )

        incoming_live = dict(document)
        self.live_collection.update_one(
            {"_id": event["icao24"]},
            [
                {
                    "$replaceWith": {
                        "$cond": [
                            {
                                "$or": [
                                    {
                                        "$eq": [
                                            {"$type": "$observed_at"},
                                            "missing",
                                        ]
                                    },
                                    {
                                        "$lt": [
                                            "$observed_at",
                                            event["observed_at"],
                                        ]
                                    },
                                ]
                            },
                            {"$mergeObjects": ["$$ROOT", incoming_live]},
                            "$$ROOT",
                        ]
                    }
                }
            ],
            upsert=True,
        )

        return {
            "icao24": event["icao24"],
            "event_id": event_id,
            "raw_inserted": raw_result.upserted_id is not None,
        }


def encode_base64(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.encode("utf-8")
    return base64.b64encode(value).decode("ascii")


def build_dlq_envelope(message, settings, error, attempts):
    timestamp_type, timestamp_ms = message.timestamp()
    headers = []
    for name, value in message.headers() or []:
        headers.append({"name": name, "value_base64": encode_base64(value)})

    return {
        "schema_version": 1,
        "dlq_id": f"{message.topic()}:{message.partition()}:{message.offset()}",
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "consumer_group": settings.consumer_group,
        "attempts": attempts,
        "error": {
            "classification": "permanent",
            "type": type(error).__name__,
            "message": str(error)[:2048],
        },
        "source": {
            "topic": message.topic(),
            "partition": message.partition(),
            "offset": message.offset(),
            "timestamp_type": timestamp_type,
            "timestamp_ms": timestamp_ms,
            "key_base64": encode_base64(message.key()),
            "headers": headers,
        },
        "payload": {
            "encoding": "base64",
            "data": encode_base64(message.value()),
        },
    }


class DlqPublisher:
    def __init__(self, producer, topic):
        self.producer = producer
        self.topic = topic

    def publish(self, envelope):
        delivery = {"error": None, "completed": False}

        def callback(error, _message):
            delivery["completed"] = True
            delivery["error"] = error

        try:
            self.producer.produce(
                self.topic,
                key=envelope["dlq_id"].encode("utf-8"),
                value=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
                on_delivery=callback,
            )
        except BufferError as error:
            raise KafkaException(error) from error
        remaining = self.producer.flush(30)

        if remaining or not delivery["completed"] or delivery["error"]:
            raise KafkaException(
                delivery["error"]
                or RuntimeError(f"DLQ tesliminde {remaining} mesaj bekliyor.")
            )


def process_with_retry(message, repository, settings, stop_event):
    try:
        event = decode_event(message)
    except PermanentMessageError:
        raise

    for attempt in range(1, settings.max_attempts + 1):
        try:
            return repository.write_event(message, event), attempt
        except PERMANENT_MONGO_ERRORS as error:
            raise PermanentMessageError(str(error)) from error
        except TRANSIENT_MONGO_ERRORS as error:
            if attempt == settings.max_attempts:
                raise TransientProcessingError(str(error)) from error
            delay = settings.retry_backoff_seconds * (2 ** (attempt - 1))
            logger.warning(
                "MongoDB yazımı yeniden denenecek.",
                extra={
                    "event": "mongodb_retry",
                    "attempt": attempt,
                    "retry_seconds": delay,
                    "partition": message.partition(),
                    "offset": message.offset(),
                    "error": str(error),
                },
            )
            if stop_event.wait(delay):
                raise TransientProcessingError("Kapanış sırasında retry kesildi.")
        except PyMongoError:
            raise

    raise AssertionError("Retry döngüsü beklenmedik biçimde tamamlandı.")


def handle_message(
    message,
    repository,
    dlq_publisher,
    kafka_consumer,
    settings,
    stop_event,
):
    """Bir mesajı işler; güvenli teslim tamamlanınca offset'i commit eder."""

    try:
        result, attempts = process_with_retry(
            message, repository, settings, stop_event
        )
    except PermanentMessageError as error:
        envelope = build_dlq_envelope(message, settings, error, 1)
        # Bu çağrı başarısız olursa commit satırına ulaşılmaz ve mesaj tekrar okunur.
        dlq_publisher.publish(envelope)
        kafka_consumer.commit(message=message, asynchronous=False)
        return {
            "status": "dlq",
            "error": error,
            "envelope": envelope,
        }

    kafka_consumer.commit(message=message, asynchronous=False)
    return {
        "status": "processed",
        "result": result,
        "attempts": attempts,
    }


def install_signal_handlers(stop_event):
    def request_stop(signum, _frame):
        logger.info("Kapanış sinyali alındı.", extra={"event": "shutdown_requested", "signal": signum})
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)


def run(
    settings,
    *,
    consumer=None,
    dlq_producer=None,
    mongo_client=None,
    stop_event=None,
):
    kafka_consumer = consumer or create_consumer(settings)
    kafka_dlq_producer = dlq_producer or create_dlq_producer(settings)
    client = mongo_client or create_mongo_client(settings)
    repository = MongoRepository(client, settings.database_name)
    dlq_publisher = DlqPublisher(kafka_dlq_producer, settings.kafka_dlq_topic)
    stopping = stop_event or threading.Event()
    processed_count = 0

    if stop_event is None:
        install_signal_handlers(stopping)

    try:
        repository.ping()
        repository.prepare_indexes(
            settings.raw_retention_hours,
            settings.live_retention_hours,
        )
        kafka_consumer.subscribe([settings.kafka_topic])
        logger.info(
            "MongoDB writer consumer başladı.",
            extra={
                "event": "service_started",
                "topic": settings.kafka_topic,
                "dlq_topic": settings.kafka_dlq_topic,
                "consumer_group": settings.consumer_group,
                "max_attempts": settings.max_attempts,
            },
        )

        while not stopping.is_set():
            message = kafka_consumer.poll(timeout=1.0)
            if message is None:
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(message.error())

            try:
                outcome = handle_message(
                    message,
                    repository,
                    dlq_publisher,
                    kafka_consumer,
                    settings,
                    stopping,
                )
            except TransientProcessingError as error:
                logger.error(
                    "Geçici altyapı hatası retry sınırını aştı; offset ilerletilmiyor.",
                    extra={
                        "event": "transient_failure_exhausted",
                        "partition": message.partition(),
                        "offset": message.offset(),
                        "error": str(error),
                    },
                )
                return 1
            except (PyMongoError, KafkaException) as error:
                logger.exception(
                    "Bilinmeyen işlem hatası; offset ilerletilmiyor.",
                    extra={
                        "event": "unknown_processing_failure",
                        "partition": message.partition(),
                        "offset": message.offset(),
                        "error": str(error),
                    },
                )
                return 1

            if outcome["status"] == "dlq":
                envelope = outcome["envelope"]
                error = outcome["error"]
                logger.error(
                    "Kalıcı hatalı mesaj DLQ'ya taşındı.",
                    extra={
                        "event": "message_sent_to_dlq",
                        "partition": message.partition(),
                        "offset": message.offset(),
                        "dlq_id": envelope["dlq_id"],
                        "error": str(error),
                    },
                )
                continue

            result = outcome["result"]
            attempts = outcome["attempts"]
            processed_count += 1
            if processed_count <= 10 or processed_count % 100 == 0:
                logger.info(
                    "Kafka mesajı MongoDB'ye yazıldı ve commit edildi.",
                    extra={
                        "event": "message_committed",
                        "processed_count": processed_count,
                        "icao24": result["icao24"],
                        "event_id": result["event_id"],
                        "partition": message.partition(),
                        "offset": message.offset(),
                        "raw_inserted": result["raw_inserted"],
                        "attempts": attempts,
                    },
                )
        return 0
    finally:
        kafka_consumer.close()
        kafka_dlq_producer.flush(10)
        client.close()
        logger.info("MongoDB writer consumer kapatıldı.", extra={"event": "service_stopped"})


def main():
    configure_json_logging("consumer")
    try:
        settings = load_settings()
        return run(settings)
    except ValueError as error:
        logger.error("Consumer ayarı geçersiz.", extra={"event": "configuration_error", "error": str(error)})
        return 2
    except (PyMongoError, KafkaException, RuntimeError) as error:
        logger.exception("Consumer başlangıç hatası.", extra={"event": "startup_error", "error": str(error)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
