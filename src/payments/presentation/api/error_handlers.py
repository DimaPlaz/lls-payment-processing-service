import fastapi
from fastapi import responses

from payments.service import exceptions as services_exceptions
from payments.domain import exceptions as domains_exceptions


def register_exception_handlers(app: fastapi.FastAPI) -> None:
    @app.exception_handler(services_exceptions.NotFound)
    async def payment_not_found_handler(request: fastapi.Request, exc: services_exceptions.NotFound):
        return responses.JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )
    @app.exception_handler(services_exceptions.AlreadyExists)
    async def already_exists_handler(request: fastapi.Request, exc: services_exceptions.AlreadyExists):
        return responses.JSONResponse(status_code=409, content={"detail": str(exc)})
    @app.exception_handler(domains_exceptions.DomainException)
    async def domain_error_handler(request: fastapi.Request, exc: domains_exceptions.DomainException):
        return responses.JSONResponse(status_code=400, content={"detail": str(exc)})