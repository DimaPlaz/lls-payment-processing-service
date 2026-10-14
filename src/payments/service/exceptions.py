class NotFound(Exception):
    pass

class PaymentNotFound(NotFound):
    pass

class AlreadyExists(Exception):
    pass

class PaymentAlreadyExists(AlreadyExists):
    pass
