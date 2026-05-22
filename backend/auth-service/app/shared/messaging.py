"""Messaging utilities for Auth Service."""

import json
from typing import Any, Callable, Dict, Optional
from aio_pika import connect_robust, Message, ExchangeType, Channel, Connection
from aio_pika.abc import AbstractIncomingMessage


class EventBus:
    """Event bus for async communication via RabbitMQ."""

    def __init__(self, rabbitmq_url: str, service_name: str):
        self.rabbitmq_url = rabbitmq_url
        self.service_name = service_name
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self.exchanges: Dict[str, Any] = {}

    async def connect(self) -> None:
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)

    async def declare_exchange(self, name: str, exchange_type: str = "topic") -> Any:
        if not self.channel:
            raise RuntimeError("Channel not initialized")
        exchange = await self.channel.declare_exchange(
            name=name, type=ExchangeType(exchange_type), durable=True,
        )
        self.exchanges[name] = exchange
        return exchange

    async def publish(self, exchange_name: str, routing_key: str, event_type: str, payload: Dict[str, Any]) -> None:
        if exchange_name not in self.exchanges:
            await self.declare_exchange(exchange_name)
        exchange = self.exchanges[exchange_name]
        message_body = {
            "event_type": event_type, "source": self.service_name,
            "payload": payload,
        }
        message = Message(
            body=json.dumps(message_body, default=str).encode(),
            delivery_mode=2, content_type="application/json",
        )
        await exchange.publish(message, routing_key=routing_key)

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
                    print(f"Error processing message: {e}")

        await queue.consume(on_message)
        return queue_name

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()


class EventTopics:
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_SIGNUP = "auth.signup"
    AUTH_FAILED = "auth.failed"
    ROLE_ASSIGNED = "role.assigned"


class EventExchanges:
    DOMAIN_EVENTS = "nexus.domain.events"
    AUTH_EVENTS = "nexus.auth.events"
    AUDIT_EVENTS = "nexus.audit.events"