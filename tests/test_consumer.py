import base64
import json
from datetime import datetime, timezone

import pytest

from consumer.mongodb_consumer import (
    ConsumerSettings,
    DlqPublisher,
    MongoRepository,
    PermanentMessageError,
    TransientProcessingError,
    build_dlq_envelope,
    decode_event,
    handle_message,
    load_settings,
    process_with_retry,
)
from confluent_kafka import KafkaException
from pymongo.errors import AutoReconnect


class FakeMessage:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value

    def key(self):
        return b"4baa12"

    def headers(self):
        return [("trace-id", b"abc")]

    def topic(self):
        return "aircraft.positions.raw.v1"

    def partition(self):
        return 0

    def offset(self):
        return 42

    def timestamp(self):
        return (1, 1_700_000_000_000)


def valid_payload():
    return json.dumps(
        {
            "schema_version": 1,
            "event_id": "00000000-0000-4000-8000-000000000001",
            "icao24": "4baa12",
            "latitude": 41.1,
            "longitude": 28.7,
            "observed_at": "2024-01-01T00:00:00+00:00",
            "ingested_at": "2024-01-01T00:00:01+00:00",
        }
    ).encode()


def settings():
    return ConsumerSettings(
        kafka_bootstrap_servers="kafka:29092",
        kafka_topic="aircraft.positions.raw.v1",
        kafka_dlq_topic="aircraft.positions.dlq.v1",
        consumer_group="flight-mongodb-writer-v1",
        mongodb_uri="mongodb://mongodb:27017",
        database_name="flightdb",
        raw_retention_hours=48,
        live_retention_hours=168,
        max_attempts=3,
        retry_backoff_seconds=1,
    )


def test_decode_event_normalizes_dates():
    event = decode_event(FakeMessage(valid_payload()))
    assert event["icao24"] == "4baa12"
    assert isinstance(event["observed_at"], datetime)
    assert event["observed_at"].tzinfo is not None


@pytest.mark.parametrize(
    "payload",
    [b"not-json", json.dumps({"icao24": "bad"}).encode()],
)
def test_invalid_payload_is_permanent(payload):
    with pytest.raises(PermanentMessageError):
        decode_event(FakeMessage(payload))


def test_dlq_envelope_preserves_binary_payload():
    message = FakeMessage(b"\xffbad")
    envelope = build_dlq_envelope(
        message, settings(), PermanentMessageError("bad"), 1
    )
    assert envelope["dlq_id"].endswith(":0:42")
    assert base64.b64decode(envelope["payload"]["data"]) == b"\xffbad"
    assert envelope["source"]["headers"][0]["name"] == "trace-id"


def test_new_event_uses_event_id_and_attempt_count():
    class Repository:
        def write_event(self, _message, event):
            return {"event_id": event["event_id"]}

    result, attempts = process_with_retry(
        FakeMessage(valid_payload()), Repository(), settings(), FakeStopEvent()
    )
    assert result["event_id"] == "00000000-0000-4000-8000-000000000001"
    assert attempts == 1


class FakeStopEvent:
    def __init__(self):
        self.waits = []

    def wait(self, _seconds):
        self.waits.append(_seconds)
        return False


def test_settings_reject_zero_attempts():
    with pytest.raises(ValueError, match="CONSUMER_MAX_ATTEMPTS"):
        load_settings({"CONSUMER_MAX_ATTEMPTS": "0"})


def test_transient_mongo_error_uses_exponential_backoff():
    class Repository:
        attempts = 0

        def write_event(self, _message, event):
            self.attempts += 1
            if self.attempts < 3:
                raise AutoReconnect("temporary")
            return {"event_id": event["event_id"]}

    stop_event = FakeStopEvent()
    result, attempts = process_with_retry(
        FakeMessage(valid_payload()), Repository(), settings(), stop_event
    )
    assert result["event_id"].endswith("0001")
    assert attempts == 3
    assert stop_event.waits == [1, 2]


def test_dlq_delivery_failure_is_not_silently_accepted():
    class Producer:
        def produce(self, _topic, **kwargs):
            kwargs["on_delivery"]("broker unavailable", object())

        def flush(self, _timeout):
            return 0

    publisher = DlqPublisher(Producer(), "aircraft.positions.dlq.v1")
    with pytest.raises(KafkaException):
        publisher.publish({"dlq_id": "raw:0:1"})


def test_permanent_message_is_delivered_to_dlq_before_commit():
    calls = []

    class Repository:
        def write_event(self, _message, _event):
            raise AssertionError("Geçersiz JSON MongoDB'ye ulaşmamalı.")

    class Publisher:
        def publish(self, envelope):
            calls.append(("dlq", envelope["dlq_id"]))

    class Consumer:
        def commit(self, *, message, asynchronous):
            assert asynchronous is False
            calls.append(("commit", message.offset()))

    outcome = handle_message(
        FakeMessage(b"not-json"),
        Repository(),
        Publisher(),
        Consumer(),
        settings(),
        FakeStopEvent(),
    )

    assert outcome["status"] == "dlq"
    assert calls == [("dlq", "aircraft.positions.raw.v1:0:42"), ("commit", 42)]


def test_dlq_failure_does_not_commit_source_offset():
    class Publisher:
        def publish(self, _envelope):
            raise KafkaException("DLQ unavailable")

    class Consumer:
        def commit(self, **_kwargs):
            raise AssertionError("DLQ başarısızken offset commit edilmemeli.")

    with pytest.raises(KafkaException):
        handle_message(
            FakeMessage(b"not-json"),
            object(),
            Publisher(),
            Consumer(),
            settings(),
            FakeStopEvent(),
        )


def test_transient_mongo_failure_is_neither_dlqed_nor_committed():
    class Repository:
        def write_event(self, _message, _event):
            raise AutoReconnect("temporary")

    class Publisher:
        def publish(self, _envelope):
            raise AssertionError("MongoDB bağlantı hatası DLQ'ya gönderilmemeli.")

    class Consumer:
        def commit(self, **_kwargs):
            raise AssertionError("MongoDB bağlantı hatasında offset ilerlememeli.")

    with pytest.raises(TransientProcessingError):
        handle_message(
            FakeMessage(valid_payload()),
            Repository(),
            Publisher(),
            Consumer(),
            settings(),
            FakeStopEvent(),
        )


def test_existing_ttl_index_retention_is_updated_with_collmod():
    class Collection:
        name = "raw_positions"

        def __init__(self):
            self.expire_seconds = 60

        def list_indexes(self):
            return [{
                "name": "ttl",
                "key": {"ingested_at": 1},
                "expireAfterSeconds": self.expire_seconds,
            }]

    class Database:
        def __init__(self, collection):
            self.collection = collection

        def command(self, command):
            self.last_command = command
            self.collection.expire_seconds = command["index"][
                "expireAfterSeconds"
            ]

    collection = Collection()
    repository = object.__new__(MongoRepository)
    repository.database = Database(collection)
    repository.ensure_ttl_index(collection, "ttl", 48)
    assert repository.database.last_command["index"]["expireAfterSeconds"] == 172800


def test_ttl_index_with_wrong_key_stops_safe_migration():
    class Collection:
        name = "raw_positions"

        def list_indexes(self):
            return [{
                "name": "idx_raw_ingested_at_ttl",
                "key": {"observed_at": 1},
                "expireAfterSeconds": 172800,
            }]

    repository = object.__new__(MongoRepository)
    with pytest.raises(RuntimeError, match="beklenen ingested_at"):
        repository.ensure_ttl_index(
            Collection(), "idx_raw_ingested_at_ttl", 48
        )
