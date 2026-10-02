"""Main Router combining all API endpoints"""

from fastapi import APIRouter
from backend.src.api.auth import router as auth_router
from backend.src.api.products import router as products_router
from backend.src.api.recommendations import router as recs_router
from backend.src.api.orders import router as orders_router
from backend.src.api.events import router as events_router
from backend.src.api.profile import router as profile_router
from backend.src.api.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(products_router)
api_router.include_router(recs_router)
api_router.include_router(orders_router)
api_router.include_router(events_router)
api_router.include_router(profile_router)
api_router.include_router(admin_router)
