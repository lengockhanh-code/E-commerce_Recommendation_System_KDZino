"""Order Management Service: Checkout, Order Persistence & History"""

from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.src.models.orm import Order, OrderItem, generate_uuid
from backend.src.models.schemas import OrderCreate, OrderResponse, OrderItemResponse


def create_order(db: Session, data: OrderCreate, user_id: Optional[str] = None) -> OrderResponse:
    if not data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giỏ hàng trống. Vui lòng thêm sản phẩm trước khi thanh toán."
        )

    items_total = sum(item.quantity * item.unit_price for item in data.items)
    grand_total = items_total + data.shipping_fee

    order_id = generate_uuid()
    order = Order(
        id=order_id,
        user_id=user_id if user_id else None,
        full_name=data.full_name,
        email=data.email.lower(),
        phone=data.phone,
        address=data.address,
        city=data.city,
        district=data.district,
        payment_method=data.payment_method,
        shipping_fee=data.shipping_fee,
        total_amount=grand_total,
        status="pending"
    )
    db.add(order)
    db.flush()

    order_items = []
    for item in data.items:
        item_obj = OrderItem(
            id=generate_uuid(),
            order_id=order_id,
            item_id=str(item.item_id),
            product_name=item.product_name,
            quantity=item.quantity,
            unit_price=item.unit_price
        )
        db.add(item_obj)
        order_items.append(item_obj)

    db.commit()
    db.refresh(order)

    # Log order event in user_events for activity history
    if user_id:
        from backend.src.services.event_service import log_user_event
        from backend.src.models.schemas import EventCreate
        for item in data.items:
            log_user_event(
                db,
                EventCreate(
                    session_id=str(order.id),
                    event_type="order",
                    item_id=str(item.item_id)
                ),
                user_id=user_id
            )

    return OrderResponse(
        id=str(order.id),
        user_id=str(order.user_id) if order.user_id else None,
        full_name=order.full_name,
        email=order.email,
        phone=order.phone,
        address=order.address,
        city=order.city,
        district=order.district,
        payment_method=order.payment_method,
        shipping_fee=order.shipping_fee,
        total_amount=order.total_amount,
        status=order.status,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                id=str(it.id),
                item_id=it.item_id,
                product_name=it.product_name,
                quantity=it.quantity,
                unit_price=it.unit_price
            ) for it in order_items
        ]
    )


def get_user_orders(db: Session, user_id: str) -> List[OrderResponse]:
    orders = db.query(Order).filter(Order.user_id == str(user_id)).order_by(Order.created_at.desc()).all()
    res = []
    for o in orders:
        items = [
            OrderItemResponse(
                id=str(it.id),
                item_id=it.item_id,
                product_name=it.product_name,
                quantity=it.quantity,
                unit_price=it.unit_price
            ) for it in o.items
        ]
        res.append(
            OrderResponse(
                id=str(o.id),
                user_id=str(o.user_id) if o.user_id else None,
                full_name=o.full_name,
                email=o.email,
                phone=o.phone,
                address=o.address,
                city=o.city,
                district=o.district,
                payment_method=o.payment_method,
                shipping_fee=o.shipping_fee,
                total_amount=o.total_amount,
                status=o.status,
                created_at=o.created_at,
                items=items
            )
        )
    return res


def get_order_by_id(db: Session, order_id: str, user_id: Optional[str] = None) -> Optional[OrderResponse]:
    q = db.query(Order).filter(Order.id == str(order_id))
    if user_id:
        q = q.filter(Order.user_id == str(user_id))
    o = q.first()
    if not o:
        return None

    items = [
        OrderItemResponse(
            id=str(it.id),
            item_id=it.item_id,
            product_name=it.product_name,
            quantity=it.quantity,
            unit_price=it.unit_price
        ) for it in o.items
    ]
    return OrderResponse(
        id=str(o.id),
        user_id=str(o.user_id) if o.user_id else None,
        full_name=o.full_name,
        email=o.email,
        phone=o.phone,
        address=o.address,
        city=o.city,
        district=o.district,
        payment_method=o.payment_method,
        shipping_fee=o.shipping_fee,
        total_amount=o.total_amount,
        status=o.status,
        created_at=o.created_at,
        items=items
    )
