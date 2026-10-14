import datetime
import types
import typing
from unittest import mock

import cqrs
import pytest

from payments.domain import entities, enums
from payments.service import exceptions, models
from tests.mock import fakes


def payment_created_event(payment: entities.Payment) -> models.CustomNotificationEvent[models.PaymentCreatedPayload]:
    return models.CustomNotificationEvent[models.PaymentCreatedPayload](
        event_name="payment_created_notification",
        topic="payments.new",
        payload=models.PaymentCreatedPayload(id=payment.id, amount=payment.amount),
    )


async def test_process_payment_succeeded_positive(
    event_mediator: cqrs.EventMediator,
    payment_repository: fakes.FakePaymentRepository,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    payment = payment_factory()

    # Act
    await event_mediator.send(payment_created_event(payment))

    # Assert
    processed = payment_repository.storage[payment.id]
    assert processed.status == enums.PaymentStatus.SUCCEEDED
    assert processed.processed_at is not None
    assert payment_repository.commits == 1


async def test_process_payment_failed_positive(
    event_mediator: cqrs.EventMediator,
    payment_repository: fakes.FakePaymentRepository,
    payment_factory: typing.Callable[..., entities.Payment],
    payment_processing: types.SimpleNamespace,
):
    # Arrange
    payment_processing.random = lambda: 0.0
    payment = payment_factory()

    # Act
    await event_mediator.send(payment_created_event(payment))

    # Assert
    processed = payment_repository.storage[payment.id]
    assert processed.status == enums.PaymentStatus.FAILED
    assert processed.processed_at is not None
    assert payment_repository.commits == 1


@pytest.mark.parametrize(
    ("failure_chance", "expected_success"),
    [
        (1.0, True),
        (0.0, False),
    ],
)
async def test_process_payment_notifies_webhook_positive(
    event_mediator: cqrs.EventMediator,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
    payment_processing: types.SimpleNamespace,
    failure_chance: float,
    expected_success: bool,
):
    # Arrange
    payment_processing.random = lambda: failure_chance
    payment = payment_factory()

    # Act
    await event_mediator.send(payment_created_event(payment))

    # Assert
    assert webhook_client.calls == [
        {
            "url": str(payment.webhook_url),
            "idempotency_key": payment.idempotency_key,
            "data": {"success": expected_success},
        },
    ]


async def test_process_payment_not_found_negative(
    event_mediator: cqrs.EventMediator,
    payment_repository: fakes.FakePaymentRepository,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    payment = payment_factory()
    del payment_repository.storage[payment.id]

    # Act
    with pytest.raises(exceptions.PaymentNotFound):
        await event_mediator.send(payment_created_event(payment))

    # Assert
    assert webhook_client.calls == []
    assert payment_repository.commits == 0


@pytest.mark.parametrize("status", [enums.PaymentStatus.SUCCEEDED, enums.PaymentStatus.FAILED])
async def test_process_payment_already_processed_resends_webhook_positive(
    event_mediator: cqrs.EventMediator,
    payment_repository: fakes.FakePaymentRepository,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
    status: enums.PaymentStatus,
):
    # Arrange
    processed_at = datetime.datetime.now(datetime.UTC)
    payment = payment_factory(status=status, processed_at=processed_at)

    # Act
    await event_mediator.send(payment_created_event(payment))

    # Assert
    stored = payment_repository.storage[payment.id]
    assert stored.status == status
    assert stored.processed_at == processed_at
    assert payment_repository.commits == 0
    assert webhook_client.calls == [
        {
            "url": str(payment.webhook_url),
            "idempotency_key": payment.idempotency_key,
            "data": {"success": status == enums.PaymentStatus.SUCCEEDED},
        },
    ]


async def test_process_payment_webhook_error_saves_status_negative(
    monkeypatch: pytest.MonkeyPatch,
    event_mediator: cqrs.EventMediator,
    payment_repository: fakes.FakePaymentRepository,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    async def notify_with_error(**kwargs):
        raise ConnectionError("webhook is unavailable")

    monkeypatch.setattr(webhook_client, "notify", notify_with_error)
    payment = payment_factory()

    # Act
    with pytest.raises(ConnectionError):
        await event_mediator.send(payment_created_event(payment))

    # Assert
    stored = payment_repository.storage[payment.id]
    assert stored.status == enums.PaymentStatus.SUCCEEDED
    assert stored.processed_at is not None
    assert payment_repository.commits == 1


async def test_process_payment_retry_after_webhook_error_positive(
    event_mediator: cqrs.EventMediator,
    payment_repository: fakes.FakePaymentRepository,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
    payment_processing: types.SimpleNamespace,
):
    # Arrange
    payment = payment_factory()
    event = payment_created_event(payment)
    with mock.patch.object(webhook_client, "notify", side_effect=ConnectionError("webhook is unavailable")):
        with pytest.raises(ConnectionError):
            await event_mediator.send(event)
    first_attempt = payment_repository.storage[payment.id]
    # Если обработка повторится, платёж завершится неуспешно
    payment_processing.random = lambda: 0.0

    # Act
    await event_mediator.send(event)

    # Assert
    stored = payment_repository.storage[payment.id]
    assert stored.status == enums.PaymentStatus.SUCCEEDED
    assert stored.processed_at == first_attempt.processed_at
    assert payment_repository.commits == 1
    assert webhook_client.calls == [
        {
            "url": str(payment.webhook_url),
            "idempotency_key": payment.idempotency_key,
            "data": {"success": True},
        },
    ]


async def test_process_payment_concurrent_finalize_positive(
    monkeypatch: pytest.MonkeyPatch,
    event_mediator: cqrs.EventMediator,
    payment_repository: fakes.FakePaymentRepository,
    webhook_client: fakes.FakeWebhookClient,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    pending_payment = payment_factory()
    # Другой consumer уже финализировал платёж, но этот прочитал его ещё в PENDING
    payment_repository.storage[pending_payment.id] = pending_payment.model_copy(
        update={"status": enums.PaymentStatus.FAILED, "processed_at": datetime.datetime.now(datetime.UTC)},
    )
    original_get = payment_repository.get
    stale_reads = [pending_payment]

    async def get_with_stale_first_read(payment_id: int) -> entities.Payment | None:
        return stale_reads.pop() if stale_reads else await original_get(payment_id)

    monkeypatch.setattr(payment_repository, "get", get_with_stale_first_read)

    # Act
    await event_mediator.send(payment_created_event(pending_payment))

    # Assert
    assert payment_repository.storage[pending_payment.id].status == enums.PaymentStatus.FAILED
    assert webhook_client.calls[0]["data"] == {"success": False}
