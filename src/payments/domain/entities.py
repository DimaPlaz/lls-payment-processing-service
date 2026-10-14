from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pydantic

from payments.domain import enums, exceptions


class Entity(pydantic.BaseModel):
    pass


class Payment(Entity):
    """Entity: Платёж. Идентичность определяется по id"""

    id: int = pydantic.Field(frozen=True)
    amount: Decimal = pydantic.Field(gt=0, max_digits=12, decimal_places=2, frozen=True)
    currency: enums.Currency = pydantic.Field(frozen=True)
    description: str = pydantic.Field(default="", max_length=500, frozen=True)
    meta: dict[str, Any] = pydantic.Field(default_factory=dict, frozen=True)
    status: enums.PaymentStatus = pydantic.Field(default=enums.PaymentStatus.PENDING)
    idempotency_key: str = pydantic.Field(min_length=1, max_length=255, frozen=True)
    webhook_url: pydantic.HttpUrl = pydantic.Field(frozen=True)
    created_at: datetime = pydantic.Field(frozen=True)
    processed_at: datetime | None = None

    model_config = pydantic.ConfigDict(validate_assignment=True)

    @pydantic.model_validator(mode="after")
    def _check_invariants(self) -> Payment:
        if self.status == enums.PaymentStatus.PENDING and self.processed_at is not None:
            raise ValueError("У платежа в статусе pending не может быть processed_at")
        if self.status != enums.PaymentStatus.PENDING and self.processed_at is None:
            raise ValueError("У обработанного платежа должен быть processed_at")
        if self.processed_at and self.processed_at < self.created_at:
            raise ValueError("processed_at не может быть раньше created_at")
        return self

    @property
    def is_final(self) -> bool:
        return self.status != enums.PaymentStatus.PENDING

    def mark_succeeded(self) -> None:
        self._finalize(enums.PaymentStatus.SUCCEEDED)

    def mark_failed(self) -> None:
        self._finalize(enums.PaymentStatus.FAILED)

    def _finalize(self, new_status: enums.PaymentStatus) -> None:
        if self.is_final:
            raise exceptions.InvalidPaymentStateError(
                f"Платёж {self.id} уже в финальном статусе {self.status}"
            )
        # Одним вызовом, чтобы не нарушить инвариант между присваиваниями
        self.__dict__.update(status=new_status, processed_at=datetime.now(UTC))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Payment):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
