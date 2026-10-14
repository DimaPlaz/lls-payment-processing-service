import decimal
import typing

import pydantic

from payments.domain import enums


T = typing.TypeVar("T")


class Response(pydantic.BaseModel, typing.Generic[T]):
    result: T


class PaymentCreate(pydantic.BaseModel):
    amount: decimal.Decimal = pydantic.Field(gt=0, max_digits=12, decimal_places=2, description="Сумма")
    currency: enums.Currency = pydantic.Field(description="Валюта")
    description: str = pydantic.Field(max_length=255, description="Описание")
    meta: dict[str, typing.Any] = pydantic.Field(
        default_factory=dict,
        description="Дополнительная информация",
    )
    webhook_url: pydantic.HttpUrl = pydantic.Field(description="URL для уведомления о результате")
