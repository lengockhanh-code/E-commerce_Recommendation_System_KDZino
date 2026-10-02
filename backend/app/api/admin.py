"""Admin Dashboard & Management API Router"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.model.database import get_db
from app.model.models import Order, Product, User
from app.model.schemas import AdminDashboardStats, OrderOut, OrderStatusUpdate, ProductOut, UserOut
from app.services.product_service import format_product_dict

router = APIRouter(prefix="/admin", tags=["Admin Management & Dashboard"])


@router.get("/stats", response_model=AdminDashboardStats)
def get_admin_dashboard_stats(db: Session = Depends(get_db)):
    """Lấy thống kê tổng quan cho trang quản trị Admin: Doanh thu, Đơn hàng, Sản phẩm, Người dùng"""
    total_rev = db.query(func.sum(Order.total_amount)).scalar() or 0.0
    total_orders = db.query(Order).count()
    total_products = db.query(Product).filter(Product.is_active == True).count()
    total_users = db.query(User).count()

    # Recent sales for analytics chart
    recent_orders = db.query(Order).order_by(desc(Order.created_at)).limit(7).all()
    chart_data = [
        {
            "id": o.id,
            "date": o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
            "amount": o.total_amount,
            "status": o.status
        }
        for o in recent_orders
    ]

    return {
        "total_revenue": total_rev,
        "total_orders": total_orders,
        "total_products": total_products,
        "total_users": total_users,
        "recent_sales": chart_data
    }


@router.get("/orders", response_model=List[OrderOut])
def list_admin_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lấy danh sách tất cả đơn hàng cho trang Admin"""
    query = db.query(Order)
    if status_filter:
        query = query.filter(Order.status == status_filter)

    query = query.order_by(desc(Order.created_at))
    offset = (page - 1) * limit
    return query.offset(offset).limit(limit).all()


@router.put("/orders/{id}/status", response_model=OrderOut)
def update_order_status_route(
    id: str,
    data: OrderStatusUpdate,
    db: Session = Depends(get_db)
):
    """Cập nhật trạng thái đơn hàng (pending, confirmed, shipping, completed, cancelled)"""
    order = db.query(Order).filter(Order.id == id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn hàng"
        )
    order.status = data.status
    db.commit()
    db.refresh(order)
    return order


@router.get("/products", response_model=List[ProductOut])
def list_admin_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Lấy danh sách sản phẩm quản trị"""
    products = db.query(Product).order_by(desc(Product.created_at)).offset((page - 1) * limit).limit(limit).all()
    return [format_product_dict(p) for p in products]


@router.put("/products/{id}/status")
def toggle_product_status_route(
    id: str,
    is_active: bool = Query(..., description="Trạng thái hoạt động"),
    db: Session = Depends(get_db)
):
    """Bật/Tắt trạng thái kinh doanh của sản phẩm"""
    p = db.query(Product).filter(Product.item_id == id).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm"
        )
    p.is_active = is_active
    db.commit()
    return {"status": "updated", "item_id": id, "is_active": is_active}


@router.get("/users", response_model=List[UserOut])
def list_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Lấy danh sách tất cả tài khoản người dùng"""
    return db.query(User).order_by(desc(User.created_at)).offset((page - 1) * limit).limit(limit).all()
