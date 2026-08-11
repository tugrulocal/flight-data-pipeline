import json

import pytest

from producer.opensky_producer import (
    DeliveryTracker,
    get_effective_poll_interval,
    load_settings,
    normalize_state,
    run,
    send_states_to_kafka,
)


def sample_state():
    return [
        "4BAA12",
        " THY123 ",
        "Turkey",
        1_700_000_000,
        1_700_000_001,
        28.75,
        41.10,
        8500.0,
        False,
        220.0,
        90.0,
        0.0,
        None,
        8700.0,
        "1234",
        False,
        0,
        3,
    ]


def test_normalize_state_adds_contract_fields():
    event = normalize_state(
        sample_state(),
        1_700_000_010,
        event_id="event-1",
        ingested_at="2024-01-01T00:00:00+00:00",
    )

    assert event["schema_version"] == 1
    assert event["event_id"] == "event-1"
    assert event["icao24"] == "4baa12"
    assert event["callsign"] == "THY123"
    assert event["baro_altitude_m"] == 8500.0


def test_normalize_state_uses_last_contact_when_position_time_is_missing():
    state = sample_state()
    state[3] = None
    state[4] = 1_700_000_123
    event = normalize_state(state, 1_700_000_999)
    assert event["observed_at"] == "2023-11-14T22:15:23+00:00"


def test_settings_reject_partial_credentials():
    with pytest.raises(ValueError, match="birlikte"):
        load_settings({"OPENSKY_CLIENT_ID": "only-id"})


def test_settings_reject_invalid_numbers():
    with pytest.raises(ValueError, match="POLL_INTERVAL_SECONDS"):
        load_settings({"POLL_INTERVAL_SECONDS": "0"})


def test_global_defaults_and_anonymous_interval_protect_quota():
    settings = load_settings({})

    assert settings.area_mode == "global"
    assert settings.poll_interval_seconds == 120
    assert get_effective_poll_interval(settings) == 900


def test_anonymous_turkey_interval_protects_quota():
    settings = load_settings({
        "OPENSKY_AREA_MODE": "turkey",
        "POLL_INTERVAL_SECONDS": "30",
    })

    assert get_effective_poll_interval(settings) == 660


def test_authenticated_global_interval_uses_configured_value():
    settings = load_settings({
        "OPENSKY_AREA_MODE": "global",
        "POLL_INTERVAL_SECONDS": "120",
        "OPENSKY_CLIENT_ID": "client-id",
        "OPENSKY_CLIENT_SECRET": "client-secret",
    })

    assert get_effective_poll_interval(settings) == 120


class FakeProducer:
    def __init__(self, delivery_error=None):
        self.delivery_error = delivery_error
        self.callbacks = []

    def produce(self, **kwargs):
        json.loads(kwargs["value"])
        self.callbacks.append(kwargs["on_delivery"])

    def poll(self, _timeout):
        return 0

    def flush(self, _timeout):
        for callback in self.callbacks:
            callback(self.delivery_error, object())
        self.callbacks.clear()
        return 0


def test_run_fetches_immediately_then_waits_effective_interval():
    calls = []

    class Client:
        def fetch_states(self):
            calls.append("fetch")
            return 1_700_000_010, []

        def close(self):
            calls.append("close")

    class StopEvent:
        def is_set(self):
            return False

        def wait(self, seconds):
            calls.append(("wait", seconds))
            return False

    settings = load_settings({"MAX_POLLS": "2"})
    run(
        settings,
        producer=FakeProducer(),
        opensky_client=Client(),
        stop_event=StopEvent(),
    )

    assert calls[:3] == ["fetch", ("wait", 900), "fetch"]


def test_delivery_failure_makes_poll_fail():
    producer = FakeProducer(delivery_error="broker failed")
    with pytest.raises(RuntimeError, match="başarısız=1"):
        send_states_to_kafka(
            producer,
            "aircraft.positions.raw.v1",
            [sample_state()],
            1_700_000_010,
        )


def test_delivery_tracker_counts_success():
    tracker = DeliveryTracker()
    tracker.callback(None, object())
    assert tracker.delivered == 1
    assert tracker.failed == 0
