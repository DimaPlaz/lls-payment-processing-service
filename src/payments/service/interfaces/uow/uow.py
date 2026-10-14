import abc
import contextlib
import typing

import cqrs

from payments.service import interfaces


class IUoW(abc.ABC):
    payment_repository: interfaces.IPaymentRepository
    outbox_repository: cqrs.OutboxedEventRepository

    @abc.abstractmethod
    def transaction(self) -> contextlib.AbstractAsyncContextManager[typing.Self]:
        raise NotImplementedError
