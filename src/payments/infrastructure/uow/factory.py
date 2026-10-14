import cqrs

from payments.infrastructure import database, repositories
from payments.infrastructure.uow import uow


class SqlAlchemyUoWFactory:
    async def __call__(self):
        session = database.async_sessionmaker()
        payment_repository = repositories.SqlAlchemyPaymentRepository(session)
        outbox_repository = cqrs.SqlAlchemyOutboxedEventRepository(session)
        return uow.SqlAlchemyUoW(
            session=session,
            payment_repository=payment_repository,
            outbox_repository=outbox_repository,
        )
