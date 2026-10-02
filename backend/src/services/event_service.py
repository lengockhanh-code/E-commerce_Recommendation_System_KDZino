"""User Analytics Event Service: Event Persistence & Activity History Query"""

import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.src.models.orm import UserEvent, UserSession, RecommendationRequest, Product, ProductImage, generate_uuid
from backend.src.models.schemas import EventCreate, EventResponse


def ensure_user_session(db: Session, session_id: str, user_id: Optional[str]) -> UserSession:
    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError
    browsing = db.get(UserSession, session_id)
    if not browsing:
        try:
            with db.begin_nested():
                db.add(UserSession(id=session_id, user_id=user_id))
                db.flush()
        except IntegrityError:
            pass  # A concurrent request may have created this session.
        browsing = db.get(UserSession, session_id)
    if browsing is None or browsing.user_id != user_id:
        raise HTTPException(403, "Phiên tương tác không thuộc tài khoản này")
    return browsing


def log_user_event(db: Session, data: EventCreate, user_id: Optional[str] = None) -> EventResponse:
    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError
    if data.session_id:
        ensure_user_session(db, str(data.session_id), user_id)
    if data.recommendation_request_id:
        request = db.get(RecommendationRequest, str(data.recommendation_request_id))
        if request is None or request.user_id != user_id or (user_id is None and request.session_id != str(data.session_id)):
            raise HTTPException(403, "Yêu cầu gợi ý không thuộc phiên này")
    if not db.get(Product, data.item_id):
        import json
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        try:
            result = subprocess.run([sys.executable, str(root / "scripts/personalized_recommendations.py")],
                input=json.dumps({"operation": "item", "item_id": data.item_id}),
                text=True, encoding="utf-8", capture_output=True, timeout=8, check=True, cwd=root)
            row = json.loads(result.stdout)
        except (subprocess.SubprocessError, OSError, ValueError):
            raise HTTPException(503, "Chưa thể xác minh sản phẩm. Vui lòng thử lại.") from None
        if row is None:
            raise HTTPException(404, "Sản phẩm không tồn tại")
        try:
            with db.begin_nested():
                db.add(Product(**{key: row.get(key) for key in ("item_id", "product_id", "name", "price", "category0", "category1", "category2", "brand", "condition", "shipper")}))
                db.flush()
        except IntegrityError:
            if not db.get(Product, data.item_id):
                raise
    if not db.get(Product, data.item_id).is_active:
        raise HTTPException(404, "Sản phẩm không còn khả dụng")
    if data.event_key:
        previous = db.query(UserEvent).filter(UserEvent.event_key == str(data.event_key)).first()
        if previous:
            if (previous.user_id, previous.session_id, previous.item_id, previous.event_type) != (
                user_id, str(data.session_id) if data.session_id else None, data.item_id, data.event_type
            ):
                raise HTTPException(409, "Mã tương tác đã được sử dụng")
            return EventResponse(status="success", event_id=str(previous.id))
    event = UserEvent(
        event_key=str(data.event_key) if data.event_key else None,
        user_id=user_id,
        session_id=str(data.session_id) if data.session_id else None,
        event_type=data.event_type,
        item_id=data.item_id,
        extra_data=data.extra_data,
        source_page=data.source_page,
        recommendation_request_id=str(data.recommendation_request_id) if data.recommendation_request_id else None,
        position=data.position,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if data.event_key:
            previous = db.query(UserEvent).filter(UserEvent.event_key == str(data.event_key)).first()
            if previous:
                return log_user_event(db, data, user_id)
        raise
    db.refresh(event)
    return EventResponse(status="success", event_id=str(event.id))


def get_user_activity_history(db: Session, user_id: str) -> List[Dict[str, Any]]:
    """Query user_events for user_id joined with products and product_images from PostgreSQL"""
    events_db = (
        db.query(UserEvent)
        .filter(UserEvent.user_id == str(user_id))
        .order_by(UserEvent.created_at.desc())
        .limit(50)
        .all()
    )

    if not events_db:
        return []

    # Deduplicate view events for the same product on the same date
    seen_views = set()
    deduped_events = []
    for e in events_db:
        if e.event_type in ("view", "view_item") and e.item_id:
            created_ts = e.created_at or datetime.datetime.now()
            date_str = created_ts.strftime("%Y-%m-%d")
            view_key = f"{e.item_id}:{date_str}"
            if view_key in seen_views:
                continue
            seen_views.add(view_key)
        deduped_events.append(e)

    events_db = deduped_events

    item_ids = [e.item_id for e in events_db if e.item_id]
    products_db = db.query(Product).filter(Product.item_id.in_(item_ids)).all() if item_ids else []
    products_by_id = {p.item_id: p for p in products_db}

    images_db = db.query(ProductImage).filter(ProductImage.item_id.in_(item_ids)).all() if item_ids else []
    images_by_id = {}
    for img in images_db:
        if img.item_id not in images_by_id:
            images_by_id[img.item_id] = img.image_url

    results = []
    for e in events_db:
        p = products_by_id.get(e.item_id)
        prod_name = p.name if (p and p.name) else (e.item_id or "Sản phẩm MerRec")
        prod_price = float(p.price) if (p and p.price is not None) else 0.0
        img_url = images_by_id.get(e.item_id, "/placeholder.svg")

        event_type = e.event_type
        if event_type in ("view", "view_item", "click"):
            label = "Đã xem sản phẩm"
            action_btn = "Xem sản phẩm"
            badge_type = "view"
        elif event_type in ("cart", "add_to_cart"):
            label = "Đã thêm vào giỏ hàng"
            action_btn = "Xem giỏ hàng"
            badge_type = "cart"
        elif event_type in ("like", "favorite"):
            label = "Đã yêu thích sản phẩm"
            action_btn = "Xem sản phẩm"
            badge_type = "favorite"
        elif event_type in ("buy_comp", "purchase", "order"):
            label = "Đã đặt hàng"
            action_btn = "Xem đơn hàng"
            badge_type = "order"
        else:
            label = "Hoạt động sản phẩm"
            action_btn = "Xem sản phẩm"
            badge_type = "view"

        created_ts = e.created_at or datetime.datetime.now()
        results.append({
            "id": str(e.id),
            "type": badge_type,
            "label": label,
            "title": prod_name,
            "price": prod_price,
            "image": img_url,
            "item_id": e.item_id,
            "time": created_ts.strftime("%H:%M"),
            "dateGroup": created_ts.strftime("%d/%m/%Y"),
            "actionBtnText": action_btn,
            "href": f"/products/{e.item_id}" if e.item_id else "/products"
        })

    return results
