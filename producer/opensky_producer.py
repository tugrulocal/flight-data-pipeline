import json
import os
import time
from datetime import datetime, timezone

import requests
from confluent_kafka import Producer


KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

TOPIC_NAME = os.getenv(
    "KAFKA_TOPIC",
    "aircraft.positions.raw.v1",
)

POLL_INTERVAL_SECONDS = int(
    os.getenv("POLL_INTERVAL_SECONDS", "300")
)

# 0 değeri producer'ın sürekli çalışması anlamına gelir.
MAX_POLLS = int(
    os.getenv("MAX_POLLS", "0")
)

OPENSKY_URL = "https://opensky-network.org/api/states/all"

# İstanbul ve çevresi
BOUNDING_BOX = {
    "lamin": 40.50,
    "lomin": 27.50,
    "lamax": 42.00,
    "lomax": 30.00,
    "extended": 1,
}


producer = Producer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "client.id": "opensky-flight-producer",
        "acks": "all",
        "enable.idempotence": True,
    }
)

http_session = requests.Session()


def unix_to_iso(timestamp):
    """Unix timestamp değerini UTC ISO-8601 metnine çevirir."""

    if timestamp is None:
        return None

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    ).isoformat()


def delivery_report(error, message):
    """Kafka mesajının teslim hatalarını gösterir."""

    if error is not None:
        print(f"Kafka gönderim hatası: {error}")


def fetch_opensky_states():
    """OpenSky'dan İstanbul çevresindeki uçakları getirir."""

    response = http_session.get(
        OPENSKY_URL,
        params=BOUNDING_BOX,
        timeout=20,
    )

    print(f"OpenSky HTTP durumu: {response.status_code}")

    remaining = response.headers.get("X-Rate-Limit-Remaining")

    if remaining is not None:
        print(f"Kalan OpenSky kredisi: {remaining}")

    response.raise_for_status()

    payload = response.json()

    return payload.get("time"), payload.get("states") or []


def normalize_state(state, api_time):
    """OpenSky dizisini okunabilir bir sözlüğe dönüştürür."""

    if len(state) < 17:
        return None

    icao24 = state[0]
    longitude = state[5]
    latitude = state[6]

    if not icao24 or longitude is None or latitude is None:
        return None

    callsign = state[1]

    if isinstance(callsign, str):
        callsign = callsign.strip() or None

    return {
        "icao24": icao24,
        "callsign": callsign,
        "origin_country": state[2],
        "time_position": state[3],
        "observed_at": unix_to_iso(state[3]),
        "last_contact": state[4],
        "longitude": longitude,
        "latitude": latitude,
        "baro_altitude_m": state[7],
        "on_ground": state[8],
        "velocity_mps": state[9],
        "true_track_deg": state[10],
        "vertical_rate_mps": state[11],
        "geo_altitude_m": state[13],
        "squawk": state[14],
        "spi": state[15],
        "position_source": state[16],
        "category": state[17] if len(state) > 17 else None,
        "api_time": api_time,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "source": "opensky",
    }


def send_states_to_kafka(states, api_time):
    """Her uçağı Kafka'ya ayrı mesaj olarak gönderir."""

    sent_count = 0
    skipped_count = 0

    for state in states:
        event = normalize_state(state, api_time)

        if event is None:
            skipped_count += 1
            continue

        producer.produce(
            topic=TOPIC_NAME,
            key=event["icao24"].encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
            on_delivery=delivery_report,
        )

        producer.poll(0)
        sent_count += 1

    remaining_messages = producer.flush(30)

    if remaining_messages:
        raise RuntimeError(
            f"{remaining_messages} Kafka mesajı teslim edilemedi."
        )

    print(
        f"API kaydı: {len(states)} | "
        f"Kafka'ya gönderilen: {sent_count} | "
        f"Atlanan: {skipped_count}"
    )


def get_retry_seconds(response):
    """Rate-limit sonrasında beklenecek süreyi belirler."""

    value = response.headers.get(
        "X-Rate-Limit-Retry-After-Seconds"
    )

    try:
        return max(int(value), 60)
    except (TypeError, ValueError):
        return 3600


def main():
    poll_number = 0

    print("OpenSky producer başladı.")
    print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic: {TOPIC_NAME}")
    print(f"Bounding box: {BOUNDING_BOX}")
    print(f"Çağrı aralığı: {POLL_INTERVAL_SECONDS} saniye")
    print(
        "Toplam çağrı: "
        + ("sınırsız" if MAX_POLLS == 0 else str(MAX_POLLS))
    )
    print("Durdurmak için Control + C kullan.\n")

    try:
        while MAX_POLLS == 0 or poll_number < MAX_POLLS:
            poll_number += 1

            print(f"\n----- API çağrısı {poll_number} -----")

            try:
                api_time, states = fetch_opensky_states()
                send_states_to_kafka(states, api_time)

            except requests.HTTPError as error:
                if error.response.status_code == 429:
                    retry_seconds = get_retry_seconds(
                        error.response
                    )

                    print(
                        "OpenSky kredi limiti aşıldı. "
                        f"{retry_seconds} saniye beklenecek."
                    )

                    time.sleep(retry_seconds)
                    continue

                print(f"OpenSky HTTP hatası: {error}")

            except requests.RequestException as error:
                print(f"OpenSky bağlantı hatası: {error}")

            except (ValueError, RuntimeError) as error:
                print(f"Producer işlem hatası: {error}")

            if MAX_POLLS == 0 or poll_number < MAX_POLLS:
                print(
                    f"{POLL_INTERVAL_SECONDS} saniye bekleniyor..."
                )
                time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nProducer kullanıcı tarafından durduruldu.")

    finally:
        producer.flush(10)
        http_session.close()
        print("OpenSky producer kapatıldı.")


if __name__ == "__main__":
    main()
