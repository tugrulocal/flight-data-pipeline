import json
import logging
import os
import signal
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from confluent_kafka import Producer

from flight_common.logging import configure_json_logging


logger = logging.getLogger(__name__)

OPENSKY_URL = "https://opensky-network.org/api/states/all"
DEFAULT_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/"
    "opensky-network/protocol/openid-connect/token"
)
TOKEN_REFRESH_MARGIN_SECONDS = 60
GLOBAL_WARNING_POLL_INTERVAL_SECONDS = 90
GLOBAL_RECOMMENDED_POLL_INTERVAL_SECONDS = 120
ANONYMOUS_MIN_POLL_INTERVAL_SECONDS = {
    "turkey": 660,
    "global": 900,
}
SUPPORTED_AREA_MODES = {"turkey", "global"}

TURKEY_BOUNDING_BOX = {
    "lamin": 35.00,
    "lomin": 25.00,
    "lamax": 43.50,
    "lomax": 46.00,
    "extended": 1,
}


def parse_int(name, value, *, minimum):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} tam sayı olmalı.") from error

    if parsed < minimum:
        raise ValueError(f"{name} en az {minimum} olmalı.")

    return parsed


@dataclass(frozen=True)
class ProducerSettings:
    kafka_bootstrap_servers: str
    kafka_topic: str
    poll_interval_seconds: int
    max_polls: int
    area_mode: str
    opensky_token_url: str
    opensky_client_id: str | None
    opensky_client_secret: str | None

    @property
    def has_credentials(self):
        return bool(self.opensky_client_id and self.opensky_client_secret)


def load_settings(environ=None):
    values = os.environ if environ is None else environ
    area_mode = values.get("OPENSKY_AREA_MODE", "global").strip().lower()

    if area_mode not in SUPPORTED_AREA_MODES:
        raise ValueError(
            "OPENSKY_AREA_MODE değeri 'turkey' veya 'global' olmalı. "
            f"Gelen değer: {area_mode!r}"
        )

    client_id = values.get("OPENSKY_CLIENT_ID") or None
    client_secret = values.get("OPENSKY_CLIENT_SECRET") or None

    if bool(client_id) != bool(client_secret):
        raise ValueError(
            "OPENSKY_CLIENT_ID ve OPENSKY_CLIENT_SECRET birlikte verilmelidir."
        )

    return ProducerSettings(
        kafka_bootstrap_servers=values.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        ),
        kafka_topic=values.get(
            "KAFKA_TOPIC", "aircraft.positions.raw.v1"
        ),
        poll_interval_seconds=parse_int(
            "POLL_INTERVAL_SECONDS",
            values.get("POLL_INTERVAL_SECONDS", "120"),
            minimum=1,
        ),
        max_polls=parse_int(
            "MAX_POLLS", values.get("MAX_POLLS", "0"), minimum=0
        ),
        area_mode=area_mode,
        opensky_token_url=values.get(
            "OPENSKY_TOKEN_URL", DEFAULT_TOKEN_URL
        ),
        opensky_client_id=client_id,
        opensky_client_secret=client_secret,
    )


def get_effective_poll_interval(settings):
    """Kimliksiz çağrıların günlük OpenSky kotasını tüketmesini sınırlar."""

    if settings.has_credentials:
        return settings.poll_interval_seconds

    return max(
        settings.poll_interval_seconds,
        ANONYMOUS_MIN_POLL_INTERVAL_SECONDS[settings.area_mode],
    )


def create_kafka_producer(settings):
    return Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "opensky-flight-producer",
            "acks": "all",
            "enable.idempotence": True,
        }
    )


def unix_to_iso(timestamp):
    if timestamp is None:
        return None

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def get_opensky_params(area_mode):
    if area_mode == "turkey":
        return dict(TURKEY_BOUNDING_BOX)

    return {"extended": 1}


class OpenSkyClient:
    def __init__(self, settings, session=None):
        self.settings = settings
        self.session = session or requests.Session()
        self.access_token = None
        self.token_expires_at = 0.0

    def close(self):
        self.session.close()

    def get_access_token(self):
        if not self.settings.has_credentials:
            return None

        now = time.monotonic()
        if self.access_token and now < self.token_expires_at:
            return self.access_token

        response = self.session.post(
            self.settings.opensky_token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.opensky_client_id,
                "client_secret": self.settings.opensky_client_secret,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token")

        if not isinstance(access_token, str) or not access_token:
            raise ValueError("OpenSky token cevabında access_token bulunamadı.")

        expires_in = parse_int(
            "OpenSky expires_in", payload.get("expires_in", 1800), minimum=1
        )
        self.access_token = access_token
        self.token_expires_at = now + max(
            expires_in - TOKEN_REFRESH_MARGIN_SECONDS, 60
        )
        logger.info("OpenSky OAuth token alındı veya yenilendi.", extra={"event": "oauth_token_refreshed"})
        return self.access_token

    def fetch_states(self):
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"} if token else None
        response = self.session.get(
            OPENSKY_URL,
            params=get_opensky_params(self.settings.area_mode),
            headers=headers,
            timeout=20,
        )
        remaining = response.headers.get("X-Rate-Limit-Remaining")
        logger.info(
            "OpenSky API cevabı alındı.",
            extra={
                "event": "opensky_response",
                "http_status": response.status_code,
                "rate_limit_remaining": remaining,
            },
        )
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("OpenSky cevabı JSON nesnesi olmalı.")

        return payload.get("time"), payload.get("states") or []


def normalize_state(state, api_time, *, event_id=None, ingested_at=None):
    if not isinstance(state, (list, tuple)) or len(state) < 17:
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
        "schema_version": 1,
        "event_id": event_id or str(uuid.uuid4()),
        "icao24": str(icao24).lower(),
        "callsign": callsign,
        "origin_country": state[2],
        "time_position": state[3],
        "observed_at": unix_to_iso(state[3] or state[4] or api_time),
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
        "ingested_at": ingested_at or datetime.now(timezone.utc).isoformat(),
        "source": "opensky",
    }


