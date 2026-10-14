import logging

import cqrs
import faststream
from faststream import rabbit

from payments import settings
from payments.infrastructure import message_broker
from payments.infrastructure.message_broker import topology
from payments.presentation.consumer import dependencies
from payments.service.models import events


logger = logging.getLogger(__name__)
broker = message_broker.rabbit_broker_factory()
app = faststream.FastStream(broker)


@app.on_startup
def setup_logging():
    settings.configure_logging()


@app.after_startup
async def setup_infrastructure():
    await topology.declare(broker)


@broker.subscriber(topology.payments, topology.payments_exchange)
async def handle_payment(
    msg: rabbit.RabbitMessage,
    body: events.RabbitMsg[events.CustomNotificationEvent[events.PaymentCreatedPayload]],
    mediator: cqrs.EventMediator = faststream.Depends(dependency=dependencies.event_mediator_factory),
):
    await mediator.send(body.payload)
    await msg.ack()
