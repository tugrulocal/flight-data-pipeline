import pytest

from kafka import admin
from kafka.admin import (
    TopicSpec,
    positive_integer,
    reconcile_topics_with_retry,
    topic_specs,
)


def test_topic_spec_contains_required_retention_config():
    spec = TopicSpec("events", 60_000, 1_048_576)

    assert spec.config == {
        "cleanup.policy": "delete",
        "retention.ms": "60000",
        "retention.bytes": "1048576",
    }


@pytest.mark.parametrize("value", ["", "0", "-1", "abc", "1.5"])
def test_positive_integer_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("RETENTION", value)

    with pytest.raises(ValueError, match="pozitif tam sayı"):
        positive_integer("RETENTION", 10)


def test_topic_specs_use_release_defaults(monkeypatch):
    for name in (
        "KAFKA_TOPIC",
        "KAFKA_DLQ_TOPIC",
        "KAFKA_RAW_RETENTION_MS",
        "KAFKA_RAW_RETENTION_BYTES",
        "KAFKA_DLQ_RETENTION_MS",
        "KAFKA_DLQ_RETENTION_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)

    raw, dlq = topic_specs()

    assert (raw.name, raw.retention_ms, raw.retention_bytes) == (
        "aircraft.positions.raw.v1",
        172_800_000,
        10_737_418_240,
    )
    assert (dlq.name, dlq.retention_ms, dlq.retention_bytes) == (
        "aircraft.positions.dlq.v1",
        2_592_000_000,
        1_073_741_824,
    )


def test_topic_reconcile_retries_transient_startup_error(monkeypatch):
    attempts = []
    configured = []
    verified = []

    def create_topics(_client, _specs):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("controller henüz hazır değil")

    monkeypatch.setattr(admin, "create_topics", create_topics)
    monkeypatch.setattr(
        admin,
        "configure_topics",
        lambda _client, _specs: configured.append(1),
    )
    monkeypatch.setattr(
        admin,
        "verify_topics",
        lambda _client, _specs: verified.append(1),
    )

    reconcile_topics_with_retry(
        object(),
        (TopicSpec("events", 60_000, 1_048_576),),
        mutate=True,
        max_attempts=3,
        backoff_seconds=0,
    )

    assert len(attempts) == 2
    assert configured == [1]
    assert verified == [1]


def test_topic_reconcile_fails_after_bounded_attempts(monkeypatch):
    attempts = []

    def fail_verification(_client, _specs):
        attempts.append(1)
        raise RuntimeError("config henüz görünmüyor")

    monkeypatch.setattr(admin, "verify_topics", fail_verification)

    with pytest.raises(RuntimeError, match="3 denemede tamamlanamadı"):
        reconcile_topics_with_retry(
            object(),
            (TopicSpec("events", 60_000, 1_048_576),),
            mutate=False,
            max_attempts=3,
            backoff_seconds=0,
        )

    assert len(attempts) == 3
