import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
    Path,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .config import load_settings
from .database import MongoRepository
from .kafka_gateway import KafkaRealtimeGateway
from .websocket_manager import WebSocketManager


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)
logger = logging.getLogger(__name__)

settings = load_settings()


@asynccontextmanager
async def lifespan(app):
    """Uygulama kaynaklarını kontrollü biçimde açar ve kapatır."""

    repository = MongoRepository(
        settings.mongodb_uri,
        settings.mongodb_database,
    )
    websocket_manager = WebSocketManager()
    kafka_gateway = KafkaRealtimeGateway(
        settings,
        websocket_manager,
    )
    kafka_stop_event = asyncio.Event()

    await asyncio.to_thread(repository.ping)
    logger.info("MongoDB bağlantısı başarılı.")

    kafka_task = asyncio.create_task(
        kafka_gateway.run(kafka_stop_event),
        name="kafka-realtime-gateway",
    )

    app.state.repository = repository
    app.state.websocket_manager = websocket_manager
    app.state.kafka_gateway = kafka_gateway
    app.state.kafka_task = kafka_task

    try:
        yield
    finally:
        logger.info("Backend bağlantıları kapatılıyor...")
        kafka_stop_event.set()

        try:
            await asyncio.wait_for(
                kafka_task,
                timeout=5,
            )
        except TimeoutError:
            kafka_task.cancel()
            await asyncio.gather(
                kafka_task,
                return_exceptions=True,
            )

        await asyncio.to_thread(repository.close)
        logger.info("Backend kapatıldı.")


app = FastAPI(
    title="Flight Data Pipeline API",
    version="1.0.0",
    description=(
        "MongoDB uçuş durumunu REST ile, yeni Kafka "
        "olaylarını WebSocket ile sunar."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


async def run_mongo(operation, *args):
    """Senkron PyMongo işlemini olay döngüsünü durdurmadan çalıştırır."""

    try:
        return await asyncio.to_thread(operation, *args)
    except PyMongoError as error:
        logger.exception("MongoDB okuma hatası.")
        raise HTTPException(
            status_code=503,
            detail="MongoDB geçici olarak kullanılamıyor.",
        ) from error


def repository_from(request):
    return request.app.state.repository


@app.get("/")
async def root():
    return {
        "service": "flight-data-pipeline-backend",
        "health": "/health",
        "docs": "/docs",
        "websocket": "/ws/aircraft",
    }


@app.get("/health")
async def health(request: Request):
    repository = repository_from(request)
    gateway = request.app.state.kafka_gateway

    mongo_status = "up"

    try:
        await asyncio.to_thread(repository.ping)
    except PyMongoError as error:
        mongo_status = "down"
        logger.warning("Healthcheck MongoDB hatası: %s", error)

    kafka_status = (
        "up"
        if gateway.status.connected
        else "down"
    )
    healthy = mongo_status == "up" and kafka_status == "up"

    payload = {
        "status": "ok" if healthy else "degraded",
        "components": {
            "mongodb": mongo_status,
            "kafka_realtime": kafka_status,
        },
        "kafka": {
            "topic": settings.kafka_topic,
            "consumer_group": (
                settings.kafka_realtime_consumer_group
            ),
            "processed_messages": (
                gateway.status.processed_messages
            ),
            "skipped_messages": (
                gateway.status.skipped_messages
            ),
            "last_error": gateway.status.last_error,
        },
        "websocket_clients": (
            request.app.state
            .websocket_manager
            .connection_count
        ),
    }

    return JSONResponse(
        status_code=200 if healthy else 503,
        content=payload,
    )


@app.get("/api/aircraft")
async def list_aircraft(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
):
    aircraft = await run_mongo(
        repository_from(request).list_live_aircraft,
        limit,
    )

    return {
        "count": len(aircraft),
        "items": aircraft,
    }


@app.get("/api/aircraft/{icao24}/history")
async def aircraft_history(
    request: Request,
    icao24: str = Path(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9a-fA-F]{6}$",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
):
    history = await run_mongo(
        repository_from(request).get_aircraft_history,
        icao24,
        limit,
    )

    return {
        "icao24": icao24.lower(),
        "count": len(history),
        "items": history,
    }


@app.get("/api/aircraft/{icao24}")
async def aircraft_detail(
    request: Request,
    icao24: str = Path(
        min_length=6,
        max_length=6,
        pattern=r"^[0-9a-fA-F]{6}$",
    ),
):
    aircraft = await run_mongo(
        repository_from(request).get_live_aircraft,
        icao24,
    )

    if aircraft is None:
        raise HTTPException(
            status_code=404,
            detail="Uçak bulunamadı.",
        )

    return aircraft


@app.get("/api/stats")
async def statistics(request: Request):
    return await run_mongo(
        repository_from(request).get_live_statistics
    )


@app.websocket("/ws/aircraft")
async def aircraft_websocket(websocket: WebSocket):
    origin = websocket.headers.get("origin")

    if origin and origin not in settings.cors_origins:
        await websocket.close(code=1008)
        return

    manager = websocket.app.state.websocket_manager
    await manager.connect(websocket)

    await websocket.send_json(
        {
            "type": "connection.ready",
            "message": (
                "İlk durum ve yeniden eşitleme için "
                "REST /api/aircraft endpoint'ini kullan."
            ),
        }
    )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
