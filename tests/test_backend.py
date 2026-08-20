import asyncio
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.config import load_settings
from backend.app.contracts import public_aircraft_from_event
from backend.app.database import MongoRepository
from backend.app.kafka_gateway import KafkaRealtimeGateway, PendingRealtimeMessage
from backend.app.main import aircraft_websocket, health, metrics
from backend.app.websocket_manager import WebSocketManager


def test_backend_settings_include_runtime_window():
    settings = load_settings()
    assert settings.live_position_window_minutes == 20
    assert settings.app_version == "1.0.0-rc.3"


def test_backend_default_origins_follow_runtime_app_port(monkeypatch):
    monkeypatch.setenv("APP_PORT", "5175")
    monkeypatch.setenv("CORS_ORIGINS", "")

    settings = load_settings()

    assert settings.cors_origins == [
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]


def test_public_contract_removes_internal_fields_and_adds_metadata():
    class Message:
        def topic(self):
            return "raw"

        def partition(self):
            return 2

        def offset(self):
            return 9

    public = public_aircraft_from_event(
        {
            "icao24": "4baa12",
            "latitude": 41.0,
            "longitude": 29.0,
            "client_secret": "must-not-leak",
        },
        Message(),
    )
    assert "client_secret" not in public
    assert public["on_ground"] is None
    assert public["kafka_partition"] == 2
    assert public["kafka_offset"] == 9


def test_live_list_uses_recent_filter_projection_and_truncation_probe():
    class Cursor:
        def __init__(self, documents):
            self.documents = documents

        def sort(self, field, direction):
            self.sort_args = (field, direction)
            return self

        def limit(self, value):
            self.limit_value = value
            return self

        def __iter__(self):
            return iter(self.documents[:self.limit_value])

    class Collection:
        def find(self, query, projection):
            self.query = query
            self.projection = projection
            self.cursor = Cursor([
                {"_id": "a", "icao24": "a"},
                {"_id": "b", "icao24": "b"},
                {"_id": "c", "icao24": "c"},
            ])
            return self.cursor

    observed_since = datetime.now(timezone.utc)
    repository = object.__new__(MongoRepository)
    repository.live_positions = Collection()

    items, truncated = repository.list_live_aircraft(2, observed_since)

    assert repository.live_positions.query == {
        "observed_at": {"$gte": observed_since}
    }
    assert "client_secret" not in repository.live_positions.projection
    assert repository.live_positions.projection["icao24"] == 1
    assert repository.live_positions.cursor.limit_value == 3
    assert len(items) == 2
    assert truncated is True
    assert items[0]["on_ground"] is None


def test_statistics_returns_single_consistent_aggregation_result():
    class Collection:
        def aggregate(self, pipeline):
            self.pipeline = pipeline
            return [
                {
                    "total_aircraft": 3,
                    "airborne": 1,
                    "on_ground": 1,
                    "unknown_ground_state": 1,
                    "last_observed_at": datetime.now(timezone.utc),
                }
            ]

    repository = object.__new__(MongoRepository)
    repository.live_positions = Collection()
    result = repository.get_live_statistics(datetime.now(timezone.utc))
    assert result["total_aircraft"] == 3
    assert result["unknown_ground_state"] == 1
    assert len(repository.live_positions.pipeline) == 3


def test_stale_data_is_informational_and_does_not_fail_health():
    class Repository:
        def ping(self):
            return None

        def get_latest_ingested_at(self):
            return datetime(2000, 1, 1, tzinfo=timezone.utc)

    gateway = SimpleNamespace(
        status=SimpleNamespace(
            connected=True,
            processed_messages=10,
            published_batches=2,
            skipped_messages=1,
            last_error=None,
        )
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                repository=Repository(),
                kafka_gateway=gateway,
                websocket_manager=SimpleNamespace(connection_count=0),
            )
        )
    )

    response = asyncio.run(health(request))
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["data_freshness"]["status"] == "stale"


def test_metrics_expose_aggregated_runtime_state():
    class Repository:
        def ping(self):
            return None

        def get_latest_ingested_at(self):
            return datetime(2000, 1, 1, tzinfo=timezone.utc)

    gateway = SimpleNamespace(
        status=SimpleNamespace(
            connected=True,
            processed_messages=10,
            published_batches=2,
            skipped_messages=1,
        )
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                repository=Repository(),
                kafka_gateway=gateway,
                websocket_manager=SimpleNamespace(connection_count=3),
            )
        )
    )

    response = asyncio.run(metrics(request))

    assert response.status_code == 200
    assert b"flight_backend_mongodb_up 1.0" in response.body
    assert b"flight_backend_kafka_realtime_connected 1.0" in response.body
    assert b"flight_backend_kafka_processed_messages 10.0" in response.body
    assert b"flight_backend_websocket_clients 3.0" in response.body
    assert b"flight_backend_data_freshness_available 1.0" in response.body


