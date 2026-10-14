import contextlib
import datetime
import decimal
import typing

import cqrs
import pydantic
from cqrs.outbox import repository as outbox_repository

from payments.domain import entities, enums
from payments.service import exceptions, interfaces


class FakePaymentRepository(interfaces.IPaymentRepository):
    """In-memory репозиторий платежей"""

    def __init__(self) -> None:
        self.storage: dict[int, entities.Payment] = {}
        self.commits = 0
        self._next_id = 1

    def add(self, payment: entities.Payment) -> entities.Payment:
        """Положить готовый платёж в хранилище (для подготовки данных в тестах)"""
        self.storage[payment.id] = payment
        self._next_id = max(self._next_id, payment.id + 1)
        return payment

    async def get(self, payment_id: int) -> entities.Payment | None:
        payment = self.storage.get(payment_id)
        # Копия, чтобы мутации сущности в хендлере не попадали в хранилище без update
        return payment and payment.model_copy()

    async def create(
        self,
        amount: decimal.Decimal,
        currency: enums.Currency,
        description: str,
        meta: dict,
        idempotency_key: str,
        webhook_url: pydantic.HttpUrl,
    ) -> entities.Payment:
        # Аналог unique-констрейнта на idempotency_key
        if any(payment.idempotency_key == idempotency_key for payment in self.storage.values()):
            raise exceptions.PaymentAlreadyExists(f"Payment with idempotency key {idempotency_key} already exists")
        payment = entities.Payment(
            id=self._next_id,
            amount=amount,
            currency=currency,
            description=description,
            meta=meta,
            idempotency_key=idempotency_key,
            webhook_url=webhook_url,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        return self.add(payment).model_copy()

    async def update(self, payment: entities.Payment) -> bool:
        # Аналог условия WHERE status = 'PENDING'
        if self.storage[payment.id].status != enums.PaymentStatus.PENDING:
            return False
        self.storage[payment.id] = payment.model_copy()
        return True

    async def commit(self):
        self.commits += 1


class FakeOutboxRepository(cqrs.OutboxedEventRepository):
    """In-memory outbox: просто копит добавленные события"""

    def __init__(self) -> None:
        self.events: list[cqrs.INotificationEvent] = []

    def add(self, event: cqrs.INotificationEvent) -> None:
        self.events.append(event)

    async def get_many(
        self,
        batch_size: int = 100,
        topic: str | None = None,
    ) -> list[outbox_repository.OutboxedEvent]:
        return []

    async def update_status(self, outboxed_event_id: int, new_status: outbox_repository.EventStatus):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class FakeUoW(interfaces.IUoW):
    def __init__(
        self,
        payment_repository: FakePaymentRepository,
        outbox_repository: FakeOutboxRepository,
    ) -> None:
        self.payment_repository = payment_repository
        self.outbox_repository = outbox_repository
        self.committed = False
        self.rolled_back = False

    @contextlib.asynccontextmanager
    async def transaction(self) -> typing.AsyncIterator[typing.Self]:
        try:
            yield self
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise


class FakeWebhookClient(interfaces.IWebhookClient):
    """Запоминает все вызовы notify вместо реальных http-запросов"""

    def __init__(self) -> None:
        self.calls: list[dict[str, typing.Any]] = []

    async def notify(self, url: str, idempotency_key: str, data: dict | None = None) -> None:
        self.calls.append({"url": url, "idempotency_key": idempotency_key, "data": data})


def payment_repository_factory(repository: FakePaymentRepository) -> interfaces.PaymentRepositoryFactory:
    @contextlib.asynccontextmanager
    async def factory() -> typing.AsyncIterator[interfaces.IPaymentRepository]:
        yield repository

    return factory
