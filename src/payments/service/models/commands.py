import decimal
import typing

import cqrs
import pydantic

from payments.domain import enums


class CreatePayment(cqrs.PydanticRequest):
    amount: decimal.Decimal
    currency: enums.Currency
    description: str
    meta: dict[str, typing.Any]
    webhook_url: pydantic.HttpUrl
    idempotency_key: str
