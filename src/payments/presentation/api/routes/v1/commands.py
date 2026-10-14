import typing

import cqrs
import fastapi
from fastapi import status

from payments.presentation.api import models, dependencies
from payments.service import models as service_models

router = fastapi.APIRouter(
    prefix="/payments",
    tags=["Управление платежами"]
)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_payment(
    body: models.PaymentCreate,
    idempotency_key: typing.Annotated[str, fastapi.Header(alias="Idempotency-Key")],
    mediator: cqrs.RequestMediator = fastapi.Depends(dependencies.request_mediator_factory),
) -> models.Response[service_models.PaymentCreated]:
    """## Создание платежа"""
    command = service_models.CreatePayment(
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        meta=body.meta,
        webhook_url=body.webhook_url,
        idempotency_key=idempotency_key,
    )
    result = await mediator.send(command)
    return models.Response[service_models.PaymentCreated](result=result)