class DeliveryTracker:
    def __init__(self):
        self.delivered = 0
        self.failed = 0
        self.last_error = None

    def callback(self, error, _message):
        if error is None:
            self.delivered += 1
            return

        self.failed += 1
        self.last_error = str(error)
        logger.error(
            "Kafka mesajı teslim edilemedi.",
            extra={"event": "kafka_delivery_failed", "error": str(error)},
        )


def send_states_to_kafka(producer, topic, states, api_time):
    tracker = DeliveryTracker()
    skipped_count = 0
    queued_count = 0

    for state in states:
        event = normalize_state(state, api_time)
        if event is None:
            skipped_count += 1
            continue

        encoded = json.dumps(event, allow_nan=False).encode("utf-8")

        while True:
            try:
                producer.produce(
                    topic=topic,
                    key=event["icao24"].encode("utf-8"),
                    value=encoded,
                    on_delivery=tracker.callback,
                )
                break
            except BufferError:
                producer.poll(0.1)

        producer.poll(0)
        queued_count += 1

    remaining = producer.flush(30)
    if remaining or tracker.failed:
        raise RuntimeError(
            "Kafka teslimi tamamlanamadı: "
            f"bekleyen={remaining}, başarısız={tracker.failed}, "
            f"son_hata={tracker.last_error}"
        )

    result = {
        "api_records": len(states),
        "queued": queued_count,
        "delivered": tracker.delivered,
        "skipped": skipped_count,
    }
    logger.info("OpenSky turu Kafka'ya teslim edildi.", extra={"event": "poll_delivered", **result})
    return result


def get_retry_seconds(response):
    value = response.headers.get("X-Rate-Limit-Retry-After-Seconds")
    try:
        return max(int(value), 60)
    except (TypeError, ValueError):
        return 3600


def install_signal_handlers(stop_event):
    def request_stop(signum, _frame):
        logger.info("Kapanış sinyali alındı.", extra={"event": "shutdown_requested", "signal": signum})
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)


def run(settings, *, producer=None, opensky_client=None, stop_event=None):
    kafka_producer = producer or create_kafka_producer(settings)
    client = opensky_client or OpenSkyClient(settings)
    stopping = stop_event or threading.Event()
    poll_number = 0
    effective_poll_interval = get_effective_poll_interval(settings)

    if stop_event is None:
        install_signal_handlers(stopping)

    logger.info(
        "OpenSky producer başladı.",
        extra={
            "event": "service_started",
            "topic": settings.kafka_topic,
            "area_mode": settings.area_mode,
            "poll_interval_seconds": settings.poll_interval_seconds,
            "max_polls": settings.max_polls,
            "authentication": "oauth" if settings.has_credentials else "anonymous",
            "configured_poll_interval_seconds": settings.poll_interval_seconds,
            "effective_poll_interval_seconds": effective_poll_interval,
        },
    )

    if (
        settings.area_mode == "global"
        and effective_poll_interval < GLOBAL_WARNING_POLL_INTERVAL_SECONDS
    ):
        logger.warning(
            "Global mod çağrı aralığı kotayı hızlı tüketebilir.",
            extra={
                "event": "risky_global_interval",
                "recommended_seconds": GLOBAL_RECOMMENDED_POLL_INTERVAL_SECONDS,
            },
        )

    try:
        while not stopping.is_set() and (
            settings.max_polls == 0 or poll_number < settings.max_polls
        ):
            poll_number += 1
            try:
                api_time, states = client.fetch_states()
                send_states_to_kafka(
                    kafka_producer, settings.kafka_topic, states, api_time
                )
            except requests.HTTPError as error:
                if error.response is not None and error.response.status_code == 429:
                    retry_seconds = get_retry_seconds(error.response)
                    logger.warning(
                        "OpenSky kredi limiti aşıldı.",
                        extra={"event": "rate_limited", "retry_seconds": retry_seconds},
                    )
                    stopping.wait(retry_seconds)
                    continue
                logger.error("OpenSky HTTP hatası.", extra={"event": "http_error", "error": str(error)})
            except requests.RequestException as error:
                logger.error("OpenSky bağlantı hatası.", extra={"event": "request_error", "error": str(error)})
            except (ValueError, RuntimeError) as error:
                logger.error("Producer işlem hatası.", extra={"event": "processing_error", "error": str(error)})

            if settings.max_polls == 0 or poll_number < settings.max_polls:
                stopping.wait(effective_poll_interval)
    finally:
        remaining = kafka_producer.flush(10)
        client.close()
        logger.info(
            "OpenSky producer kapatıldı.",
            extra={"event": "service_stopped", "remaining_messages": remaining},
        )


def main():
    configure_json_logging("producer")
    try:
        settings = load_settings()
        run(settings)
    except ValueError as error:
        logger.error("Producer ayarı geçersiz.", extra={"event": "configuration_error", "error": str(error)})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
