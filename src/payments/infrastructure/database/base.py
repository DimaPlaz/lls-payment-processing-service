import contextlib
import typing

import cqrs
import sqlalchemy.ext.asyncio as sa
from cqrs.outbox import sqlalchemy as outbox_sqlalchemy
from sqlalchemy import orm, pool

from payments.infrastructure import settings

Base = orm.registry().generate_base()
cqrs.rebind_outbox_model(outbox_sqlalchemy.OutboxModel, Base, table_name="outbox_payments")

engine = sa.create_async_engine(
    str(settings.db.dsn),
    isolation_level="REPEATABLE READ",
    poolclass=pool.AsyncAdaptedQueuePool,
    pool_size=settings.db.pool_size,
    pool_recycle=60 * 5,
    pool_pre_ping=True,
)
async_sessionmaker = sa.async_sessionmaker(engine)


class SessionFactory:
    @contextlib.asynccontextmanager
    async def __call__(self) -> typing.AsyncGenerator[sa.AsyncSession, typing.Any]:
        async with async_sessionmaker() as session:
            yield session
