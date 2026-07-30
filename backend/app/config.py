import os
from dataclasses import dataclass


def parse_cors_origins(value):
    """Virgülle ayrılmış frontend adreslerini temiz bir listeye dönüştürür."""

    return [
        origin.strip()
        for origin in value.split(",")
        if origin.strip()
    ]


@dataclass(frozen=True)
class Settings:
    mongodb_uri: str
    mongodb_database: str
    kafka_bootstrap_servers: str
    kafka_topic: str
    kafka_realtime_consumer_group: str
    cors_origins: list[str]


def load_settings():
    """Backend ayarlarını ortam değişkenlerinden yükler."""

    return Settings(
        mongodb_uri=os.getenv(
            "MONGODB_URI",
            "mongodb://localhost:27017",
        ),
        mongodb_database=os.getenv(
            "MONGODB_DATABASE",
            "flightdb",
        ),
        kafka_bootstrap_servers=os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092",
        ),
        kafka_topic=os.getenv(
            "KAFKA_TOPIC",
            "aircraft.positions.raw.v1",
        ),
        kafka_realtime_consumer_group=os.getenv(
            "KAFKA_REALTIME_CONSUMER_GROUP",
            "flight-realtime-gateway-v1",
        ),
        cors_origins=parse_cors_origins(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            )
        ),
    )
