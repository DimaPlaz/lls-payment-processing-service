import decimal
import typing

import cqrs
import faker as faker_lib
import pydantic
import pytest

from payments.domain import entities, enums
from payments.service import exceptions, models
from tests.mock import fakes


@pytest.fixture
def create_payment_command(faker: faker_lib.Faker) -> models.CreatePayment:
    return models.CreatePayment(
        amount=decimal.Decimal("100.50"),
        currency=enums.Currency.RUB,
        description=faker.sentence(),
        meta={"order_id": faker.uuid4()},
        webhook_url=pydantic.HttpUrl(faker.url()),
        idempotency_key=faker.uuid4(),
    )


async def test_create_payment_returns_pending_payment_positive(
    request_mediator: cqrs.RequestMediator,
    create_payment_command: models.CreatePayment,
):
    # Arrange
    # Act
    result = await request_mediator.send(create_payment_command)

    # Assert
    assert isinstance(result, models.PaymentCreated)
    assert result.status == enums.PaymentStatus.PENDING


async def test_create_payment_saves_payment_positive(
    request_mediator: cqrs.RequestMediator,
    payment_repository: fakes.FakePaymentRepository,
    create_payment_command: models.CreatePayment,
):
    # Arrange
    # Act
    result = await request_mediator.send(create_payment_command)

    # Assert
    payment = payment_repository.storage[result.payment_id]
    assert payment.amount == create_payment_command.amount
    assert payment.currency == create_payment_command.currency
    assert payment.description == create_payment_command.description
    assert payment.meta == create_payment_command.meta
    assert payment.webhook_url == create_payment_command.webhook_url
    assert payment.idempotency_key == create_payment_command.idempotency_key
    assert payment.status == enums.PaymentStatus.PENDING
    assert payment.processed_at is None


async def test_create_payment_adds_event_to_outbox_positive(
    request_mediator: cqrs.RequestMediator,
    outbox_repository: fakes.FakeOutboxRepository,
    create_payment_command: models.CreatePayment,
):
    # Arrange
    # Act
    result = await request_mediator.send(create_payment_command)

    # Assert
    assert len(outbox_repository.events) == 1
    event = outbox_repository.events[0]
    assert isinstance(event, models.CustomNotificationEvent)
    assert event.event_name == "payment_created_notification"
    assert event.topic == "payments.new"
    assert event.payload == models.PaymentCreatedPayload(id=result.payment_id, amount=create_payment_command.amount)


async def test_create_payment_commits_transaction_positive(
    request_mediator: cqrs.RequestMediator,
    uow: fakes.FakeUoW,
    create_payment_command: models.CreatePayment,
):
    # Arrange
    # Act
    await request_mediator.send(create_payment_command)

    # Assert
    assert uow.committed
    assert not uow.rolled_back


async def test_create_payment_repository_error_rolls_back_negative(
    monkeypatch: pytest.MonkeyPatch,
    request_mediator: cqrs.RequestMediator,
    uow: fakes.FakeUoW,
    payment_repository: fakes.FakePaymentRepository,
    outbox_repository: fakes.FakeOutboxRepository,
    create_payment_command: models.CreatePayment,
):
    # Arrange
    async def create_with_error(**kwargs):
        raise RuntimeError("db is unavailable")

    monkeypatch.setattr(payment_repository, "create", create_with_error)

    # Act
    with pytest.raises(RuntimeError, match="db is unavailable"):
        await request_mediator.send(create_payment_command)

    # Assert
    assert uow.rolled_back
    assert not uow.committed
    assert outbox_repository.events == []


async def test_create_payment_duplicate_idempotency_key_negative(
    request_mediator: cqrs.RequestMediator,
    uow: fakes.FakeUoW,
    outbox_repository: fakes.FakeOutboxRepository,
    payment_factory: typing.Callable[..., entities.Payment],
    create_payment_command: models.CreatePayment,
):
    # Arrange
    payment_factory(idempotency_key=create_payment_command.idempotency_key)

    # Act
    with pytest.raises(exceptions.PaymentAlreadyExists):
        await request_mediator.send(create_payment_command)

    # Assert
    assert uow.rolled_back
    assert not uow.committed
    assert outbox_repository.events == []
