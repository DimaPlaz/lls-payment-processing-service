from faststream import rabbit
from faststream.rabbit.schemas import queue as queue_schemas

from payments.infrastructure import settings

_durable = settings.rabbitmq.durable

payments_exchange = rabbit.RabbitExchange(
    settings.rabbitmq.payments_exchange,
    type=rabbit.ExchangeType.DIRECT,
    durable=_durable,
)
retry_exchange = rabbit.RabbitExchange(
    settings.rabbitmq.retry_exchange,
    type=rabbit.ExchangeType.DIRECT,
    durable=_durable,
)
dead_letter_exchange = rabbit.RabbitExchange(
    settings.rabbitmq.dl_exchange,
    type=rabbit.ExchangeType.DIRECT,
    durable=_durable,
)

dlq = rabbit.RabbitQueue(
    settings.rabbitmq.dl_queue,
    durable=_durable,
    routing_key=settings.rabbitmq.dl_queue,
)
payments = rabbit.RabbitQueue(
    settings.rabbitmq.payments_queue,
    durable=_durable,
    routing_key=settings.rabbitmq.payments_queue,
    # Отклонённые сообщения (reject без requeue) уходят в DLQ
    arguments=queue_schemas.ClassicQueueArgs({
        "x-dead-letter-exchange": dead_letter_exchange.name,
        "x-dead-letter-routing-key": dlq.routing(),
    }),
)


def _retry_queue(delay_seconds: int) -> rabbit.RabbitQueue:
    name = f"{settings.rabbitmq.retry_exchange}.{delay_seconds}s"
    return rabbit.RabbitQueue(
        name,
        durable=_durable,
        routing_key=name,
        # Подписчиков нет: по истечении TTL сообщение возвращается в основную очередь
        arguments=queue_schemas.ClassicQueueArgs({
            "x-message-ttl": delay_seconds * 1000,
            "x-dead-letter-exchange": payments_exchange.name,
            "x-dead-letter-routing-key": payments.routing(),
        }),
    )


retry_queues = tuple(_retry_queue(delay) for delay in settings.rabbitmq.retry_delays)

bindings: tuple[tuple[rabbit.RabbitExchange, rabbit.RabbitQueue], ...] = (
    (payments_exchange, payments),
    (dead_letter_exchange, dlq),
    *((retry_exchange, queue) for queue in retry_queues),
)


async def declare(broker: rabbit.RabbitBroker) -> None:
    """Объявляет все exchange'и, очереди и binding'и. Идемпотентно, вызывается при старте consumer и publisher"""
    for exchange, queue in bindings:
        robust_exchange = await broker.declare_exchange(exchange)
        robust_queue = await broker.declare_queue(queue)
        await robust_queue.bind(robust_exchange, routing_key=queue.routing())
