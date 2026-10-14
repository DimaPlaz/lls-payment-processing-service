import functools

from cqrs.bootstrap import events

from payments.service import mapping
from payments.presentation import di


@functools.lru_cache
def event_mediator_factory():
    return events.bootstrap(
        di_container=di.container,
        events_mapper=mapping.init_events,
    )
