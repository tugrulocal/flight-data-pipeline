import asyncio
import json
import logging
from dataclasses import dataclass

from confluent_kafka import Consumer, KafkaError, KafkaException


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
    event: dict
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
                        "Kafka realtime gateway bağlantı hatası."
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
                "Kafka realtime gateway hazır | topic=%s | group=%s | "
                "batch_interval_ms=%s | batch_max_size=%s",
                self.settings.kafka_topic,
                self.settings.kafka_realtime_consumer_group,
                self.settings.websocket_batch_interval_ms,
                self.settings.websocket_batch_max_size,
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
                "Realtime mesajı atlandı | partition=%s | "
                "offset=%s | hata=%s",
                message.partition(),
                message.offset(),
                error,
            )

            await asyncio.to_thread(
                consumer.commit,
                message=message,
                asynchronous=False,
            )
        else:
            pending_batch.append(
                PendingRealtimeMessage(
                    event=event,
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
        pending_batch.clear()

        await self.websocket_manager.broadcast(
            {
                "type": "aircraft.batch",
                "items": [item.event for item in batch],
            }
        )

        for item in batch:
            await asyncio.to_thread(
                consumer.commit,
                message=item.message,
                asynchronous=False,
            )

        self.status.processed_messages += len(batch)
        self.status.published_batches += 1

        if (
            self.status.published_batches <= 10
            or self.status.published_batches % 20 == 0
        ):
            last_message = batch[-1].message
            logger.info(
                "Realtime batch yayınlandı #%s | "
                "adet=%s | son_offset=%s | clients=%s",
                self.status.published_batches,
                len(batch),
                last_message.offset(),
                self.websocket_manager.connection_count,
            )

        return now
