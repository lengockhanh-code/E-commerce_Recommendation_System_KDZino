"""Services module initialization"""
from backend.src.services.auth_service import (
    register_local_user, login_local_user, authenticate_google_user,
    handle_google_callback
)
from backend.src.services.product_service import (
    get_products, get_product_by_id, get_categories_and_brands
)
from backend.src.services.recommendation_service import get_recommendations
from backend.src.services.order_service import create_order, get_user_orders, get_order_by_id
from backend.src.services.event_service import log_user_event

__all__ = [
    "register_local_user", "login_local_user", "authenticate_google_user",
    "handle_google_callback",
    "get_products", "get_product_by_id", "get_categories_and_brands",
    "get_recommendations", "create_order", "get_user_orders", "get_order_by_id",
    "log_user_event"
]
