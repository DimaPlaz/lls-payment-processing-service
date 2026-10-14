import typing

import cqrs
import pytest

from payments.domain import entities
from payments.service import exceptions, models


async def test_get_payment_positive(
    request_mediator: cqrs.RequestMediator,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    payment = payment_factory()

    # Act
    result = await request_mediator.send(models.GetPayment(payment_id=payment.id))

    # Assert
    assert isinstance(result, models.Payment)
    assert result.model_dump() == payment.model_dump()


async def test_get_payment_not_found_negative(
    request_mediator: cqrs.RequestMediator,
    payment_factory: typing.Callable[..., entities.Payment],
):
    # Arrange
    payment = payment_factory()
    missing_payment_id = payment.id + 1

    # Act
    # Assert
    with pytest.raises(exceptions.PaymentNotFound):
        await request_mediator.send(models.GetPayment(payment_id=missing_payment_id))
