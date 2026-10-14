import datetime
import decimal
from decimal import Decimal
from typing import Any

import sqlalchemy
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import JSONB

from payments.domain import enums
from payments.infrastructure.database import base


class Payment(base.Base):
    __tablename__ = "payments"

    id: orm.Mapped[int] = orm.mapped_column(sqlalchemy.Identity(always=True), primary_key=True)
    amount: orm.Mapped[Decimal] = orm.mapped_column(sqlalchemy.Numeric(12, 2), nullable=False)
    currency: orm.Mapped[enums.Currency] = orm.mapped_column(sqlalchemy.Enum(enums.Currency), nullable=False)
    description: orm.Mapped[str] = orm.mapped_column(sqlalchemy.Text, nullable=False)
    meta: orm.Mapped[dict[str, Any]] = orm.mapped_column(JSONB, nullable=False)
    status: orm.Mapped[enums.PaymentStatus] = orm.mapped_column(
        sqlalchemy.Enum(enums.PaymentStatus),
        nullable=False,
        default=str(enums.PaymentStatus.PENDING),
        server_default=str(enums.PaymentStatus.PENDING),
    )
    idempotency_key: orm.Mapped[str] = orm.mapped_column(sqlalchemy.String(255), unique=True, nullable=False)
    webhook_url: orm.Mapped[str] = orm.mapped_column(sqlalchemy.String(2048), nullable=False)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        sqlalchemy.DateTime(timezone=True),
        nullable=False,
        server_default=sqlalchemy.func.now(),
    )
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        sqlalchemy.DateTime(timezone=True),
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )
    processed_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
        sqlalchemy.DateTime(timezone=True),
        nullable=True,
    )

    @classmethod
    def get_payment_stmt(cls, payment_id: int) -> sqlalchemy.Select:
        return sqlalchemy.select(cls).where(cls.id == payment_id)

    @classmethod
    def create_payment_stmt(
        cls,
        amount: decimal.Decimal,
        currency: enums.Currency,
        description: str,
        meta: dict,
        idempotency_key: str,
        webhook_url: str,
    ) -> sqlalchemy.Insert:
        return (
            sqlalchemy.insert(cls)
            .values(
                amount=amount,
                currency=currency,
                description=description,
                meta=meta,
                idempotency_key=idempotency_key,
                webhook_url=webhook_url,
            )
            .returning(cls)
        )

    @classmethod
    def update_payment_stmt(
        cls,
        payment_id: int,
        status: enums.PaymentStatus,
        processed_at: datetime.datetime | None,
    ) -> sqlalchemy.Update:
        return (
            sqlalchemy.update(cls)
            .where(cls.id == payment_id, cls.status == enums.PaymentStatus.PENDING)
            .values(
                status=status,
                processed_at=processed_at,
            )
        )
