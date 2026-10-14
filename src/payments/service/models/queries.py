import cqrs


class GetPayment(cqrs.PydanticRequest):
    payment_id: int
