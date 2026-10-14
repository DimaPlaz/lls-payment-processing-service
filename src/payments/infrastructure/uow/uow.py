import asyncio
import contextlib
import typing

import cqrs
from sqlalchemy.ext.asyncio import AsyncSession

from payments.service import interfaces


class SqlAlchemyUoW(interfaces.IUoW):
    def __init__(
        self,
        session: AsyncSession,
        payment_repository: interfaces.IPaymentRepository,
        outbox_repository: cqrs.OutboxedEventRepository,
    ):
        self._session = session
        self.outbox_repository = outbox_repository
        self.payment_repository = payment_repository

    @contextlib.asynccontextmanager
    async def transaction(self) -> typing.AsyncGenerator[typing.Self, typing.Any]:
        try:
            await self._session.begin()
            yield self
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        finally:
            await asyncio.shield(self._session.close())
