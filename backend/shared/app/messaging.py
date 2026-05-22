"""RabbitMQ messaging integration for asynchronous communication between microservices."""

import asyncio
import json
from typing import Any, Callable, Dict, Optional
from aio_pika import connect_robust, Message, ExchangeType, Channel, Connection
from aio_pika.abc import AbstractIncomingMessage

from app.logging import get_logger

logger = get_logger(__name__)


class EventBus:
    """Event bus for async communication between microservices via RabbitMQ."""

    def __init__(self, rabbitmq_url: str, service_name: str):
        self.rabbitmq_url = rabbitmq_url
        self.service_name = service_name
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self.exchanges: Dict[str, Any] = {}

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            self.connection = await connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            logger.info("Connected to RabbitMQ", extra={"rabbitmq_url": self.rabbitmq_url})
        except Exception as e:
            logger.error("Failed to connect to RabbitMQ", extra={"error": str(e)})
            raise

    async def declare_exchange(self, name: str, exchange_type: str = "topic") -> Any:
        if not self.channel:
            raise RuntimeError("Channel not initialized. Call connect() first.")
        exchange = await self.channel.declare_exchange(
            name=name, type=ExchangeType(exchange_type), durable=True,
        )
        self.exchanges[name] = exchange
        return exchange

    async def publish(self, exchange_name: str, routing_key: str, event_type: str,
                      payload: Dict[str, Any], correlation_id: Optional[str] = None) -> None:
        if exchange_name not in self.exchanges:
            await self.declare_exchange(exchange_name)
        exchange = self.exchanges[exchange_name]
        message_body = {
            "event_type": event_type, "source": self.service_name,
            "timestamp": asyncio.get_event_loop().time(),
            "correlation_id": correlation_id, "payload": payload,
        }
        message = Message(
            body=json.dumps(message_body, default=str).encode(),
            delivery_mode=2, content_type="application/json",
            headers={"event_type": event_type, "source": self.service_name},
        )
        await exchange.publish(message, routing_key=routing_key)
        logger.info("Published event", extra={"exchange": exchange_name, "routing_key": routing_key, "event_type": event_type})

    async def subscribe(self, exchange_name: str, routing_keys: list[str], queue_name: str, callback: Callable) -> str:
        if exchange_name not in self.exchanges:
            await self.declare_exchange(exchange_name)
        exchange = self.exchanges[exchange_name]
        queue = await self.channel.declare_queue(name=queue_name, durable=True)
        for routing_key in routing_keys:
            await queue.bind(exchange, routing_key=routing_key)

        async def on_message(message: AbstractIncomingMessage) -> None:
            async with message.process():
                try:
                    body = json.loads(message.body.decode())
                    await callback(body)
                except Exception as e:
                    logger.error("Error processing message", extra={"error": str(e), "exchange": exchange_name, "routing_key": message.routing_key})
        await queue.consume(on_message)
        logger.info("Subscribed to events", extra={"exchange": exchange_name, "queue": queue_name, "routing_keys": routing_keys})
        return queue_name

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()
            logger.info("RabbitMQ connection closed")


class EventTopics:
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_SIGNUP = "auth.signup"
    AUTH_FAILED = "auth.failed"
    ROLE_CREATED = "role.created"
    ROLE_UPDATED = "role.updated"
    ROLE_DELETED = "role.deleted"
    ROLE_ASSIGNED = "role.assigned"
    ROLE_REVOKED = "role.revoked"


class EventExchanges:
    DOMAIN_EVENTS = "nexus.domain.events"
    AUTH_EVENTS = "nexus.auth.events"
    AUDIT_EVENTS = "nexus.audit.events"