"""Authenticated context assembly. Catalog/model work runs with a hard time limit."""

import datetime as dt
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import aliased

from backend.src.models.orm import UserEvent, UserSession, Product, RecommendationRequest, RecommendationItem, AuthAccount
from backend.src.services.event_service import ensure_user_session
from backend.src.services.preferences_service import read_preferences
from backend.src.services.recommendation_experiment import assignment, experiment_tag, parse_experiment, resolve_feed_cursor, block_id, read_feed_page, SNAPSHOT_SIZE, utc_datetime

ROOT = Path(__file__).resolve().parents[3]
_slots = threading.BoundedSemaphore(2)
RECENT_HISTORY_WINDOW = dt.timedelta(days=7)


def recommendation_feed(db, user_id=None, session_id=None, context="home", item_id=None, limit=12, exclude=None, cursor=None, anonymous_id=None):
    root = None
    block_index = 0
    continuation_id = None
    if cursor:
        if context != "home":
            raise HTTPException(422, "Phân trang chỉ áp dụng cho gợi ý trang chủ.")
        root, block, offset, block_index = resolve_feed_cursor(db, cursor, user_id, session_id)
        active_experiment = assignment(user_id, anonymous_id if session_id else None, context)
        stored_experiment = parse_experiment(root.model_name)
        if active_experiment and stored_experiment and active_experiment["id"] != stored_experiment["id"]:
            raise HTTPException(410, "Cấu hình gợi ý đã thay đổi. Vui lòng tải lại.")
        activity_query = db.query(func.max(UserEvent.created_at)).filter(UserEvent.event_type != "impression")
        if user_id:
            activity_query = activity_query.filter(UserEvent.user_id == user_id)
        elif anonymous_id:
            activity_query = activity_query.outerjoin(UserSession, UserSession.id == UserEvent.session_id).filter(
                UserEvent.user_id.is_(None), or_(UserEvent.session_id == session_id,
                    UserSession.source == f"experiment_guest:{anonymous_id}"))
        else:
            activity_query = activity_query.filter(UserEvent.user_id.is_(None), UserEvent.session_id == session_id)
        latest_activity = activity_query.scalar()
        latest_activity = utc_datetime(latest_activity) if latest_activity else None
        stale = block is not None and latest_activity is not None and latest_activity > utc_datetime(block.generated_at)
        if block is not None and not stale:
            return read_feed_page(db, block, limit, offset, str(root.id), block_index * SNAPSHOT_SIZE)
        if offset and not stale:
            raise HTTPException(422, "Vị trí tải gợi ý không hợp lệ.")
        # Serialize continuation creation in PostgreSQL. Repeated/concurrent
        # requests for the same cursor reuse the same durable block.
        db.query(RecommendationRequest).filter_by(id=root.id).with_for_update().one()
        if stale:
            # Keep delivered ranks and any recorded interactions. Retire only
            # the unseen draft tail, so a refresh can retrieve those items again
            # instead of excluding hundreds of products the user never saw.
            recorded = db.query(UserEvent.id).filter(UserEvent.recommendation_request_id == block.id,
                UserEvent.item_id == RecommendationItem.item_id).exists()
            db.query(RecommendationItem).filter(RecommendationItem.request_id == block.id,
                RecommendationItem.rank_position > offset, ~recorded).delete(synchronize_session=False)
            block_index += 1
            # Reuse a fresh continuation created by a concurrent request/retry.
            # Earlier reserved blocks remain excluded so visible cards never repeat.
            while True:
                candidate = db.get(RecommendationRequest, block_id(root.id, block_index))
                if candidate is None:
                    break
                if utc_datetime(candidate.generated_at) >= latest_activity:
                    return read_feed_page(db, candidate, limit, 0, str(root.id), block_index * SNAPSHOT_SIZE)
                block_index += 1
        continuation_id = block_id(root.id, block_index)
        block = db.get(RecommendationRequest, continuation_id)
        if block is not None:
            return read_feed_page(db, block, limit, 0, str(root.id), block_index * SNAPSHOT_SIZE)
        previous_ids = [block_id(root.id, index) for index in range(block_index)]
        reserved = [row[0] for row in db.query(RecommendationItem.item_id).filter(
            RecommendationItem.request_id.in_(previous_ids)).all()]
        inactive = [row[0] for row in db.query(Product.item_id).filter(Product.is_active.is_(False)).all()]
        exclude = list(dict.fromkeys((exclude or []) + reserved + inactive))
    if session_id:
        session_record = ensure_user_session(db, session_id, user_id)
        if not user_id and anonymous_id:
            identity = f"experiment_guest:{anonymous_id}"
            if session_record.source and session_record.source.startswith("experiment_guest:") and session_record.source != identity:
                raise HTTPException(403, "Phiên gợi ý không hợp lệ.")
            session_record.source = identity
    experiment = parse_experiment(root.model_name) if root else assignment(user_id, anonymous_id if session_id else None, context)
    now = dt.datetime.now(dt.timezone.utc)
    preferences = read_preferences(db, user_id)["categories"] if user_id else []
    history = []
    if user_id or session_id:
        query = db.query(UserEvent).filter(UserEvent.item_id.isnot(None), UserEvent.event_type != "impression")
        if user_id:
            query = query.filter(UserEvent.user_id == user_id)
        elif anonymous_id:
            # A guest returning in a new browsing session keeps the history of
            # this browser identity. Never include authenticated account events.
            db.flush()
            query = query.outerjoin(UserSession, UserSession.id == UserEvent.session_id).filter(
                UserEvent.user_id.is_(None), or_(UserEvent.session_id == session_id,
                    UserSession.source == f"experiment_guest:{anonymous_id}"))
        else:
            query = query.filter(UserEvent.user_id.is_(None), UserEvent.session_id == session_id)
        history = query.order_by(UserEvent.created_at.desc(), UserEvent.id.desc()).limit(100).all()
    session = [e for e in history if session_id and str(e.session_id) == session_id
               and utc_datetime(e.created_at) >= now - dt.timedelta(minutes=30)]
    distinct = len({e.item_id for e in history})
    session_distinct = len({e.item_id for e in session})
    latest_actions = {}
    for event in history:
        latest_actions.setdefault(event.item_id, event.event_type)
    dismissed = {key for key, kind in latest_actions.items() if kind == "unlike"}
    recent_history = [e for e in history if e.event_type != "unlike" and e.item_id not in dismissed
        and utc_datetime(e.created_at) >= now - RECENT_HISTORY_WINDOW]
    recent_distinct = len({e.item_id for e in recent_history})
    # Recent sequential history survives a new app/browser session. Long-term
    # eligibility is independent of the current visit's interaction count.
    long_term_eligible = bool((user_id or anonymous_id) and distinct >= 10)
    # Only server-owned demo account links can select a trained user embedding.
    model_user_id = user_id
    if user_id:
        account = db.query(AuthAccount).filter(AuthAccount.user_id == user_id,
            AuthAccount.provider == "local").first()
        link = account.provider_account_id if account else None
        if link and link.startswith("merrec-demo:") and link[12:].isdigit():
            model_user_id = link[12:]
    segment = "session" if recent_distinct >= 3 else "warm" if long_term_eligible else "few" if distinct else "cold"
    recent = db.query(UserEvent.item_id, func.count(UserEvent.id)).filter(
        UserEvent.created_at >= now - dt.timedelta(days=30), UserEvent.item_id.isnot(None), UserEvent.event_type.notin_(("unlike", "impression"))
    ).group_by(UserEvent.item_id).order_by(func.count(UserEvent.id).desc()).limit(1500).all()
    trending = db.query(UserEvent.item_id, func.count(UserEvent.id)).filter(
        UserEvent.created_at >= now - dt.timedelta(days=1), UserEvent.item_id.isnot(None), UserEvent.event_type.notin_(("unlike", "impression"))
    ).group_by(UserEvent.item_id).order_by(func.count(UserEvent.id).desc()).limit(500).all()
    seeds = list(dict.fromkeys(([item_id] if item_id else []) + [e.item_id for e in history
        if e.event_type != "unlike" and e.item_id not in dismissed]))[:100]
    covis = []
    if seeds:
        # Session co-occurrence, restricted to a recent window and bounded seed set.
        left, right = aliased(UserEvent), aliased(UserEvent)
        peers = db.query(left.session_id).filter(left.item_id.in_(seeds), left.session_id.isnot(None),
            left.created_at >= now - dt.timedelta(days=7), left.event_type.notin_(("unlike", "impression"))).distinct().limit(1000).subquery()
        covis = db.query(right.item_id, func.count(func.distinct(right.session_id))).filter(
            right.session_id.in_(db.query(peers.c.session_id)), right.item_id.notin_(seeds),
            right.created_at >= now - dt.timedelta(days=7), right.event_type.notin_(("unlike", "impression"))
        ).group_by(right.item_id).order_by(func.count(func.distinct(right.session_id)).desc()).limit(500).all()
    payload = dict(user_id=user_id, model_user_id=model_user_id, preferences=preferences, segment=segment, context=context,
                   trigger_item_id=item_id, limit=SNAPSHOT_SIZE if context == "home" else limit, exclude=exclude or [], seeds=seeds,
                   history_distinct_count=distinct, session_distinct_count=session_distinct,
                   recent_distinct_count=recent_distinct,
                   long_term_eligible=long_term_eligible,
                   history=[{"item_id": e.item_id, "event_type": e.event_type,
                             "age_hours": max(0.0, (now - utc_datetime(e.created_at)).total_seconds() / 3600)}
                            for e in reversed(history)],
                   recent_history=[{"item_id": e.item_id, "event_type": e.event_type,
                             "age_hours": max(0.0, (now - utc_datetime(e.created_at)).total_seconds() / 3600)}
                            for e in reversed(recent_history)],
                   popularity=dict(recent), trending=dict(trending), covis=dict(covis))
    if experiment:
        payload.update(ranker_override=experiment["ranker"], blend_weight=.7,
            dcn_path=os.getenv("MERREC_AB_DCN_PATH", str(ROOT / "training/dcn/runs/numeric_earlystop_20261010/model/dcn_best.pt")))
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "Hệ thống gợi ý đang bận. Vui lòng thử lại.")
    try:
        result = subprocess.run([sys.executable, str(ROOT / "scripts/personalized_recommendations.py")],
            input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True,
            cwd=ROOT, timeout=40, check=True)
        response = json.loads(result.stdout)
        ids = [item["id"] for item in response["items"]]
        inactive = {row[0] for row in db.query(Product.item_id).filter(
            Product.item_id.in_(ids), Product.is_active.is_(False)).all()}
        excluded = set(exclude or [])
        response["items"] = [item for item in response["items"] if item["id"] not in inactive and item["id"] not in excluded]
        if session_id:
            ensure_user_session(db, session_id, user_id)
        existing = {row[0] for row in db.query(Product.item_id).filter(Product.item_id.in_(ids)).all()}
        for item in response["items"]:
            if item["id"] not in existing:
                db.add(Product(item_id=item["id"], name=item["name"], price=item["price"],
                    category0=item.get("c0_name"), category1=item.get("c1_name"), category2=item.get("c2_name"),
                    brand=item.get("brand"), condition=item.get("condition"), is_active=True))
                existing.add(item["id"])
        request_id = continuation_id or response["request_id"]
        record = RecommendationRequest(id=request_id, user_id=user_id, session_id=session_id,
            context=context, trigger_item_id=item_id if item_id and db.get(Product, item_id) else None,
            model_name=experiment_tag(experiment) if experiment else response["model_name"][:100], generated_at=now)
        db.add(record)
        if root:
            record.model_name = root.model_name
        db.flush()
        added_rec_items = set()
        for rank, item in enumerate(response["items"], start=1):
            if item["id"] in added_rec_items:
                continue
            added_rec_items.add(item["id"])
            db.add(RecommendationItem(request_id=request_id, item_id=item["id"], rank_position=rank,
                score=item.get("score"), source_model=response["ranker"][:100]))
        db.commit()
        if context == "home":
            page = read_feed_page(db, record, limit, root_id=str(root.id) if root else None,
                block_start=block_index * SNAPSHOT_SIZE)
            page.update(segment=response["segment"], model_status=response["model_status"], degraded=response["degraded"],
                retrieval_modes=response.get("retrieval_modes", {}))
            return page
        return response
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
        logging.getLogger(__name__).warning("recommendation_worker_failed type=%s", type(exc).__name__)
        raise HTTPException(503, "Chưa thể tạo gợi ý. Vui lòng thử lại.") from None
    finally:
        _slots.release()
