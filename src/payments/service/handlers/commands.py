import cqrs

from payments.service import interfaces, models


class CreatePaymentHandler(cqrs.RequestHandler[models.CreatePayment, models.PaymentCreated]):
    def __init__(self, uow: interfaces.IUoW):
        self._uow = uow

    async def handle(self, request: models.CreatePayment) -> models.PaymentCreated:
        async with self._uow.transaction() as uow:
            payment = await uow.payment_repository.create(
                amount=request.amount,
                currency=request.currency,
                description=request.description,
                meta=request.meta,
                idempotency_key=request.idempotency_key,
                webhook_url=request.webhook_url,
            )
            uow.outbox_repository.add(models.CustomNotificationEvent[models.PaymentCreatedPayload](
                event_name="payment_created_notification",
                topic="payments.new",
                payload=models.PaymentCreatedPayload(id=payment.id, amount=payment.amount),
            ))

        return models.PaymentCreated(
            payment_id=payment.id,
            status=payment.status,
            created_at=payment.created_at,
        )
