import asyncio
import json
import logging
from dataclasses import dataclass

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    TopicPartition,
)

from .contracts import public_aircraft_from_event


logger = logging.getLogger(__name__)


@dataclass
class KafkaGatewayStatus:
    running: bool = False
    connected: bool = False
    processed_messages: int = 0
    published_batches: int = 0
    skipped_messages: int = 0
    last_error: str | None = None


@dataclass
class PendingRealtimeMessage:
    event: dict | None
    message: object


class KafkaRealtimeGateway:
    """Kafka mesajlarını WebSocket istemcilerine yayınlar."""

    def __init__(self, settings, websocket_manager):
        self.settings = settings
        self.websocket_manager = websocket_manager
        self.status = KafkaGatewayStatus()
        self._batch_interval_seconds = (
            settings.websocket_batch_interval_ms / 1000
        )
        self._batch_max_size = settings.websocket_batch_max_size

    async def run(self, stop_event):
        """Gateway'i çalıştırır ve geçici Kafka hatalarında tekrar dener."""

        self.status.running = True

        try:
            while not stop_event.is_set():
                try:
                    await self._consume_session(stop_event)
                except KafkaException as error:
                    self.status.connected = False
                    self.status.last_error = str(error)
                    logger.exception(
                        "Kafka realtime gateway bağlantı hatası.",
                        extra={
                            "event": "kafka_connection_error",
                            "error": str(error),
                            "retry_seconds": 5,
                        },
                    )

                    try:
                        await asyncio.wait_for(
                            stop_event.wait(),
                            timeout=5,
                        )
                    except TimeoutError:
                        pass
        finally:
            self.status.running = False
            self.status.connected = False

    async def _consume_session(self, stop_event):
        consumer = Consumer(
            {
                "bootstrap.servers": (
                    self.settings.kafka_bootstrap_servers
                ),
                "group.id": (
                    self.settings.kafka_realtime_consumer_group
                ),
                "client.id": "flight-realtime-gateway",
                "auto.offset.reset": "latest",
                "enable.auto.commit": False,
                "enable.auto.offset.store": False,
            }
        )

        try:
            await asyncio.to_thread(
                consumer.list_topics,
                self.settings.kafka_topic,
                10,
            )

            consumer.subscribe([self.settings.kafka_topic])
            self.status.connected = True
            self.status.last_error = None

            logger.info(
                "Kafka realtime gateway hazır.",
                extra={
                    "event": "kafka_gateway_ready",
                    "topic": self.settings.kafka_topic,
                    "consumer_group": (
                        self.settings.kafka_realtime_consumer_group
                    ),
                    "batch_interval_ms": (
                        self.settings.websocket_batch_interval_ms
                    ),
                    "batch_max_size": (
                        self.settings.websocket_batch_max_size
                    ),
                },
            )

            pending_batch = []
            last_flush_at = asyncio.get_running_loop().time()

            while not stop_event.is_set():
                message = await asyncio.to_thread(
                    consumer.poll,
                    self._poll_timeout_seconds(pending_batch),
                )

                if message is None:
                    last_flush_at = await self._flush_due_batch(
                        consumer,
                        pending_batch,
                        last_flush_at,
                        force=True,
                    )
                    continue

                if message.error():
                    if (
                        message.error().code()
                        == KafkaError._PARTITION_EOF
                    ):
                        continue

                    raise KafkaException(message.error())

                await self._process_message(
                    consumer,
                    message,
                    pending_batch,
                )

                last_flush_at = await self._flush_due_batch(
                    consumer,
                    pending_batch,
                    last_flush_at,
                )

            await self._flush_due_batch(
                consumer,
                pending_batch,
                last_flush_at,
                force=True,
            )
        finally:
            self.status.connected = False
            await asyncio.to_thread(consumer.close)

    def _poll_timeout_seconds(self, pending_batch):
        if pending_batch:
            return self._batch_interval_seconds

        return 1.0

    async def _process_message(self, consumer, message, pending_batch):
        try:
            event = json.loads(
                message.value().decode("utf-8")
            )

            if not isinstance(event, dict) or not event.get("icao24"):
                raise ValueError(
                    "Mesaj geçerli bir uçak olayı değil."
                )

        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValueError,
        ) as error:
            self.status.skipped_messages += 1
            self.status.last_error = str(error)

            logger.error(
                "Realtime mesajı atlandı.",
                extra={
                    "event": "realtime_message_skipped",
                    "partition": message.partition(),
                    "offset": message.offset(),
                    "error": str(error),
                },
            )

            # Bozuk realtime mesajı yayınlanmaz. Ancak hemen commit etmek,
            # aynı partition'da batch içinde bekleyen önceki geçerli mesajı
            # atlayabilir. Offset bu yüzden batch sınırında birlikte ilerler.
            pending_batch.append(
                PendingRealtimeMessage(
                    event=None,
                    message=message,
                )
            )
        else:
            pending_batch.append(
                PendingRealtimeMessage(
                    event=public_aircraft_from_event(event, message),
                    message=message,
                )
            )

    async def _flush_due_batch(
        self,
        consumer,
        pending_batch,
        last_flush_at,
        force=False,
    ):
        if not pending_batch:
            return last_flush_at

        now = asyncio.get_running_loop().time()
        batch_is_full = len(pending_batch) >= self._batch_max_size
        batch_is_due = now - last_flush_at >= self._batch_interval_seconds

        if not force and not batch_is_full and not batch_is_due:
            return last_flush_at

        batch = pending_batch[:]
        public_events = [
            item.event for item in batch if item.event is not None
        ]

        if public_events:
            await self.websocket_manager.broadcast(
                {
                    "type": "aircraft.batch",
                    "items": public_events,
                }
            )

        highest_offsets = {}
        for item in batch:
            key = (item.message.topic(), item.message.partition())
            highest_offsets[key] = max(
                highest_offsets.get(key, -1),
                item.message.offset(),
            )

        await asyncio.to_thread(
            consumer.commit,
            offsets=[
                TopicPartition(topic, partition, offset + 1)
                for (topic, partition), offset in highest_offsets.items()
            ],
            asynchronous=False,
        )

        # Commit başarısız olursa buraya ulaşılmaz; mesajlar yeni consumer
        # oturumunda Kafka'dan tekrar okunur.
        del pending_batch[:len(batch)]
        self.status.processed_messages += len(public_events)
        if public_events:
            self.status.published_batches += 1

        if (
            public_events
            and (
                self.status.published_batches <= 10
                or self.status.published_batches % 20 == 0
            )
        ):
            last_message = batch[-1].message
            logger.info(
                "Realtime batch yayınlandı.",
                extra={
                    "event": "realtime_batch_published",
                    "batch_number": self.status.published_batches,
                    "batch_size": len(public_events),
                    "partition": last_message.partition(),
                    "last_offset": last_message.offset(),
                    "websocket_clients": (
                        self.websocket_manager.connection_count
                    ),
                },
            )

        return now
