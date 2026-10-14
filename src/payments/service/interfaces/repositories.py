import abc
import contextlib
import decimal
import typing

import pydantic

from payments.domain import entities, enums


class IPaymentRepository(abc.ABC):
    @abc.abstractmethod
    async def get(self, payment_id: int) -> entities.Payment | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def create(
        self,
        amount: decimal.Decimal,
        currency: enums.Currency,
        description: str,
        meta: dict,
        idempotency_key: str,
        webhook_url: pydantic.HttpUrl,
    ) -> entities.Payment:
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, payment: entities.Payment) -> bool:
        """Финализирует платёж в статусе PENDING. Возвращает False, если платёж уже был финализирован"""
        raise NotImplementedError

    @abc.abstractmethod
    async def commit(self):
        raise NotImplementedError


class PaymentRepositoryFactory(typing.Protocol):
    def __call__(self) -> contextlib.AbstractAsyncContextManager[IPaymentRepository]: ...
