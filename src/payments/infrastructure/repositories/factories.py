import contextlib

from payments.infrastructure import repositories
from payments.infrastructure.database import base


class PaymentRepositoryFactory:
    def __init__(self, session_factory: base.SessionFactory) -> None:
        self._session_factory = session_factory

    @contextlib.asynccontextmanager
    async def __call__(self):
        async with self._session_factory() as session:
            yield repositories.SqlAlchemyPaymentRepository(session)