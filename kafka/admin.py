import json
import os
import sys
import time
from dataclasses import dataclass

from confluent_kafka import ConsumerGroupTopicPartitions, KafkaException, TopicPartition
from confluent_kafka.admin import (
    AdminClient,
    AlterConfigOpType,
    ConfigEntry,
    ConfigResource,
    NewTopic,
    OffsetSpec,
    ResourceType,
)


@dataclass(frozen=True)
class TopicSpec:
    name: str
    retention_ms: int
    retention_bytes: int

    @property
    def config(self) -> dict[str, str]:
        return {
            "cleanup.policy": "delete",
            "retention.ms": str(self.retention_ms),
            "retention.bytes": str(self.retention_bytes),
        }


def positive_integer(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} pozitif tam sayı olmalı: {raw}") from exc
    if value <= 0:
        raise ValueError(f"{name} pozitif tam sayı olmalı: {raw}")
    return value


def topic_specs() -> tuple[TopicSpec, TopicSpec]:
    return (
        TopicSpec(
            os.getenv("KAFKA_TOPIC", "aircraft.positions.raw.v1"),
            positive_integer("KAFKA_RAW_RETENTION_MS", 172_800_000),
            positive_integer("KAFKA_RAW_RETENTION_BYTES", 10_737_418_240),
        ),
        TopicSpec(
            os.getenv("KAFKA_DLQ_TOPIC", "aircraft.positions.dlq.v1"),
            positive_integer("KAFKA_DLQ_RETENTION_MS", 2_592_000_000),
            positive_integer("KAFKA_DLQ_RETENTION_BYTES", 1_073_741_824),
        ),
    )


def wait_for_broker(bootstrap_servers: str, timeout_seconds: int = 90) -> AdminClient:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        client = AdminClient({"bootstrap.servers": bootstrap_servers})
        try:
            client.list_topics(timeout=5)
            return client
        except KafkaException as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(
        f"Kafka {timeout_seconds} saniye içinde hazır olmadı: {last_error}"
    )


def create_topics(client: AdminClient, specs: tuple[TopicSpec, ...]) -> None:
    metadata = client.list_topics(timeout=10)
    missing = [
        NewTopic(spec.name, num_partitions=1, replication_factor=1)
        for spec in specs
        if spec.name not in metadata.topics
    ]
    if not missing:
        return
    for topic, future in client.create_topics(missing, request_timeout=15).items():
        future.result(timeout=20)
        print(json.dumps({"event": "topic.created", "topic": topic}))


def configure_topics(client: AdminClient, specs: tuple[TopicSpec, ...]) -> None:
    resources = []
    for spec in specs:
        entries = [
            ConfigEntry(
                name,
                value,
                incremental_operation=AlterConfigOpType.SET,
            )
            for name, value in spec.config.items()
        ]
        resources.append(
            ConfigResource(
                ResourceType.TOPIC,
                spec.name,
                incremental_configs=entries,
            )
        )

    for resource, future in client.incremental_alter_configs(
        resources, request_timeout=15
    ).items():
        future.result(timeout=20)
        print(json.dumps({"event": "topic.configured", "topic": resource.name}))


def verify_topics(client: AdminClient, specs: tuple[TopicSpec, ...]) -> None:
    resources = [ConfigResource(ResourceType.TOPIC, spec.name) for spec in specs]
    described = client.describe_configs(resources, request_timeout=15)
    expected_by_name = {spec.name: spec for spec in specs}
    for resource, future in described.items():
        actual = future.result(timeout=20)
        expected = expected_by_name[resource.name]
        for name, value in expected.config.items():
            if actual[name].value != value:
                raise RuntimeError(
                    f"{resource.name} config doğrulaması başarısız: "
                    f"{name}={actual[name].value!r}, beklenen={value!r}"
                )

        metadata = client.list_topics(resource.name, timeout=10)
        partition_count = len(metadata.topics[resource.name].partitions)
        if partition_count != 1:
            raise RuntimeError(
                f"{resource.name} partition sayısı 1 değil: {partition_count}"
            )
        print(
            json.dumps(
                {
                    "event": "topic.ready",
                    "topic": resource.name,
                    "partitions": partition_count,
                    **expected.config,
                },
                sort_keys=True,
            )
        )


def reconcile_topics_with_retry(
    client: AdminClient,
    specs: tuple[TopicSpec, ...],
    *,
    mutate: bool,
    max_attempts: int = 10,
    backoff_seconds: float = 2,
) -> None:
    """Broker startup races may outlive the first successful metadata request."""
    last_error: KafkaException | RuntimeError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            if mutate:
                create_topics(client, specs)
                configure_topics(client, specs)
            verify_topics(client, specs)
            return
        except (KafkaException, RuntimeError) as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            print(
                json.dumps(
                    {
                        "event": "topic.retry",
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            time.sleep(backoff_seconds)
    raise RuntimeError(
        f"Kafka topic işlemi {max_attempts} denemede tamamlanamadı: {last_error}"
    )


def print_consumer_group_lag(client: AdminClient, group_id: str) -> None:
    future = client.list_consumer_group_offsets(
        [ConsumerGroupTopicPartitions(group_id)], request_timeout=15
    )[group_id]
    result = future.result(timeout=20)
    committed = result.topic_partitions or []
    latest_requests = {
        TopicPartition(item.topic, item.partition): OffsetSpec.latest()
        for item in committed
    }
    latest = (
        client.list_offsets(latest_requests, request_timeout=15)
        if latest_requests
        else {}
    )
    total_lag = 0
    rows = []
    for item in committed:
        key = TopicPartition(item.topic, item.partition)
        high_watermark = latest[key].result(timeout=20).offset
        committed_offset = item.offset
        lag = (
            max(0, high_watermark - committed_offset)
            if committed_offset >= 0
            else high_watermark
        )
        total_lag += lag
        rows.append(
            {
                "topic": item.topic,
                "partition": item.partition,
                "committed_offset": committed_offset,
                "latest_offset": high_watermark,
                "lag": lag,
            }
        )
    print(json.dumps({"group": group_id, "total_lag": total_lag, "partitions": rows}))


def main() -> int:
    try:
        command = sys.argv[1] if len(sys.argv) > 1 else "init"
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        client = wait_for_broker(bootstrap_servers)
        if command == "group":
            if len(sys.argv) != 3:
                raise ValueError("Kullanım: kafka_admin.py group CONSUMER_GROUP")
            print_consumer_group_lag(client, sys.argv[2])
        elif command in {"init", "topics"}:
            specs = topic_specs()
            reconcile_topics_with_retry(
                client,
                specs,
                mutate=command == "init",
            )
        else:
            raise ValueError("Komut init, topics veya group olmalı")
        return 0
    except (KafkaException, RuntimeError, ValueError) as exc:
        print(f"topic-init HATA: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
