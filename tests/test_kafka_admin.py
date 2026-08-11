import pytest

from kafka.admin import TopicSpec, positive_integer, topic_specs


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
