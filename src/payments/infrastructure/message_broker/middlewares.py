import logging
import typing

import faststream
import pydantic
from fast_depends import exceptions as fd_exceptions
from faststream import exceptions

from payments.infrastructure.message_broker import topology


logger = logging.getLogger(__name__)
RETRY_HEADER = "x-retry-count"


class RetryMiddleware(faststream.BaseMiddleware):
    # исключения управления потоком FastStream — не ретраим
    passthrough = (
        exceptions.AckMessage,
        exceptions.NackMessage,
        exceptions.RejectMessage,
        exceptions.SkipMessage,
    )
    # сообщение не соответствует схеме — повторять бессмысленно
    invalid_message = (
        pydantic.ValidationError,
        fd_exceptions.ValidationError,
    )

    async def consume_scope(
        self,
        call_next: typing.Callable[[typing.Any], typing.Awaitable[typing.Any]],
        msg: typing.Any,  # RabbitMessage
    ) -> typing.Any:
        try:
            return await call_next(msg)
        except self.passthrough:
            raise
        except self.invalid_message as exc:
            # reject без requeue -> RabbitMQ перекладывает сообщение через DLX в DLQ
            logger.error("Invalid message, sending to DLQ: %r", exc)
            await msg.reject()
        except Exception as exc:
            attempt = int(msg.headers.get(RETRY_HEADER, 0))

            if attempt >= len(topology.retry_queues):
                logger.error("Retries exhausted, sending to DLQ: %r", exc)
                await msg.reject()
                return

            retry_queue = topology.retry_queues[attempt]
            logger.warning("Retry #%d via %s after error: %r", attempt + 1, retry_queue.name, exc)

            broker = self.context.get("broker")
            await broker.publish(
                msg.body,
                exchange=topology.retry_exchange,
                routing_key=retry_queue.routing(),
                headers={**msg.headers, RETRY_HEADER: attempt + 1},
                message_id=msg.message_id,
                correlation_id=msg.correlation_id,
                content_type=msg.content_type,
                persist=True,
            )
            # Исключение подавлено -> исходное сообщение будет ack'нуто
