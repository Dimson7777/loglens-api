from fastapi import APIRouter

from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.error_groups import router as error_groups_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.logs import router as logs_router
from app.api.routes.system import router as system_router
from app.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(auth_router, prefix="/api/v1")
api_router.include_router(logs_router, prefix="/api/v1")
api_router.include_router(error_groups_router, prefix="/api/v1")
api_router.include_router(jobs_router, prefix="/api/v1")
api_router.include_router(users_router, prefix="/api/v1")
api_router.include_router(analytics_router, prefix="/api/v1")
