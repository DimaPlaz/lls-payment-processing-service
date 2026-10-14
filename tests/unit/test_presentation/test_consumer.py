import typing
import uuid
from unittest import mock

import pytest
from cqrs.message_brokers import protocol
from faststream import rabbit
from faststream.rabbit import message as rabbit_message

from payments.domain import entities, enums
from payments.infrastructure.message_broker import middlewares, topology
from payments.presentation.consumer import main as consumer_main
from payments.service import models
from tests.mock import fakes


def payment_created_message(payment_id: int, amount: typing.Any) -> dict[str, typing.Any]:
    """Сообщение в том виде, в котором его публикует outbox паблишер"""
    event = models.CustomNotificationEvent[models.PaymentCreatedPayload](
        event_name="payment_created_notification",
        topic=topology.payments.routing(),
        payload=models.PaymentCreatedPayload(id=payment_id, amount=amount),
    )
    return protocol.Message(
        message_name=event.event_name,
        message_id=event.event_id,
        topic=event.topic,
        payload=event.to_dict(),
    ).to_dict()


async def publish_payment_message(
    broker: rabbit.RabbitBroker,
    message: dict[str, typing.Any],
    headers: dict[str, typing.Any] | None = None,
) -> None:
    """Публикация так же, как это делает outbox паблишер: в exchange payments с routing key очереди"""
    await broker.publish(
        message,
        exchange=topology.payments_exchange,
        routing_key=topology.payments.routing(),
        headers=headers,
    )


@pytest.fixture
def retry_publish(monkeypatch: pytest.MonkeyPatch, rabbit_broker: rabbit.RabbitBroker) -> mock.AsyncMock:
    """Перехватывает публикации в retry exchange.

    У retry-очередей нет подписчиков (сообщения возвращаются в основную очередь по TTL через DLX),
    поэтому TestRabbitBroker падает на них с SubscriberNotFound
    """
    original_publish = rabbit_broker.publish
    retry_publish_mock = mock.AsyncMock()

    async def publish(message: typing.Any = None, *args: typing.Any, **kwargs: typing.Any):
        exchange = kwargs.get("exchange")
        if exchange is not None and exchange.name == topology.retry_exchange.name:
            return await retry_publish_mock(message, **kwargs)
        return await original_publish(message, *args, **kwargs)

    monkeypatch.setattr(rabbit_broker, "publish", publish)
    return retry_publish_mock


@pytest.fixture
def reject(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    """Отслеживает reject сообщения: в RabbitMQ оно уйдёт через DLX в DLQ"""
    reject_mock = mock.AsyncMock()
    monkeypatch.setattr(rabbit_message.RabbitMessage, "reject", reject_mock)
    return reject_mock


async def test_handle_payment_positive(
    rabbit_broker: rabbit.RabbitBroker,
    payment_repository: fakes.FakePaymentRepository,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    payment = payment_factory()
    message = payment_created_message(payment.id, payment.amount)

    # Act
    await publish_payment_message(rabbit_broker, message)

    # Assert
    consumer_main.handle_payment.mock.assert_called_once_with(message)
    assert payment_repository.storage[payment.id].status == enums.PaymentStatus.SUCCEEDED
    assert webhook_client.calls == [
        {
            "url": str(payment.webhook_url),
            "idempotency_key": payment.idempotency_key,
            "data": {"success": True},
        },
    ]


async def test_handle_payment_not_found_sends_to_retry_negative(
    rabbit_broker: rabbit.RabbitBroker,
    retry_publish: mock.AsyncMock,
    reject: mock.AsyncMock,
    webhook_client: fakes.FakeWebhookClient,
):
    # Arrange
    message = payment_created_message(payment_id=1, amount="100.00")

    # Act
    await publish_payment_message(rabbit_broker, message)

    # Assert
    retry_publish.assert_awaited_once()
    retry_kwargs = retry_publish.await_args_list[0].kwargs
    assert retry_kwargs["routing_key"] == topology.retry_queues[0].routing()
    assert retry_kwargs["headers"][middlewares.RETRY_HEADER] == 1
    reject.assert_not_awaited()
    assert webhook_client.calls == []


@pytest.mark.parametrize("attempt", range(len(topology.retry_queues)))
async def test_handle_payment_retry_goes_to_next_retry_queue_negative(
    rabbit_broker: rabbit.RabbitBroker,
    retry_publish: mock.AsyncMock,
    attempt: int,
):
    # Arrange
    message = payment_created_message(payment_id=1, amount="100.00")

    # Act
    await publish_payment_message(rabbit_broker, message, headers={middlewares.RETRY_HEADER: attempt})

    # Assert
    retry_publish.assert_awaited_once()
    retry_kwargs = retry_publish.await_args_list[0].kwargs
    assert retry_kwargs["routing_key"] == topology.retry_queues[attempt].routing()
    assert retry_kwargs["headers"][middlewares.RETRY_HEADER] == attempt + 1


async def test_handle_payment_retries_exhausted_sends_to_dlq_negative(
    rabbit_broker: rabbit.RabbitBroker,
    retry_publish: mock.AsyncMock,
    reject: mock.AsyncMock,
):
    # Arrange
    message = payment_created_message(payment_id=1, amount="100.00")
    headers = {middlewares.RETRY_HEADER: len(topology.retry_queues)}

    # Act
    await publish_payment_message(rabbit_broker, message, headers=headers)

    # Assert
    reject.assert_awaited_once()
    retry_publish.assert_not_awaited()


async def test_handle_payment_invalid_message_sends_to_dlq_negative(
    rabbit_broker: rabbit.RabbitBroker,
    retry_publish: mock.AsyncMock,
    reject: mock.AsyncMock,
    payment_repository: fakes.FakePaymentRepository,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    payment = payment_factory()
    message = {"messageId": str(uuid.uuid4()), "payload": {"id": payment.id}}

    # Act
    await publish_payment_message(rabbit_broker, message)

    # Assert
    reject.assert_awaited_once()
    retry_publish.assert_not_awaited()
    assert payment_repository.storage[payment.id].status == enums.PaymentStatus.PENDING
    assert webhook_client.calls == []


async def test_handle_duplicate_message_positive(
    rabbit_broker: rabbit.RabbitBroker,
    retry_publish: mock.AsyncMock,
    reject: mock.AsyncMock,
    payment_repository: fakes.FakePaymentRepository,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    payment = payment_factory()
    message = payment_created_message(payment.id, payment.amount)
    await publish_payment_message(rabbit_broker, message)
    processed = payment_repository.storage[payment.id]

    # Act
    await publish_payment_message(rabbit_broker, message)

    # Assert
    retry_publish.assert_not_awaited()
    reject.assert_not_awaited()
    assert payment_repository.storage[payment.id].processed_at == processed.processed_at
    assert len(webhook_client.calls) == 2
