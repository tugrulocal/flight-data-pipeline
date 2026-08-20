import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

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
from fastapi.responses import JSONResponse, Response
from pymongo.errors import PyMongoError

from .config import load_settings
from .database import MongoRepository
from .kafka_gateway import KafkaRealtimeGateway
from .metrics import (
    observe_http_request,
    render_metrics,
    route_label,
    update_runtime_metrics,
)
from .websocket_manager import WebSocketManager
from flight_common.logging import configure_json_logging


configure_json_logging("backend")
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
    logger.info(
        "MongoDB bağlantısı başarılı.",
        extra={"event": "mongodb_connected"},
    )

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
        logger.info(
            "Backend bağlantıları kapatılıyor.",
            extra={"event": "shutdown_started"},
        )
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
        logger.info(
            "Backend kapatıldı.",
            extra={"event": "service_stopped"},
        )


app = FastAPI(
    title="Flight Data Pipeline API",
    version=settings.app_version,
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


@app.middleware("http")
async def collect_http_metrics(request, call_next):
    """İstekleri route şablonuyla ölçer; uçak kimliği gibi sınırsız label üretmez."""

    started_at = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        observe_http_request(
            request.method,
            route_label(request.scope),
            status_code,
            time.perf_counter() - started_at,
        )


async def run_mongo(operation, *args):
    """Senkron PyMongo işlemini olay döngüsünü durdurmadan çalıştırır."""

    try:
        return await asyncio.to_thread(operation, *args)
    except PyMongoError as error:
        logger.exception(
            "MongoDB okuma hatası.",
            extra={"event": "mongodb_read_error"},
        )
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
        "metrics": "/metrics",
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
        logger.warning(
            "Healthcheck MongoDB hatası.",
            extra={
                "event": "health_mongodb_error",
                "error": str(error),
            },
        )

    kafka_status = (
        "up"
        if gateway.status.connected
        else "down"
    )
    healthy = mongo_status == "up" and kafka_status == "up"

    latest_ingested_at = None
    if mongo_status == "up":
        try:
            latest_ingested_at = await asyncio.to_thread(
                repository.get_latest_ingested_at
            )
        except PyMongoError as error:
            logger.warning(
                "Veri tazeliği okunamadı.",
                extra={
                    "event": "freshness_read_error",
                    "error": str(error),
                },
            )

    age_seconds = None
    if isinstance(latest_ingested_at, datetime):
        age_seconds = max(
            0,
            int(
                (
                    datetime.now(timezone.utc)
                    - latest_ingested_at.astimezone(timezone.utc)
                ).total_seconds()
            ),
        )

    payload = {
        "status": "ok" if healthy else "degraded",
        "version": settings.app_version,
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
            "published_batches": (
                gateway.status.published_batches
            ),
            "skipped_messages": (
                gateway.status.skipped_messages
            ),
            "last_error": gateway.status.last_error,
            "batch_interval_ms": (
                settings.websocket_batch_interval_ms
            ),
            "batch_max_size": (
                settings.websocket_batch_max_size
            ),
        },
        "websocket_clients": (
            request.app.state
            .websocket_manager
            .connection_count
        ),
        "data_freshness": {
            "last_ingested_at": (
                latest_ingested_at.isoformat()
                if isinstance(latest_ingested_at, datetime)
                else None
            ),
            "age_seconds": age_seconds,
            "status": (
                "empty"
                if latest_ingested_at is None
                else "fresh"
                if age_seconds <= settings.live_position_window_minutes * 60
                else "stale"
            ),
        },
    }

    return JSONResponse(
        status_code=200 if healthy else 503,
        content=payload,
    )


@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    """Prometheus'un cluster içinden çağırdığı metric endpoint'i."""

    repository = repository_from(request)
    gateway = request.app.state.kafka_gateway
    mongo_up = True
    latest_ingested_at = None

    try:
        await asyncio.to_thread(repository.ping)
        latest_ingested_at = await asyncio.to_thread(
            repository.get_latest_ingested_at
        )
    except PyMongoError as error:
        mongo_up = False
        logger.warning(
            "Metrics MongoDB hatası.",
            extra={"event": "metrics_mongodb_error", "error": str(error)},
        )

    freshness_seconds = None
    if isinstance(latest_ingested_at, datetime):
        freshness_seconds = max(
            0,
            int(
                (
                    datetime.now(timezone.utc)
                    - latest_ingested_at.astimezone(timezone.utc)
                ).total_seconds()
            ),
        )

    update_runtime_metrics(
        mongo_up=mongo_up,
        kafka_connected=gateway.status.connected,
        gateway_status=gateway.status,
        websocket_clients=(
            request.app.state.websocket_manager.connection_count
        ),
        data_freshness_seconds=freshness_seconds,
    )
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


@app.get("/api/aircraft")
async def list_aircraft(
    request: Request,
    limit: int = Query(default=200, ge=1, le=50000),
):
    observed_since = datetime.now(timezone.utc) - timedelta(
        minutes=settings.live_position_window_minutes
    )
    aircraft, truncated = await run_mongo(
        repository_from(request).list_live_aircraft,
        limit,
        observed_since,
    )

    return {
        "count": len(aircraft),
        "items": aircraft,
        "window_minutes": settings.live_position_window_minutes,
        "truncated": truncated,
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
    observed_since = datetime.now(timezone.utc) - timedelta(
        minutes=settings.live_position_window_minutes
    )
    return await run_mongo(
        repository_from(request).get_live_statistics,
        observed_since,
    )


@app.websocket("/ws/aircraft")
async def aircraft_websocket(websocket: WebSocket):
    origin = websocket.headers.get("origin")

    if origin and origin not in settings.cors_origins:
        await websocket.close(code=1008)
        return

    manager = websocket.app.state.websocket_manager
    await manager.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "connection.ready",
                "message": (
                    "İlk durum ve yeniden eşitleme için "
                    "REST /api/aircraft endpoint'ini kullan."
                ),
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
