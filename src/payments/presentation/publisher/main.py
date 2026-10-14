import asyncio

import cqrs

from payments import settings as app_settings
from payments.infrastructure import message_broker, settings, database
from payments.infrastructure.message_broker import topology
from payments.service import models  # noqa: F401 -- регистрирует события outbox


async def outbox_producer():
    broker = message_broker.rabbit_broker_factory()
    async with database.async_sessionmaker() as session:
        producer = cqrs.EventProducer(
            message_broker=message_broker.RabbitMessageBroker(
                broker=broker,
                exchange=topology.payments_exchange,
                durable=settings.rabbitmq.durable,
            ),
            repository=cqrs.SqlAlchemyOutboxedEventRepository(
                session=session,
            ),
        )
        await broker.start()
        await topology.declare(broker)
        async for messages in producer.event_batch_generator():
            for message in messages:
                await producer.send_message(message)
            await producer.repository.commit()
            await asyncio.sleep(10)

if __name__ == "__main__":
    app_settings.configure_logging()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(outbox_producer())
