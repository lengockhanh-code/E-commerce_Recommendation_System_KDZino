"""Admin Management & Analytics Endpoints"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.src.database.connection import get_db
from backend.src.models.schemas import AdminStatsResponse, OrderResponse
from backend.src.observability.metrics import get_admin_metrics
from backend.src.services.order_service import get_user_orders

router = APIRouter(prefix="/admin", tags=["Admin Analytics & Management"])


@router.get("/stats", response_model=AdminStatsResponse)
def admin_stats(db: Session = Depends(get_db)):
    """Lấy thống kê tổng quan doanh thu, đơn hàng, sản phẩm cho Dashboard Quản Trị"""
    return get_admin_metrics(db)
