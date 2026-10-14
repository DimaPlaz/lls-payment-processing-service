import cqrs

from payments.service import interfaces, models, exceptions


class GetPaymentHandler(cqrs.RequestHandler[models.GetPayment, models.Payment]):
    def __init__(self, payment_repository_factory: interfaces.PaymentRepositoryFactory):
        self._payment_repository_factory = payment_repository_factory

    async def handle(self, request: models.GetPayment) -> models.Payment:
        async with self._payment_repository_factory() as payment_repository:
            payment = await payment_repository.get(payment_id=request.payment_id)
            if not payment:
                raise exceptions.PaymentNotFound(f"Payment {request.payment_id} not found")
            return models.Payment.model_validate(payment, from_attributes=True)
