"""Admin Analytics & System Metrics"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.src.models.orm import User, Product, Order, OrderItem
from backend.src.models.schemas import AdminStatsResponse, OrderResponse, OrderItemResponse


def get_admin_metrics(db: Session) -> AdminStatsResponse:
    total_revenue = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).scalar() or 0.0
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    total_products = db.query(func.count(Product.item_id)).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0

    top_items_query = (
        db.query(
            OrderItem.item_id,
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label("total_sold"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("revenue")
        )
        .group_by(OrderItem.item_id, OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )

    top_selling = [
        {
            "item_id": item.item_id,
            "product_name": item.product_name,
            "total_sold": int(item.total_sold or 0),
            "revenue": float(item.revenue or 0.0)
        }
        for item in top_items_query
    ]

    recent_orders_db = (
        db.query(Order)
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )

    recent_orders = []
    for o in recent_orders_db:
        items = [
            OrderItemResponse(
                id=str(it.id),
                item_id=it.item_id,
                product_name=it.product_name,
                quantity=it.quantity,
                unit_price=it.unit_price
            ) for it in o.items
        ]
        recent_orders.append(
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

    return AdminStatsResponse(
        total_revenue=float(total_revenue),
        total_orders=int(total_orders),
        total_products=int(total_products),
        total_users=int(total_users),
        top_selling_products=top_selling,
        recent_orders=recent_orders
    )
