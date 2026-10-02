"""Orders API Router"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.schemas import OrderCreate, OrderOut
from app.services.auth_service import get_current_user
from app.services.order_service import create_order_service, get_user_orders, get_order_by_id

router = APIRouter(prefix="/orders", tags=["Orders & Checkout"])


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order_route(
    data: OrderCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Tạo đơn hàng mới"""
    user_id = current_user.id if current_user else None
    return create_order_service(db=db, order_data=data, user_id=user_id)


@router.get("", response_model=List[OrderOut])
def list_user_orders_route(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách đơn hàng của người dùng đang đăng nhập"""
    if not current_user:
        return []
    return get_user_orders(db=db, user_id=current_user.id)


@router.get("/{id}", response_model=OrderOut)
def get_order_detail_route(
    id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy thông tin chi tiết một đơn hàng theo ID"""
    user_id = current_user.id if current_user else None
    order = get_order_by_id(db=db, order_id=id, user_id=user_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn hàng"
        )
    return order
