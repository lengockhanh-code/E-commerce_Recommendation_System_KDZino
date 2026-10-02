"""Order Management Service"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from app.model.models import Order, OrderItem
from app.model.schemas import OrderCreate


def create_order_service(
    db: Session,
    order_data: OrderCreate,
    user_id: Optional[str] = None
) -> Order:
    if not order_data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn hàng phải chứa ít nhất 1 sản phẩm"
        )

    order = Order(
        user_id=user_id,
        status="pending",
        total_amount=order_data.total_amount,
        shipping_address=order_data.shipping_address,
        payment_method=order_data.payment_method or "cod"
    )
    db.add(order)
    db.flush()

    for item in order_data.items:
        order_item = OrderItem(
            order_id=order.id,
            item_id=str(item.item_id),
            product_name=item.product_name,
            quantity=item.quantity,
            unit_price=item.unit_price
        )
        db.add(order_item)

    db.commit()
    db.refresh(order)
    return order


def get_user_orders(db: Session, user_id: str) -> List[Order]:
    return db.query(Order).filter(Order.user_id == user_id).order_by(desc(Order.created_at)).all()


def get_order_by_id(db: Session, order_id: str, user_id: Optional[str] = None) -> Optional[Order]:
    query = db.query(Order).filter(Order.id == order_id)
    if user_id:
        query = query.filter(Order.user_id == user_id)
    return query.first()