def test_realtime_batch_commits_highest_offset_once_per_partition():
    class Manager:
        def __init__(self):
            self.payload = None
            self.connection_count = 0

        async def broadcast(self, payload):
            self.payload = payload

    class Message:
        def __init__(self, partition, offset):
            self._partition = partition
            self._offset = offset

        def topic(self):
            return "raw"

        def partition(self):
            return self._partition

        def offset(self):
            return self._offset

    class Consumer:
        def commit(self, **kwargs):
            self.kwargs = kwargs

    manager = Manager()
    gateway = KafkaRealtimeGateway(
        SimpleNamespace(
            websocket_batch_interval_ms=250,
            websocket_batch_max_size=500,
        ),
        manager,
    )
    pending = [
        PendingRealtimeMessage({"icao24": "a"}, Message(0, 3)),
        PendingRealtimeMessage({"icao24": "b"}, Message(0, 5)),
        PendingRealtimeMessage({"icao24": "c"}, Message(1, 2)),
    ]
    consumer = Consumer()

    asyncio.run(gateway._flush_due_batch(consumer, pending, 0, force=True))
    offsets = {
        (item.partition, item.offset)
        for item in consumer.kwargs["offsets"]
    }
    assert offsets == {(0, 6), (1, 3)}
    assert consumer.kwargs["asynchronous"] is False
    assert manager.payload["type"] == "aircraft.batch"


def test_invalid_realtime_message_waits_for_batch_commit_boundary():
    class Manager:
        connection_count = 0

        def __init__(self):
            self.payload = None

        async def broadcast(self, payload):
            self.payload = payload

    class Message:
        def __init__(self, value, offset):
            self._value = value
            self._offset = offset

        def value(self):
            return self._value

        def topic(self):
            return "raw"

        def partition(self):
            return 0

        def offset(self):
            return self._offset

    class Consumer:
        def __init__(self):
            self.commits = []

        def commit(self, **kwargs):
            self.commits.append(kwargs)

    async def scenario():
        manager = Manager()
        gateway = KafkaRealtimeGateway(
            SimpleNamespace(
                websocket_batch_interval_ms=250,
                websocket_batch_max_size=500,
            ),
            manager,
        )
        consumer = Consumer()
        pending = []
        valid = json.dumps({"icao24": "4baa12"}).encode()

        await gateway._process_message(
            consumer, Message(valid, 10), pending
        )
        await gateway._process_message(
            consumer, Message(b"not-json", 11), pending
        )

        assert consumer.commits == []
        await gateway._flush_due_batch(consumer, pending, 0, force=True)
        return manager, gateway, consumer, pending

    manager, gateway, consumer, pending = asyncio.run(scenario())
    assert len(manager.payload["items"]) == 1
    published = manager.payload["items"][0]
    assert published["_id"] == "4baa12"
    assert published["icao24"] == "4baa12"
    assert published["on_ground"] is None
    assert published["kafka_topic"] == "raw"
    assert published["kafka_partition"] == 0
    assert published["kafka_offset"] == 10
    assert consumer.commits[0]["offsets"][0].offset == 12
    assert gateway.status.processed_messages == 1
    assert gateway.status.skipped_messages == 1
    assert pending == []


def test_failed_batch_commit_keeps_pending_messages():
    class Manager:
        connection_count = 0

        async def broadcast(self, _payload):
            return None

    class Message:
        def topic(self):
            return "raw"

        def partition(self):
            return 0

        def offset(self):
            return 5

    class Consumer:
        def commit(self, **_kwargs):
            raise RuntimeError("commit failed")

    gateway = KafkaRealtimeGateway(
        SimpleNamespace(
            websocket_batch_interval_ms=250,
            websocket_batch_max_size=500,
        ),
        Manager(),
    )
    pending = [PendingRealtimeMessage({"icao24": "4baa12"}, Message())]

    with pytest.raises(RuntimeError, match="commit failed"):
        asyncio.run(
            gateway._flush_due_batch(Consumer(), pending, 0, force=True)
        )

    assert len(pending) == 1


def test_websocket_broadcast_removes_failed_client():
    class Socket:
        async def send_json(self, _payload):
            raise RuntimeError("client gone")

    async def scenario():
        manager = WebSocketManager()
        socket = Socket()
        manager._connections.add(socket)
        await manager.broadcast({"type": "test"})
        return manager.connection_count

    assert asyncio.run(scenario()) == 0


def test_websocket_broadcast_does_not_wait_for_slow_client():
    class SlowSocket:
        async def send_json(self, _payload):
            await asyncio.sleep(1)

    class FastSocket:
        def __init__(self):
            self.received = False

        async def send_json(self, _payload):
            self.received = True

    async def scenario():
        manager = WebSocketManager(send_timeout_seconds=0.01)
        slow = SlowSocket()
        fast = FastSocket()
        manager._connections.update({slow, fast})
        started = time.monotonic()
        await manager.broadcast({"type": "test"})
        return manager, fast, time.monotonic() - started

    manager, fast, elapsed = asyncio.run(scenario())
    assert fast.received is True
    assert manager.connection_count == 1
    assert elapsed < 0.2


def test_initial_websocket_send_failure_cleans_manager_connection():
    class Manager:
        def __init__(self):
            self.connections = set()

        async def connect(self, websocket):
            self.connections.add(websocket)

        async def disconnect(self, websocket):
            self.connections.discard(websocket)

    class Socket:
        headers = {}

        def __init__(self, manager):
            self.app = SimpleNamespace(
                state=SimpleNamespace(websocket_manager=manager)
            )

        async def send_json(self, _payload):
            raise RuntimeError("client disconnected during ready")

    async def scenario():
        manager = Manager()
        socket = Socket(manager)
        with pytest.raises(RuntimeError, match="client disconnected"):
            await aircraft_websocket(socket)
        return manager

    assert asyncio.run(scenario()).connections == set()
