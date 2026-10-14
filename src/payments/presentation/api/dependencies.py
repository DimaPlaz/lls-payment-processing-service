import functools
import secrets

import fastapi
from fastapi import security, status
from cqrs.bootstrap import requests

from payments.presentation.api import settings
from payments.service import mapping
from payments.presentation import di


@functools.lru_cache
def request_mediator_factory():
    return requests.bootstrap(
        di_container=di.container,
        commands_mapper=mapping.init_commands,
        queries_mapper=mapping.init_queries,
    )


async def verify_api_key(api_key: str = fastapi.Depends(security.APIKeyHeader(name=settings.api.auth_key_name))):
    if not secrets.compare_digest(api_key, settings.api.auth_key):
        raise fastapi.HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
