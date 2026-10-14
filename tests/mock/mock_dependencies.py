import cqrs
import di
from cqrs.bootstrap import events, requests
from di import dependent

from payments.service import interfaces, mapping
from tests.mock import fakes


def container_factory(
    uow: fakes.FakeUoW,
    webhook_client: fakes.FakeWebhookClient,
    payment_repository: fakes.FakePaymentRepository,
) -> di.Container:
    """DI контейнер, аналогичный payments.presentation.di, но с fake-реализациями"""
    container = di.Container()
    container.bind(
        di.bind_by_type(dependent.Dependent(lambda: uow, scope="request"), interfaces.IUoW),
    )
    container.bind(
        di.bind_by_type(dependent.Dependent(lambda: webhook_client, scope="request"), interfaces.IWebhookClient),
    )
    container.bind(
        di.bind_by_type(
            dependent.Dependent(lambda: fakes.payment_repository_factory(payment_repository), scope="request"),
            interfaces.PaymentRepositoryFactory,
        ),
    )
    return container


def request_mediator_factory(container: di.Container) -> cqrs.RequestMediator:
    return requests.bootstrap(
        di_container=container,
        commands_mapper=mapping.init_commands,
        queries_mapper=mapping.init_queries,
    )


def event_mediator_factory(container: di.Container) -> cqrs.EventMediator:
    return events.bootstrap(
        di_container=container,
        events_mapper=mapping.init_events,
    )
