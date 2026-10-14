import fastapi

from payments.presentation.api.routes import v1

api_router = fastapi.APIRouter(prefix="/api")
api_router.include_router(v1.queries_v1_router)
api_router.include_router(v1.commands_v1_router)
