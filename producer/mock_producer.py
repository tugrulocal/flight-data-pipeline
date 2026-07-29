import json
import random
import time
from datetime import datetime, timezone

from confluent_kafka import Producer


KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC_NAME = "aircraft.positions.raw.v1"


producer = Producer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "client.id": "mock-flight-producer",
        "acks": "all",
        "enable.idempotence": True,
    }
)


aircraft = [
    {
        "icao24": "4baa12",
        "callsign": "THY123",
        "latitude": 41.10,
        "longitude": 28.75,
        "altitude_m": 8500,
        "velocity_mps": 220,
    },
    {
        "icao24": "4baa13",
        "callsign": "PGT456",
        "latitude": 40.98,
        "longitude": 29.12,
        "altitude_m": 7200,
        "velocity_mps": 205,
    },
    {
        "icao24": "4baa14",
        "callsign": "IGA789",
        "latitude": 41.25,
        "longitude": 28.74,
        "altitude_m": 9500,
        "velocity_mps": 235,
    },
]


def delivery_report(error, message):
    """Kafka mesajı teslim edildiğinde çağrılır."""

    if error is not None:
        print(f"Mesaj gönderilemedi: {error}")
        return

    key = message.key().decode("utf-8") if message.key() else None

    print(
        "Gönderildi | "
        f"key={key} | "
        f"partition={message.partition()} | "
        f"offset={message.offset()}"
    )


print(f"Producer başladı. Topic: {TOPIC_NAME}")
print("Durdurmak için Control + C kullan.\n")


sequence = 0

try:
    while True:
        for current_aircraft in aircraft:
            sequence += 1

            # Uçağın hareketini taklit etmek için koordinatları değiştiriyoruz.
            current_aircraft["latitude"] += random.uniform(-0.01, 0.01)
            current_aircraft["longitude"] += random.uniform(-0.01, 0.01)
            current_aircraft["altitude_m"] += random.randint(-50, 50)

            event = {
                **current_aircraft,
                "sequence": sequence,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "source": "mock",
            }

            key = event["icao24"].encode("utf-8")
            value = json.dumps(event).encode("utf-8")

            producer.produce(
                topic=TOPIC_NAME,
                key=key,
                value=value,
                on_delivery=delivery_report,
            )

            # Teslim callback'lerinin çalışmasını sağlar.
            producer.poll(0)

        time.sleep(2)

except KeyboardInterrupt:
    print("\nProducer durduruluyor...")

finally:
    # Gönderilmeyi bekleyen mesajların tamamlanmasını bekler.
    remaining_messages = producer.flush(10)

    if remaining_messages == 0:
        print("Bekleyen bütün mesajlar Kafka'ya gönderildi.")
    else:
        print(f"Gönderilemeyen mesaj sayısı: {remaining_messages}")
