import json
import os
import random
import signal
import threading
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer


KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
)
TOPIC_NAME = os.getenv("KAFKA_TOPIC", "aircraft.positions.raw.v1")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "2"))
MAX_POLLS = int(os.getenv("MAX_POLLS", "0"))

AIRCRAFT = [
    {
        "icao24": "4baa12",
        "callsign": "THY123",
        "origin_country": "Turkey",
        "latitude": 41.10,
        "longitude": 28.75,
        "baro_altitude_m": 8500.0,
        "velocity_mps": 220.0,
        "true_track_deg": 90.0,
    },
    {
        "icao24": "4baa13",
        "callsign": "PGT456",
        "origin_country": "Turkey",
        "latitude": 40.98,
        "longitude": 29.12,
        "baro_altitude_m": 7200.0,
        "velocity_mps": 205.0,
        "true_track_deg": 135.0,
    },
    {
        "icao24": "4baa14",
        "callsign": "IGA789",
        "origin_country": "Turkey",
        "latitude": 41.25,
        "longitude": 28.74,
        "baro_altitude_m": 9500.0,
        "velocity_mps": 235.0,
        "true_track_deg": 250.0,
    },
]


def create_event(item):
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        **item,
        "geo_altitude_m": item["baro_altitude_m"],
        "on_ground": False,
        "vertical_rate_mps": 0.0,
        "observed_at": now.isoformat(),
        "ingested_at": now.isoformat(),
        "source": "mock",
    }


def main():
    if POLL_INTERVAL_SECONDS < 1 or MAX_POLLS < 0:
        raise ValueError("POLL_INTERVAL_SECONDS >= 1 ve MAX_POLLS >= 0 olmalı.")

    producer = Producer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "mock-flight-producer",
            "acks": "all",
            "enable.idempotence": True,
        }
    )
    stop_event = threading.Event()

    def request_stop(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    poll_number = 0

    exit_code = 0
    try:
        while not stop_event.is_set() and (
            MAX_POLLS == 0 or poll_number < MAX_POLLS
        ):
            poll_number += 1
            for item in AIRCRAFT:
                item["latitude"] += random.uniform(-0.01, 0.01)
                item["longitude"] += random.uniform(-0.01, 0.01)
                item["baro_altitude_m"] += random.randint(-50, 50)
                item["true_track_deg"] = (
                    item["true_track_deg"] + random.uniform(-4, 4)
                ) % 360
                event = create_event(item)
                producer.produce(
                    TOPIC_NAME,
                    key=event["icao24"].encode("utf-8"),
                    value=json.dumps(event).encode("utf-8"),
                )
                producer.poll(0)
            if producer.flush(10):
                exit_code = 1
                break
            if MAX_POLLS == 0 or poll_number < MAX_POLLS:
                stop_event.wait(POLL_INTERVAL_SECONDS)
    finally:
        if producer.flush(10):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
