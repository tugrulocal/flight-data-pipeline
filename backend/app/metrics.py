from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


HTTP_REQUESTS = Counter(
    "flight_backend_http_requests",
    "Backend HTTP isteklerinin toplam sayısı.",
    ("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "flight_backend_http_request_duration_seconds",
    "Backend HTTP istek süreleri.",
    ("method", "route"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
MONGODB_UP = Gauge(
    "flight_backend_mongodb_up",
    "MongoDB health kontrolünün sonucu (1=up, 0=down).",
)
KAFKA_REALTIME_CONNECTED = Gauge(
    "flight_backend_kafka_realtime_connected",
    "Backend Kafka realtime gateway bağlantı durumu (1=up, 0=down).",
)
KAFKA_PROCESSED_MESSAGES = Gauge(
    "flight_backend_kafka_processed_messages",
    "Mevcut backend pod'u başladığından beri işlenen Kafka mesajı sayısı.",
)
KAFKA_PUBLISHED_BATCHES = Gauge(
    "flight_backend_kafka_published_batches",
    "Mevcut backend pod'u başladığından beri yayınlanan WebSocket batch sayısı.",
)
KAFKA_SKIPPED_MESSAGES = Gauge(
    "flight_backend_kafka_skipped_messages",
    "Mevcut backend pod'u başladığından beri atlanan Kafka mesajı sayısı.",
)
WEBSOCKET_CLIENTS = Gauge(
    "flight_backend_websocket_clients",
    "Aktif WebSocket istemcisi sayısı.",
)
DATA_FRESHNESS_SECONDS = Gauge(
    "flight_backend_data_freshness_seconds",
    "En son MongoDB'ye yazılan uçuş verisinin yaşı.",
)
DATA_FRESHNESS_AVAILABLE = Gauge(
    "flight_backend_data_freshness_available",
    "Veri tazeliği ölçülebiliyorsa 1, henüz veri yoksa 0.",
)


def route_label(scope):
    """Dinamik URL değerlerini metric label'ına taşımadan route şablonunu döndürür."""

    route = scope.get("route")
    return getattr(route, "path", "unmatched")


def observe_http_request(method, route, status_code, duration_seconds):
    labels = {
        "method": method,
        "route": route,
        "status_code": str(status_code),
    }
    HTTP_REQUESTS.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method,
        route=route,
    ).observe(duration_seconds)


def update_runtime_metrics(
    *,
    mongo_up,
    kafka_connected,
    gateway_status,
    websocket_clients,
    data_freshness_seconds,
):
    MONGODB_UP.set(1 if mongo_up else 0)
    KAFKA_REALTIME_CONNECTED.set(1 if kafka_connected else 0)
    KAFKA_PROCESSED_MESSAGES.set(gateway_status.processed_messages)
    KAFKA_PUBLISHED_BATCHES.set(gateway_status.published_batches)
    KAFKA_SKIPPED_MESSAGES.set(gateway_status.skipped_messages)
    WEBSOCKET_CLIENTS.set(websocket_clients)

    if data_freshness_seconds is None:
        DATA_FRESHNESS_AVAILABLE.set(0)
        DATA_FRESHNESS_SECONDS.set(0)
    else:
        DATA_FRESHNESS_AVAILABLE.set(1)
        DATA_FRESHNESS_SECONDS.set(data_freshness_seconds)


def render_metrics():
    return generate_latest(), CONTENT_TYPE_LATEST
