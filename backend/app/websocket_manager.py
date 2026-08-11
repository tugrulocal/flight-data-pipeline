import asyncio

from fastapi import WebSocket


class WebSocketManager:
    """Bağlı frontend WebSocket istemcilerini yönetir."""

    def __init__(self, send_timeout_seconds=2.0):
        self._connections = set()
        self._lock = asyncio.Lock()
        self._send_timeout_seconds = send_timeout_seconds

    @property
    def connection_count(self):
        return len(self._connections)

    async def connect(self, websocket):
        await websocket.accept()

        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket):
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, payload):
        """Bir Kafka olayını bütün bağlı frontend'lere gönderir."""

        async with self._lock:
            connections = tuple(self._connections)

        async def send(websocket):
            try:
                await asyncio.wait_for(
                    websocket.send_json(payload),
                    timeout=self._send_timeout_seconds,
                )
                return None
            except Exception:
                return websocket

        disconnected = [
            websocket
            for websocket in await asyncio.gather(
                *(send(websocket) for websocket in connections)
            )
            if websocket is not None
        ]

        if disconnected:
            async with self._lock:
                for websocket in disconnected:
                    self._connections.discard(websocket)
