import asyncio

from fastapi import WebSocket


class WebSocketManager:
    """Bağlı frontend WebSocket istemcilerini yönetir."""

    def __init__(self):
        self._connections = set()
        self._lock = asyncio.Lock()

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

        disconnected = []

        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)

        if disconnected:
            async with self._lock:
                for websocket in disconnected:
                    self._connections.discard(websocket)
