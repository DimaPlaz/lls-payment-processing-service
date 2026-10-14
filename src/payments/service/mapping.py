import cqrs

from payments.service.handlers import commands as command_handlers
from payments.service.handlers import queries as query_handlers
from payments.service.handlers import events as event_handlers
from payments.service import models


def init_commands(mapper: cqrs.RequestMap):
    mapper.bind(models.CreatePayment, command_handlers.CreatePaymentHandler)


def init_queries(mapper: cqrs.RequestMap):
    mapper.bind(models.GetPayment, query_handlers.GetPaymentHandler)


def init_events(mapper: cqrs.EventMap):
    mapper.bind(models.CustomNotificationEvent[models.PaymentCreatedPayload], event_handlers.ProcessPaymentHandler)
