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
from sqlalchemy import func
from sqlalchemy.orm import aliased

from backend.src.models.orm import UserEvent, UserSession, Product, RecommendationRequest, RecommendationItem
from backend.src.services.event_service import ensure_user_session
from backend.src.services.preferences_service import read_preferences

ROOT = Path(__file__).resolve().parents[3]
_slots = threading.BoundedSemaphore(2)


def recommendation_feed(db, user_id=None, session_id=None, context="home", item_id=None, limit=12, exclude=None):
    now = dt.datetime.now(dt.timezone.utc)
    preferences = read_preferences(db, user_id)["categories"] if user_id else []
    history = []
    if user_id or session_id:
        query = db.query(UserEvent).filter(UserEvent.item_id.isnot(None))
        query = query.filter(UserEvent.user_id == user_id) if user_id else query.filter(
            UserEvent.user_id.is_(None), UserEvent.session_id == session_id)
        history = query.order_by(UserEvent.created_at.desc(), UserEvent.id.desc()).limit(100).all()
    session = [e for e in history if session_id and str(e.session_id) == session_id
               and e.created_at.replace(tzinfo=dt.timezone.utc) >= now - dt.timedelta(minutes=30)]
    distinct = len({e.item_id for e in history})
    session_distinct = len({e.item_id for e in session})
    # Session intent and long-term eligibility are independent. A returning user
    # can therefore use GRU for the current visit and ALS/Two-Tower for their
    # durable profile in the same request.
    long_term_eligible = bool(user_id and distinct >= 10)
    segment = "session" if session_distinct >= 3 else "warm" if long_term_eligible else "few" if distinct else "cold"
    recent = db.query(UserEvent.item_id, func.count(UserEvent.id)).filter(
        UserEvent.created_at >= now - dt.timedelta(days=30), UserEvent.item_id.isnot(None), UserEvent.event_type != "unlike"
    ).group_by(UserEvent.item_id).order_by(func.count(UserEvent.id).desc()).limit(1500).all()
    trending = db.query(UserEvent.item_id, func.count(UserEvent.id)).filter(
        UserEvent.created_at >= now - dt.timedelta(days=1), UserEvent.item_id.isnot(None), UserEvent.event_type != "unlike"
    ).group_by(UserEvent.item_id).order_by(func.count(UserEvent.id).desc()).limit(500).all()
    seeds = list(dict.fromkeys(([item_id] if item_id else []) + [e.item_id for e in history if e.event_type != "unlike"]))[:40]
    covis = []
    if seeds:
        # Session co-occurrence, restricted to a recent window and bounded seed set.
        left, right = aliased(UserEvent), aliased(UserEvent)
        peers = db.query(left.session_id).filter(left.item_id.in_(seeds), left.session_id.isnot(None),
            left.created_at >= now - dt.timedelta(days=7), left.event_type != "unlike").distinct().limit(1000).subquery()
        covis = db.query(right.item_id, func.count(func.distinct(right.session_id))).filter(
            right.session_id.in_(db.query(peers.c.session_id)), right.item_id.notin_(seeds),
            right.created_at >= now - dt.timedelta(days=7), right.event_type != "unlike"
        ).group_by(right.item_id).order_by(func.count(func.distinct(right.session_id)).desc()).limit(500).all()
    payload = dict(user_id=user_id, preferences=preferences, segment=segment, context=context,
                   trigger_item_id=item_id, limit=limit, exclude=exclude or [], seeds=seeds,
                   history_distinct_count=distinct, session_distinct_count=session_distinct,
                   long_term_eligible=long_term_eligible,
                   history=[{"item_id": e.item_id, "event_type": e.event_type,
                             "age_hours": max(0.0, (now - e.created_at.replace(tzinfo=dt.timezone.utc)).total_seconds() / 3600)}
                            for e in reversed(session if segment == "session" else history)],
                   popularity=dict(recent), trending=dict(trending), covis=dict(covis))
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
        response["items"] = [item for item in response["items"] if item["id"] not in inactive]
        if session_id:
            ensure_user_session(db, session_id, user_id)
        existing = {row[0] for row in db.query(Product.item_id).filter(Product.item_id.in_(ids)).all()}
        for item in response["items"]:
            if item["id"] not in existing:
                db.add(Product(item_id=item["id"], name=item["name"], price=item["price"],
                    category0=item.get("c0_name"), category1=item.get("c1_name"), category2=item.get("c2_name"),
                    brand=item.get("brand"), condition=item.get("condition"), is_active=True))
        request_id = response["request_id"]
        db.add(RecommendationRequest(id=request_id, user_id=user_id, session_id=session_id,
            context=context, trigger_item_id=item_id if item_id and db.get(Product, item_id) else None,
            model_name=response["model_name"][:100]))
        for rank, item in enumerate(response["items"], start=1):
            db.add(RecommendationItem(request_id=request_id, item_id=item["id"], rank_position=rank,
                score=item.get("score"), source_model=response["ranker"][:100]))
        db.commit()
        return response
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
        logging.getLogger(__name__).warning("recommendation_worker_failed type=%s", type(exc).__name__)
        raise HTTPException(503, "Chưa thể tạo gợi ý. Vui lòng thử lại.") from None
    finally:
        _slots.release()
