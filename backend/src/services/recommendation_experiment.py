"""Stable experiment assignment and persisted feed pages using existing tables."""
import datetime as dt
import hashlib
import os
import re
from pathlib import Path
from uuid import UUID, uuid5

from dotenv import load_dotenv
from fastapi import HTTPException

from backend.src.models.orm import Product, RecommendationItem, RecommendationRequest

load_dotenv(Path(__file__).resolve().parents[3] / ".env")
SNAPSHOT_SIZE = 240
FEED_TTL = dt.timedelta(hours=6)


def utc_datetime(value):
    """SQLite returns naive UTC; PostgreSQL may return aware local timestamps."""
    return value.astimezone(dt.timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def assignment(user_id=None, anonymous_id=None, context="home"):
    if context != "home" or os.getenv("MERREC_AB_ENABLED", "0") != "1":
        return None
    subject = f"user:{user_id}" if user_id else f"guest:{anonymous_id}" if anonymous_id else None
    if not subject:
        return None
    experiment = os.getenv("MERREC_AB_EXPERIMENT", "dcn_lightgbm_home_v1")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", experiment):
        raise HTTPException(503, "Cấu hình gợi ý tạm thời chưa khả dụng.")
    bucket = int.from_bytes(hashlib.sha256(f"{experiment}:{subject}".encode()).digest()[:8], "big") % 100
    variant = "A" if bucket < 50 else "B"
    return {"id": experiment, "variant": variant, "ranker": "dcn" if variant == "A" else "lightgbm"}


def experiment_tag(experiment):
    return f"exp:{experiment['id']}:{experiment['variant']}:{experiment['ranker']}"


def parse_experiment(tag):
    parts = (tag or "").split(":")
    if len(parts) == 4 and parts[0] == "exp" and parts[2] in ("A", "B") and parts[3] in ("dcn", "lightgbm"):
        return {"id": parts[1], "variant": parts[2], "ranker": parts[3]}
    return None


def parse_cursor(cursor):
    try:
        request_id, raw = cursor.split(":")
        request_id = str(UUID(request_id))
        offset = int(raw)
        if str(offset) != raw or not 0 <= offset <= 2_147_483_647:
            raise ValueError()
        return request_id, offset
    except (ValueError, AttributeError):
        raise HTTPException(422, "Vị trí tải gợi ý không hợp lệ.") from None


def block_id(root_id, index):
    return str(root_id) if index == 0 else str(uuid5(UUID(str(root_id)), f"feed-block:{index}"))


def read_feed_page(db, request, limit, offset=0, root_id=None, block_start=0):
    rows = (db.query(RecommendationItem, Product)
            .join(Product, Product.item_id == RecommendationItem.item_id)
            .filter(RecommendationItem.request_id == request.id,
                    RecommendationItem.rank_position > offset, Product.is_active.is_(True))
            .order_by(RecommendationItem.rank_position).limit(limit + 1).all())
    has_more_in_block = len(rows) > limit
    selected = rows[:limit]
    items = []
    for rec, product in selected:
        items.append(dict(id=str(product.item_id), name=product.name, price=float(product.price or 0),
            originalPrice=float(product.price or 0), discount=0, rating=0, soldCount=0,
            image="", images=[], c0_name=product.category0 or "", c0_display=product.category0 or "",
            c1_name=product.category1 or "", c2_name=product.category2 or "",
            brand=product.brand or "", condition=product.condition or "", inStock=True,
            stockCount=0, stockKnown=False, description=getattr(product, "description", None) or "Chưa có mô tả sản phẩm.",
            currency="USD", source="merrec", score=rec.score, position=rec.rank_position))
    experiment = parse_experiment(request.model_name)
    ranker = experiment["ranker"] if experiment else (rows[0][0].source_model if rows else "empty")
    # A nonempty block is not the end of the feed. The next block performs
    # retrieval again, excluding every item reserved in earlier blocks.
    has_more = bool(rows) or db.query(RecommendationItem).filter_by(request_id=request.id).first() is not None
    next_offset = block_start + selected[-1][0].rank_position if has_more_in_block else block_start + SNAPSHOT_SIZE
    return dict(request_id=str(request.id), context=request.context, trigger_item_id=request.trigger_item_id,
                model_name=request.model_name, ranker=ranker, experiment=experiment,
                items=items, has_more=has_more,
                next_cursor=f"{root_id or request.id}:{next_offset}" if has_more else None)


def resolve_feed_cursor(db, cursor, user_id, session_id):
    request_id, offset = parse_cursor(cursor)
    request = db.get(RecommendationRequest, request_id)
    if request is None:
        raise HTTPException(404, "Danh sách gợi ý không còn khả dụng.")
    if request.context != "home" or request.user_id != user_id or (user_id is None and request.session_id != session_id):
        raise HTTPException(403, "Danh sách gợi ý không thuộc phiên này.")
    generated = utc_datetime(request.generated_at)
    if dt.datetime.now(dt.timezone.utc) - generated > FEED_TTL:
        raise HTTPException(410, "Danh sách gợi ý đã hết hạn. Vui lòng tải lại.")
    index, local_offset = divmod(offset, SNAPSHOT_SIZE)
    if index and db.get(RecommendationRequest, block_id(request.id, index - 1)) is None:
        raise HTTPException(422, "Vị trí tải gợi ý không hợp lệ.")
    block = db.get(RecommendationRequest, block_id(request.id, index))
    return request, block, local_offset, index


def resume_feed(db, cursor, user_id, session_id, limit):
    root, block, offset, index = resolve_feed_cursor(db, cursor, user_id, session_id)
    if block is None:
        return None
    return read_feed_page(db, block, limit, offset, str(root.id), index * SNAPSHOT_SIZE)
