"""Read persisted A/B exposure/click/cart metrics; no synthetic interactions."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

import numpy as np
from sqlalchemy.orm import Session

from backend.src.models.orm import RecommendationRequest, UserEvent, UserSession
from backend.src.services.recommendation_experiment import parse_experiment, utc_datetime


def summarize(records, experiment_id, bootstrap_samples=1000):
    """records: trusted variant/subject/request/item/event/time from PostgreSQL."""
    exposures, events = {}, []
    for record in records:
        if record["experiment"] != experiment_id:
            continue
        key = (record["request_id"], record["item_id"])
        if record["event_type"] == "impression":
            previous = exposures.get(key)
            if previous is None or record["time"] < previous["time"]:
                exposures[key] = record
        elif record["event_type"] in ("click", "cart"):
            events.append(record)
    counts = {"A": {}, "B": {}}
    for exposure in exposures.values():
        vector = counts[exposure["variant"]].setdefault(exposure["subject"], np.zeros(3))
        vector[0] += 1
    attributed = set()
    for event in events:
        key = (event["request_id"], event["item_id"])
        exposure = exposures.get(key)
        if not exposure or event["subject"] != exposure["subject"] or event["variant"] != exposure["variant"]:
            continue
        delay = event["time"] - exposure["time"]
        if not 0 <= delay.total_seconds() <= 1800:
            continue
        dedupe = (*key, event["event_type"])
        if dedupe in attributed:
            continue
        attributed.add(dedupe)
        counts[event["variant"]][event["subject"]][1 if event["event_type"] == "click" else 2] += 1
    result = {}
    arrays = {}
    for variant in ("A", "B"):
        array = np.array(list(counts[variant].values()), dtype=float).reshape(-1, 3)
        arrays[variant] = array
        total = array.sum(axis=0)
        result[variant] = dict(ranker="DCN" if variant == "A" else "LightGBM", exposed_users=len(array),
            impressions=int(total[0]), clicked_impressions=int(total[1]), cart_impressions=int(total[2]),
            CTR=float(total[1] / total[0]) if total[0] else None,
            cart_rate=float(total[2] / total[0]) if total[0] else None)
    interval = None
    if all(len(arrays[group]) >= 2 for group in ("A", "B")):
        rng = np.random.default_rng(42)
        deltas = []
        for _ in range(bootstrap_samples):
            rates = []
            for group in ("A", "B"):
                array = arrays[group]
                total = array[rng.integers(len(array), size=len(array))].sum(axis=0)
                rates.append(total[1] / total[0])
            deltas.append(rates[1] - rates[0])
        interval = np.quantile(deltas, [.025, .975]).tolist()
    delta = result["B"]["CTR"] - result["A"]["CTR"] if all(result[g]["CTR"] is not None for g in ("A", "B")) else None
    return dict(experiment=experiment_id, groups=result, CTR_delta_B_minus_A=delta,
                CTR_delta_user_bootstrap_95CI=interval,
                attribution_window_minutes=30, analysis_unit="user or stable anonymous browser",
                note="Report descriptive counts; sample size/duration must be preplanned before declaring a winner. No purchase conversion claim.")


def report(db, experiment_id, since=None):
    query = (db.query(UserEvent, RecommendationRequest, UserSession)
        .join(RecommendationRequest, RecommendationRequest.id == UserEvent.recommendation_request_id)
        .outerjoin(UserSession, UserSession.id == RecommendationRequest.session_id)
        .filter(UserEvent.event_type.in_(("impression", "click", "cart")),
                RecommendationRequest.model_name.like(f"exp:{experiment_id}:%")))
    if since:
        query = query.filter(RecommendationRequest.generated_at >= since)
    records = []
    for event, request, session in query:
        experiment = parse_experiment(request.model_name)
        if not experiment:
            continue
        subject = f"user:{request.user_id}" if request.user_id else (session.source if session else f"session:{request.session_id}")
        records.append(dict(experiment=experiment["id"], variant=experiment["variant"], subject=subject,
            request_id=str(request.id), item_id=event.item_id, event_type=event.event_type,
            time=utc_datetime(event.created_at)))
    return summarize(records, experiment_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", default="dcn_lightgbm_home_v1")
    parser.add_argument("--since", type=dt.datetime.fromisoformat)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from backend.src.database.connection import SessionLocal
    with SessionLocal() as db:
        result = report(db, args.experiment, args.since)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
