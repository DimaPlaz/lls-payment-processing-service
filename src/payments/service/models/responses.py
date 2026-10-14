import datetime

import cqrs

from payments.domain import enums, entities


class PaymentCreated(cqrs.PydanticResponse):
    payment_id: int
    status: enums.PaymentStatus
    created_at: datetime.datetime


class Payment(cqrs.PydanticResponse, entities.Payment):
    pass
