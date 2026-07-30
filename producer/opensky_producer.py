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
    os.getenv("POLL_INTERVAL_SECONDS", "30")
)

# 0 değeri producer'ın sürekli çalışması anlamına gelir.
MAX_POLLS = int(
    os.getenv("MAX_POLLS", "0")
)

OPENSKY_URL = "https://opensky-network.org/api/states/all"
OPENSKY_TOKEN_URL = os.getenv(
    "OPENSKY_TOKEN_URL",
    "https://auth.opensky-network.org/auth/realms/"
    "opensky-network/protocol/openid-connect/token",
)
OPENSKY_CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID")
OPENSKY_CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET")
OPENSKY_AREA_MODE = os.getenv("OPENSKY_AREA_MODE", "turkey").strip().lower()
TOKEN_REFRESH_MARGIN_SECONDS = 60

# Türkiye ve yakın çevresi
TURKEY_BOUNDING_BOX = {
    "lamin": 35.00,
    "lomin": 25.00,
    "lamax": 43.50,
    "lomax": 46.00,
    "extended": 1,
}

SUPPORTED_AREA_MODES = {"turkey", "global"}


producer = Producer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "client.id": "opensky-flight-producer",
        "acks": "all",
        "enable.idempotence": True,
    }
)

http_session = requests.Session()
opensky_access_token = None
opensky_token_expires_at = 0.0


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


def has_opensky_credentials():
    """OpenSky OAuth credential'larının verilip verilmediğini kontrol eder."""

    return bool(OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET)


def get_opensky_access_token():
    """OpenSky OAuth access token'ını alır ve süresi dolana kadar yeniden kullanır."""

    global opensky_access_token, opensky_token_expires_at

    if not has_opensky_credentials():
        return None

    now = time.monotonic()

    if opensky_access_token and now < opensky_token_expires_at:
        return opensky_access_token

    response = http_session.post(
        OPENSKY_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": OPENSKY_CLIENT_ID,
            "client_secret": OPENSKY_CLIENT_SECRET,
        },
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()
    opensky_access_token = payload["access_token"]

    expires_in = int(payload.get("expires_in", 1800))
    usable_lifetime = max(
        expires_in - TOKEN_REFRESH_MARGIN_SECONDS,
        60,
    )
    opensky_token_expires_at = now + usable_lifetime

    print("OpenSky OAuth token alındı veya yenilendi.")

    return opensky_access_token


def get_opensky_headers():
    """OpenSky API çağrısında kullanılacak HTTP header'larını üretir."""

    access_token = get_opensky_access_token()

    if access_token is None:
        return None

    return {
        "Authorization": f"Bearer {access_token}",
    }


def get_opensky_params():
    """Seçilen veri alanına göre OpenSky query parametrelerini üretir."""

    if OPENSKY_AREA_MODE == "turkey":
        return TURKEY_BOUNDING_BOX

    if OPENSKY_AREA_MODE == "global":
        return {
            "extended": 1,
        }

    raise ValueError(
        "OPENSKY_AREA_MODE değeri 'turkey' veya 'global' olmalı. "
        f"Gelen değer: {OPENSKY_AREA_MODE!r}"
    )


def fetch_opensky_states():
    """OpenSky'dan seçilen kapsamdaki uçakları getirir."""

    response = http_session.get(
        OPENSKY_URL,
        params=get_opensky_params(),
        headers=get_opensky_headers(),
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
    print(f"Veri alanı modu: {OPENSKY_AREA_MODE}")
    print(f"OpenSky query params: {get_opensky_params()}")
    print(f"Çağrı aralığı: {POLL_INTERVAL_SECONDS} saniye")
    print(
        "OpenSky auth: "
        + (
            "OAuth client credentials"
            if has_opensky_credentials()
            else "anonim"
        )
    )
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
