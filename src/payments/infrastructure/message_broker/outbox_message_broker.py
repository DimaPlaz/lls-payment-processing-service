from faststream import rabbit
from cqrs.message_brokers import protocol as broker_protocol


class RabbitMessageBroker(broker_protocol.MessageBroker):
    """Публикует события outbox в exchange; topic события используется как routing key"""

    def __init__(self, broker: rabbit.RabbitBroker, exchange: rabbit.RabbitExchange, durable: bool = True) -> None:
        self._broker = broker
        self._exchange = exchange
        self._durable = durable

    async def send_message(self, message: broker_protocol.Message) -> None:
        await self._broker.publish(
            message.to_dict(),
            exchange=self._exchange,
            routing_key=message.topic,
            message_id=str(message.message_id),
            persist=self._durable,
        )
