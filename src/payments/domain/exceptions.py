class DomainException(Exception):
    """Базовое доменное исключение"""

    def __init__(self, message: str):
        self.message = message


class InvalidPaymentStateError(DomainException):
    """Недопустимый переход состояния платежа."""
