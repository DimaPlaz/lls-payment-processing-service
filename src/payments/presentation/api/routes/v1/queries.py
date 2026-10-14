import cqrs
import fastapi
from fastapi import status

from payments.domain import entities
from payments.service import models as service_models
from payments.presentation.api import models, dependencies

router = fastapi.APIRouter(
    prefix="/payments",
    tags=["Управление платежами"]
)


@router.get("/{payment_id}", status_code=status.HTTP_200_OK)
async def get_payment(
    payment_id: int,
    mediator: cqrs.RequestMediator = fastapi.Depends(dependencies.request_mediator_factory),
) -> models.Response[entities.Payment]:
    """## Получение платежа"""
    query = service_models.GetPayment(payment_id=payment_id)
    result = await mediator.send(query)
    return models.Response[entities.Payment](result=result)

