import os
import json
from datetime import datetime

from confluent_kafka import Consumer, KafkaError, KafkaException
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

TOPIC_NAME = os.getenv(
    "KAFKA_TOPIC",
    "aircraft.positions.raw.v1",
)

CONSUMER_GROUP = os.getenv(
    "KAFKA_CONSUMER_GROUP",
    "flight-mongodb-writer-v1",
)

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017",
)

DATABASE_NAME = os.getenv(
    "MONGODB_DATABASE",
    "flightdb",
)


consumer = Consumer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
    }
)

mongo_client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
)

database = mongo_client[DATABASE_NAME]
raw_collection = database["raw_positions"]
live_collection = database["live_positions"]


def parse_iso_datetime(value):
    """ISO-8601 metnini MongoDB Date türüne uygun datetime'a çevirir."""

    if not isinstance(value, str):
        return value

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return value


def prepare_mongo_document(event):
    """Kafka JSON verisini MongoDB belgesine hazırlar."""

    document = dict(event)

    document["observed_at"] = parse_iso_datetime(
        document.get("observed_at")
    )

    document["ingested_at"] = parse_iso_datetime(
        document.get("ingested_at")
    )

    return document


def process_message(message):
    """Bir Kafka mesajını iki MongoDB collection'ına yazar."""

    event = json.loads(
        message.value().decode("utf-8")
    )

    icao24 = event.get("icao24")

    if not icao24:
        raise ValueError("Mesajda icao24 alanı bulunmuyor.")

    document = prepare_mongo_document(event)

    event_id = (
        f"{message.topic()}:"
        f"{message.partition()}:"
        f"{message.offset()}"
    )

    kafka_metadata = {
        "kafka_topic": message.topic(),
        "kafka_partition": message.partition(),
        "kafka_offset": message.offset(),
    }

    raw_document = {
        **document,
        **kafka_metadata,
    }

    live_document = {
        **document,
        **kafka_metadata,
    }

    # Aynı Kafka mesajı tekrar gelirse duplicate raw belge oluşmaz.
    raw_result = raw_collection.update_one(
        {"_id": event_id},
        {
            "$setOnInsert": raw_document
        },
        upsert=True,
    )

    # Her uçak için yalnızca en güncel belge tutulur.
    live_collection.update_one(
        {"_id": icao24},
        {
            "$set": live_document
        },
        upsert=True,
    )

    raw_inserted = raw_result.upserted_id is not None

    return {
        "icao24": icao24,
        "event_id": event_id,
        "raw_inserted": raw_inserted,
    }


def prepare_indexes():
    """Uçuş geçmişi sorguları için gerekli index'i oluşturur."""

    raw_collection.create_index(
        [
            ("icao24", ASCENDING),
            ("observed_at", DESCENDING),
        ],
        name="idx_raw_aircraft_time",
    )


print("MongoDB bağlantısı kontrol ediliyor...")

try:
    mongo_client.admin.command("ping")
    print("MongoDB bağlantısı başarılı.")

    prepare_indexes()
    print("MongoDB indexleri hazır.")

    consumer.subscribe([TOPIC_NAME])

    print(f"Kafka topic dinleniyor: {TOPIC_NAME}")
    print(f"Consumer group: {CONSUMER_GROUP}")
    print("Otomatik commit: kapalı")
    print("Durdurmak için Control + C kullan.\n")

    processed_count = 0

    while True:
        message = consumer.poll(timeout=1.0)

        if message is None:
            continue

        if message.error():
            if message.error().code() == KafkaError._PARTITION_EOF:
                continue

            raise KafkaException(message.error())

        try:
            result = process_message(message)

            # MongoDB işlemleri başarılı olduktan sonra manuel commit.
            consumer.commit(
                message=message,
                asynchronous=False,
            )

            processed_count += 1

            # Terminali binlerce satırla doldurmamak için
            # ilk 10 kaydı ve her 100. kaydı gösteriyoruz.
            if processed_count <= 10 or processed_count % 100 == 0:
                print(
                    f"İşlendi #{processed_count} | "
                    f"icao24={result['icao24']} | "
                    f"offset={message.offset()} | "
                    f"raw_inserted={result['raw_inserted']} | "
                    "commit=başarılı"
                )

        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValueError,
            PyMongoError,
            KafkaException,
        ) as error:
            print(
                "\nMesaj işlenemedi. "
                f"Partition={message.partition()}, "
                f"offset={message.offset()}"
            )
            print(f"Hata: {error}")
            print("Offset commit edilmedi. Consumer durduruluyor.")
            break

except KeyboardInterrupt:
    print("\nConsumer kullanıcı tarafından durduruldu.")

except (PyMongoError, KafkaException) as error:
    print(f"\nBaşlangıç veya bağlantı hatası: {error}")

finally:
    print("Consumer ve MongoDB bağlantıları kapatılıyor...")

    consumer.close()
    mongo_client.close()

    print("Consumer kapatıldı.")
