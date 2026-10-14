import decimal
import typing

import pydantic
import sqlalchemy
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncSession

from payments.domain import entities, enums
from payments.infrastructure.database import orm
from payments.service import exceptions, interfaces

# https://www.postgresql.org/docs/current/errcodes-appendix.html
UNIQUE_VIOLATION = "23505"


class SqlAlchemyPaymentRepository(interfaces.IPaymentRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, payment_id: int) -> entities.Payment | None:
        stmt = orm.Payment.get_payment_stmt(payment_id)
        payment_orm = await self._session.scalar(stmt)
        return payment_orm and entities.Payment.model_validate(payment_orm, from_attributes=True)

    async def create(
        self,
        amount: decimal.Decimal,
        currency: enums.Currency,
        description: str,
        meta: dict,
        idempotency_key: str,
        webhook_url: pydantic.HttpUrl,
    ) -> entities.Payment:
        stmt = orm.Payment.create_payment_stmt(
            amount=amount,
            currency=currency,
            description=description,
            meta=meta,
            idempotency_key=idempotency_key,
            webhook_url=str(webhook_url)
        )
        try:
            payment_orm = await self._session.scalar(stmt)
        except sa_exc.IntegrityError as error:
            # Единственное уникальное поле, заполняемое клиентом, — idempotency_key
            if getattr(error.orig, "sqlstate", None) == UNIQUE_VIOLATION:
                raise exceptions.PaymentAlreadyExists(
                    f"Payment with idempotency key {idempotency_key} already exists",
                ) from error
            raise
        return entities.Payment.model_validate(payment_orm, from_attributes=True)

    async def update(self, payment: entities.Payment) -> bool:
        stmt = orm.Payment.update_payment_stmt(
            payment_id=payment.id,
            status=payment.status,
            processed_at=payment.processed_at,
        )
        # Для UPDATE возвращается CursorResult, но AsyncSession.execute типизирован как Result
        result = typing.cast(sqlalchemy.CursorResult, await self._session.execute(stmt))
        return result.rowcount > 0

    async def commit(self):
        await self._session.commit()
