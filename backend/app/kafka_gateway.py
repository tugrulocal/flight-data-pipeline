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
    skipped_messages: int = 0
    last_error: str | None = None


class KafkaRealtimeGateway:
    """Kafka mesajlarını WebSocket istemcilerine yayınlar."""

    def __init__(self, settings, websocket_manager):
        self.settings = settings
        self.websocket_manager = websocket_manager
        self.status = KafkaGatewayStatus()

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
                "Kafka realtime gateway hazır | topic=%s | group=%s",
                self.settings.kafka_topic,
                self.settings.kafka_realtime_consumer_group,
            )

            while not stop_event.is_set():
                message = await asyncio.to_thread(
                    consumer.poll,
                    1.0,
                )

                if message is None:
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
                )
        finally:
            self.status.connected = False
            await asyncio.to_thread(consumer.close)

    async def _process_message(self, consumer, message):
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
        else:
            await self.websocket_manager.broadcast(
                {
                    "type": "aircraft.position",
                    "data": event,
                    "kafka": {
                        "topic": message.topic(),
                        "partition": message.partition(),
                        "offset": message.offset(),
                    },
                }
            )

            self.status.processed_messages += 1

            if (
                self.status.processed_messages <= 10
                or self.status.processed_messages % 100 == 0
            ):
                logger.info(
                    "Realtime mesajı yayınlandı #%s | "
                    "icao24=%s | offset=%s | clients=%s",
                    self.status.processed_messages,
                    event["icao24"],
                    message.offset(),
                    self.websocket_manager.connection_count,
                )

        await asyncio.to_thread(
            consumer.commit,
            message=message,
            asynchronous=False,
        )
