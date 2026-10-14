from unittest import mock

import pytest

from payments.infrastructure.message_broker import topology


class TestQueues:
    def test_payments_queue_dead_letters_to_dlq_positive(self):
        # Arrange
        # Act
        arguments = topology.payments.arguments

        # Assert
        expected = {
            "x-dead-letter-exchange": topology.dead_letter_exchange.name,
            "x-dead-letter-routing-key": topology.dlq.routing(),
        }
        assert expected.items() <= (arguments or {}).items()

    @pytest.mark.parametrize(
        ("retry_queue", "delay_ms"),
        list(zip(topology.retry_queues, (3000, 6000, 12000), strict=True)),
        ids=lambda value: getattr(value, "name", str(value)),
    )
    def test_retry_queue_returns_to_payments_queue_positive(self, retry_queue, delay_ms: int):
        # Arrange
        # Act
        arguments = retry_queue.arguments

        # Assert
        expected = {
            "x-message-ttl": delay_ms,
            "x-dead-letter-exchange": topology.payments_exchange.name,
            "x-dead-letter-routing-key": topology.payments.routing(),
        }
        assert expected.items() <= (arguments or {}).items()


class TestDeclare:
    async def test_declare_binds_all_queues_positive(self):
        # Arrange
        broker = mock.AsyncMock()
        declared_queues = {}

        async def declare_queue(queue):
            declared_queues[queue.name] = mock.AsyncMock()
            return declared_queues[queue.name]

        broker.declare_exchange.side_effect = lambda exchange: exchange.name
        broker.declare_queue.side_effect = declare_queue

        # Act
        await topology.declare(broker)

        # Assert
        for exchange, queue in topology.bindings:
            declared_queues[queue.name].bind.assert_awaited_once_with(exchange.name, routing_key=queue.routing())
        assert set(declared_queues) == {
            topology.payments.name,
            topology.dlq.name,
            *(queue.name for queue in topology.retry_queues),
        }
