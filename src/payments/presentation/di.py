import di
from di import dependent

from payments.infrastructure import webhook, repositories
from payments.infrastructure.uow import factory as uow_factory
from payments.service import interfaces

container = di.Container()


UoWBind = di.bind_by_type(
    dependent.Dependent(uow_factory.SqlAlchemyUoWFactory(), scope="request"),
    interfaces.IUoW,
)
WebhookClientBind = di.bind_by_type(
    dependent.Dependent(webhook.HTTPXWebhookClient, scope="request"),
    interfaces.IWebhookClient,
)
PaymentRepositoryBind = di.bind_by_type(
    dependent.Dependent(repositories.PaymentRepositoryFactory, scope="request"),
    interfaces.PaymentRepositoryFactory,
)

container.bind(UoWBind)
container.bind(WebhookClientBind)
container.bind(PaymentRepositoryBind)
