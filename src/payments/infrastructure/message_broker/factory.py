from faststream import rabbit

from payments.infrastructure import settings
from payments.infrastructure.message_broker import middlewares


def rabbit_broker_factory():
    return rabbit.RabbitBroker(
        str(settings.rabbitmq.dsn),
        middlewares=[middlewares.RetryMiddleware],  # type: ignore[list-item]
    )
