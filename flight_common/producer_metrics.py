"""OpenSky producer'ın Prometheus metrikleri.

Metric label'ları sınırlı sonuç kategorileridir. Uçak kimliği veya event_id
gibi her olayda değişen değerler label yapılmaz; aksi halde Prometheus'ta
gereksiz sayıda zaman serisi oluşur.
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server


OPENSKY_REQUESTS = Counter(
    "flight_producer_opensky_requests",
    "OpenSky veri sorgularının sonuçlara göre toplam sayısı.",
    ("outcome",),
)
OPENSKY_REQUEST_DURATION_SECONDS = Histogram(
    "flight_producer_opensky_request_duration_seconds",
    "OpenSky veri sorgularının süreleri.",
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30),
)
KAFKA_RECORDS_DELIVERED = Counter(
    "flight_producer_kafka_records_delivered",
    "Kafka'ya başarıyla teslim edilen uçuş kaydı sayısı.",
)
LAST_OPENSKY_SUCCESS_TIMESTAMP_SECONDS = Gauge(
    "flight_producer_last_opensky_success_timestamp_seconds",
    "Son başarılı OpenSky veri sorgusunun Unix zamanı.",
)
RATE_LIMIT_WAIT_SECONDS = Counter(
    "flight_producer_rate_limit_wait_seconds",
    "OpenSky rate-limit nedeniyle beklenen toplam süre.",
)


def start_metrics_server(port):
    """Prometheus'un cluster içinden çağıracağı HTTP endpoint'ini başlatır."""

    start_http_server(port)
