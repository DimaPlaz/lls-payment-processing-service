import fastapi
import idempotency_header_middleware as idempotency
from idempotency_header_middleware import backends

from payments.settings import app as app_settings
from payments.presentation.api import routes, dependencies, error_handlers
from payments.presentation.api.settings import api as api_settings


app = fastapi.FastAPI(
    debug=app_settings.debug,
    title=app_settings.name,
    description="API for Payments",
    dependencies=[fastapi.Depends(dependencies.verify_api_key)],
)
error_handlers.register_exception_handlers(app)
app.include_router(routes.api_router)

if api_settings.idempotency_require:
    app.add_middleware(
        idempotency.IdempotencyHeaderMiddleware,  # pyright: ignore [reportArgumentType] -- в библиотеке __call__ аннотирован как возвращающий JSONResponse
        backend=backends.MemoryBackend(),
        applicable_methods=api_settings.idempotency_methods,
    )
