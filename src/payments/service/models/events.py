import decimal
import typing
import uuid

import cqrs
import pydantic
from pydantic import alias_generators


T = typing.TypeVar("T")
E = typing.TypeVar("E")


class BaseEvent(pydantic.BaseModel, frozen=True):
    model_config = pydantic.ConfigDict(
        alias_generator=alias_generators.to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class RabbitMsg(BaseEvent, typing.Generic[T], frozen=True):
    message_id: uuid.UUID
    message_name: str
    topic: str
    payload: T


class CustomNotificationEvent(cqrs.PydanticNotificationEvent[E], BaseEvent, frozen=True):
    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


class PaymentCreatedPayload(BaseEvent, frozen=True):
    payment_id: int = pydantic.Field(alias="id")
    amount: decimal.Decimal


cqrs.OutboxedEventMap.register("payment_created_notification", CustomNotificationEvent[PaymentCreatedPayload])
