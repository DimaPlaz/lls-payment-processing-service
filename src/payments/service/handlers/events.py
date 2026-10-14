import asyncio
import random

import cqrs

from payments.domain import enums
from payments.service import interfaces, exceptions
from payments.service.models import events


class ProcessPaymentHandler(cqrs.EventHandler[events.CustomNotificationEvent[events.PaymentCreatedPayload]]):
    def __init__(
        self,
        payment_repository_factory: interfaces.PaymentRepositoryFactory,
        webhook_client: interfaces.IWebhookClient,
    ):
        self._webhook_client = webhook_client
        self._payment_repository_factory = payment_repository_factory

    async def handle(self, event: events.CustomNotificationEvent[events.PaymentCreatedPayload]) -> None:
        # Статус платежа фиксируется до отправки webhook: при повторной доставке сообщения
        # (retry после ошибки webhook или дубль) обработка не повторяется, отправляется только webhook
        async with self._payment_repository_factory() as payment_repository:
            payment = await payment_repository.get(event.payload.payment_id)
            if not payment:
                raise exceptions.PaymentNotFound(f"Payment {event.payload.payment_id} not found")

            if not payment.is_final:
                await asyncio.sleep(random.randint(2, 5))  # обработка платежа 2-5 сек
                if random.random() < 0.1:
                    payment.mark_failed()
                else:
                    payment.mark_succeeded()

                finalized = await payment_repository.update(payment)
                await payment_repository.commit()
                if not finalized:
                    # Параллельный consumer финализировал платёж раньше — уведомляем о его результате
                    payment = await payment_repository.get(payment.id)
                    if not payment:
                        raise exceptions.PaymentNotFound(f"Payment {event.payload.payment_id} not found")

        await self._webhook_client.notify(
            url=str(payment.webhook_url),
            idempotency_key=payment.idempotency_key,
            data={"success": payment.status == enums.PaymentStatus.SUCCEEDED},
        )
