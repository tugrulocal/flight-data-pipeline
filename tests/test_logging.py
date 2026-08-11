import json
import logging

from flight_common.logging import JsonFormatter


def make_record(message="normal message"):
    return logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_json_log_has_required_fields_and_default_event():
    payload = json.loads(JsonFormatter("test-service").format(make_record()))

    assert payload["timestamp"].endswith("+00:00")
    assert payload["level"] == "INFO"
    assert payload["service"] == "test-service"
    assert payload["event"] == "log"
    assert payload["message"] == "normal message"


def test_json_log_redacts_nested_secrets_and_raw_payloads():
    record = make_record(
        "request failed client_secret=visible Bearer visible-token"
    )
    record.event = "request_failed"
    record.client_secret = "visible"
    record.raw_payload = b"must-not-leak"
    record.context = {
        "headers": {"Authorization": "Bearer visible-token"},
        "icao24": "4baa12",
    }

    serialized = JsonFormatter("producer").format(record)
    payload = json.loads(serialized)

    assert "visible-token" not in serialized
    assert "must-not-leak" not in serialized
    assert payload["client_secret"] == "[REDACTED]"
    assert payload["raw_payload"] == "[REDACTED]"
    assert payload["context"]["headers"]["Authorization"] == "[REDACTED]"
    assert payload["context"]["icao24"] == "4baa12"
