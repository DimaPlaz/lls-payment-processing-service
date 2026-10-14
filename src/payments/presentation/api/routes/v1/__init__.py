import fastapi

from payments.presentation.api.routes.v1 import commands, queries

queries_v1_router = fastapi.APIRouter(prefix="/v1")
queries_v1_router.include_router(queries.router)

commands_v1_router = fastapi.APIRouter(prefix="/v1")
commands_v1_router.include_router(commands.router)
