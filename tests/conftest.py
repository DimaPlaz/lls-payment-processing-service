import datetime
import types
import typing

import cqrs
import di
import fastapi
import faker as faker_lib
import httpx
import pytest
from faststream import rabbit

from payments.domain import entities, enums
from payments.presentation.api import dependencies as api_dependencies
from payments.presentation.api import main as api_main
from payments.presentation.api.settings import api as api_settings
from payments.presentation.consumer import dependencies as consumer_dependencies
from payments.presentation.consumer import main as consumer_main
from payments.service.handlers import events as event_handlers
from tests.mock import fakes, mock_dependencies


@pytest.fixture
def payment_repository() -> fakes.FakePaymentRepository:
    return fakes.FakePaymentRepository()


@pytest.fixture
def outbox_repository() -> fakes.FakeOutboxRepository:
    return fakes.FakeOutboxRepository()


@pytest.fixture
def uow(
    payment_repository: fakes.FakePaymentRepository,
    outbox_repository: fakes.FakeOutboxRepository,
) -> fakes.FakeUoW:
    return fakes.FakeUoW(payment_repository=payment_repository, outbox_repository=outbox_repository)


@pytest.fixture
def webhook_client() -> fakes.FakeWebhookClient:
    return fakes.FakeWebhookClient()


@pytest.fixture
def payment_factory(
    faker: faker_lib.Faker,
    payment_repository: fakes.FakePaymentRepository,
) -> typing.Callable[..., entities.Payment]:
    """Создаёт платёж со случайными данными и кладёт его в payment_repository.
    Любое поле можно переопределить через kwargs"""

    def factory(**overrides: typing.Any) -> entities.Payment:
        fields = {
            "id": faker.unique.pyint(min_value=1, max_value=1_000_000),
            "amount": faker.pydecimal(left_digits=6, right_digits=2, min_value=1),
            "currency": faker.enum(enums.Currency),
            "description": faker.sentence(),
            "meta": {"order_id": faker.uuid4()},
            "status": enums.PaymentStatus.PENDING,
            "idempotency_key": faker.uuid4(),
            "webhook_url": faker.url(),
            "created_at": datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1),
            "processed_at": None,
        }
        return payment_repository.add(entities.Payment(**(fields | overrides)))

    return factory


@pytest.fixture(autouse=True)
def payment_processing(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """Детерминированная обработка платежа в ProcessPaymentHandler: без задержки и всегда успешно.

    Чтобы платёж завершился неуспешно: `payment_processing.random = lambda: 0.0`
    """
    stub = types.SimpleNamespace(randint=lambda a, b: 0, random=lambda: 1.0)
    monkeypatch.setattr(event_handlers, "random", stub)
    return stub


@pytest.fixture
def di_container(
    uow: fakes.FakeUoW,
    webhook_client: fakes.FakeWebhookClient,
    payment_repository: fakes.FakePaymentRepository,
) -> di.Container:
    return mock_dependencies.container_factory(
        uow=uow,
        webhook_client=webhook_client,
        payment_repository=payment_repository,
    )


@pytest.fixture
def request_mediator(di_container: di.Container) -> cqrs.RequestMediator:
    return mock_dependencies.request_mediator_factory(di_container)


@pytest.fixture
def event_mediator(di_container: di.Container) -> cqrs.EventMediator:
    return mock_dependencies.event_mediator_factory(di_container)


@pytest.fixture
def api_app(request_mediator: cqrs.RequestMediator) -> typing.Iterator[fastapi.FastAPI]:
    app = api_main.app
    app.dependency_overrides[api_dependencies.request_mediator_factory] = lambda: request_mediator
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def api_client(api_app: fastapi.FastAPI) -> typing.AsyncIterator[httpx.AsyncClient]:
    """Асинхронный http клиент для api версии v1 (с валидным api-ключом)"""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app),
        base_url="http://test-api/api/v1",
        headers={api_settings.auth_key_name: api_settings.auth_key},
    ) as client:
        yield client


@pytest.fixture
async def rabbit_broker(event_mediator: cqrs.EventMediator) -> typing.AsyncIterator[rabbit.RabbitBroker]:
    """Брокер консьюмера в тестовом режиме (без реального RabbitMQ) с fake медиатором"""
    broker = consumer_main.broker
    with broker.provider.scope(consumer_dependencies.event_mediator_factory, lambda: event_mediator):
        async with rabbit.TestRabbitBroker(broker) as test_broker:
            yield test_broker
