"""Online candidate generation -> feature engineering -> rank -> diversity.

stdin/stdout JSON protocol; process isolation bounds heavy model/catalog work.
No synthetic products and no dependency-error fallback to the preview catalog.
"""

import json
import math
import os
from pathlib import Path
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from backend.src.services.preferences_service import CATEGORIES


def catalog_candidates(payload):
    import duckdb
    path = Path(os.environ.get("MERREC_CATALOG_PATH", ROOT / "data/processed/recommender/serving/item_catalog_full.parquet"))
    if not path.is_file():
        raise FileNotFoundError("catalog unavailable")
    seeds = payload.get("seeds", [])
    categories = [value for key in payload["preferences"] for value in CATEGORIES[key]]
    with duckdb.connect() as db:
        db.execute("SET threads=2")
        db.execute("SET memory_limit='512MB'")
        db.from_parquet(str(path)).create_view("catalog")
        seed_rows = db.execute("SELECT item_id, category0, category1, brand, name FROM catalog WHERE item_id IN (SELECT unnest(?))", [seeds]).fetchall()
        seed_by_id = {row[0]: row for row in seed_rows}
        categories += [row[1] for row in seed_rows if row[1]]
        subcats = [row[2] for row in seed_rows if row[2]]
        brands = [row[3] for row in seed_rows if row[3] and row[3] != "__UNK__"]
        import re
        tokens = list(dict.fromkeys(word.lower() for row in seed_rows for word in re.findall(r"\w+", row[4] or "") if len(word) > 3))[:30]
        excluded = list(set(payload.get("exclude", []) + seeds + [event["item_id"] for event in payload.get("history", [])]))
        result = db.execute("""SELECT *,
            (CASE WHEN category0 IN (SELECT unnest(?)) THEN 1.0 ELSE 0 END +
             CASE WHEN category1 IN (SELECT unnest(?)) THEN 0.6 ELSE 0 END +
             CASE WHEN brand IN (SELECT unnest(?)) THEN 0.4 ELSE 0 END +
             0.1 * len(list_intersect(regexp_split_to_array(lower(coalesce(name, '')), '\\W+'), ?))) AS content_score
            FROM catalog WHERE name IS NOT NULL AND price > 0
              AND item_id NOT IN (SELECT unnest(?))
            ORDER BY content_score DESC, last_seen_ts DESC NULLS LAST, item_id
            LIMIT 1000""", [categories, subcats, brands, tokens, excluded])
        columns = [c[0] for c in result.description]
        rows = {str(row[0]): dict(zip(columns, row)) for row in result.fetchall()}
        for row in rows.values():
            row["content_score"] = float(row["content_score"])
            row["price"] = float(row["price"])
        extra_ids = list(dict.fromkeys(list(payload["covis"]) + list(payload["popularity"]) + list(payload["trending"])))[:1500]
        if extra_ids:
            result = db.execute("SELECT *, 0.0 AS content_score FROM catalog WHERE item_id IN (SELECT unnest(?)) AND item_id NOT IN (SELECT unnest(?)) AND name IS NOT NULL AND price > 0", [extra_ids, excluded])
            columns = [c[0] for c in result.description]
            for values in result.fetchall():
                row = dict(zip(columns, values))
                row["price"] = float(row["price"])
                row["content_score"] = float(row.get("category0") in categories) + .6 * (row.get("category1") in subcats) + .4 * (row.get("brand") in brands)
                rows.setdefault(str(row["item_id"]), row)
        # Recent strong actions shape the profile more than older passive views.
        profile_categories, profile_subcats, profile_brands = Counter(), Counter(), Counter()
        event_weight = {"view": 1.0, "click": 1.0, "like": 2.5, "unlike": -2.5, "cart": 3.0, "offer": 2.0,
                        "buy_start": 2.5, "buy_comp": 4.0}
        for event in payload.get("history", []):
            seed = seed_by_id.get(event["item_id"])
            if not seed:
                continue
            weight = event_weight.get(event["event_type"], 1.0) * math.exp(-float(event.get("age_hours", 0)) / (24 * 14))
            if seed[1]: profile_categories[seed[1]] += weight
            if seed[2]: profile_subcats[seed[2]] += weight
            if seed[3] and seed[3] != "__UNK__": profile_brands[seed[3]] += weight
        for row in rows.values():
            row["content_score"] += (
                2.0 * profile_categories[row.get("category0")] / max(1.0, sum(profile_categories.values())) +
                1.0 * profile_subcats[row.get("category1")] / max(1.0, sum(profile_subcats.values())) +
                .35 * profile_brands[row.get("brand")] / max(1.0, sum(profile_brands.values()))
            )
        # Preserve union of sources while bounding the candidate pool.
        prioritized = sorted(rows.values(), key=lambda r: (
            r["content_score"] + math.log1p(payload["covis"].get(r["item_id"], 0)) +
            .1 * math.log1p(payload["popularity"].get(r["item_id"], 0))), reverse=True)
        if payload["preferences"] and not payload.get("history") and not seeds:
            prioritized = [row for row in prioritized if row["content_score"] > 0]
        return prioritized[:2000]


def features_for(rows, payload, source_scores):
    features = []
    source_features = {}
    for source in ("content", "covis", "als", "gru", "twotower"):
        scores = source_scores.get(source, {})
        topk = {"content": 150, "covis": 250, "als": 200, "gru": 200, "twotower": 300}[source]
        ordered = sorted(scores, key=lambda key: (-scores[key], key))[:topk]
        source_features[source] = {
            key: (scores[key], rank, 1.0 - (rank - 1) / max(topk - 1, 1))
            for rank, key in enumerate(ordered, 1)
        }
    for row in rows:
        f = {"user_id": payload.get("user_id") or "unknown", "candidate_item_id": str(row["item_id"])}
        for name in ("product_id", "brand", "category0", "category1", "category2", "condition", "shipper"):
            f["candidate_" + name] = str(row.get(name) or "unknown")
        f.update(candidate_price=float(row["price"]), candidate_popularity=float(payload["popularity"].get(row["item_id"], 0)), source_count=0, rrf_score=0.0)
        for source, lookup in source_features.items():
            score, rank, normalized = lookup.get(row["item_id"], (0.0, 9999, 0.0))
            f.update({source + "_score": score, source + "_rank": rank, source + "_score_norm": normalized,
                      source + "_rr": 1.0 / rank if rank < 9999 else 0.0})
            if rank < 9999:
                f["source_count"] += 1
                f["rrf_score"] += 1 / (60 + rank)
        features.append(f)
    return features


def rerank(rows, scores, limit):
    # Greedy maximal-marginal-relevance style selection with category/brand diversity.
    remaining = list(zip(rows, scores))
    categories, brands = Counter(), Counter()
    selected = []
    while remaining and len(selected) < limit:
        eligible = [i for i, (row, _) in enumerate(remaining) if categories[row.get("category0")] < 4]
        if not eligible:
            eligible = range(len(remaining))
        best = max(eligible, key=lambda i: float(remaining[i][1])
                   - .09 * categories[remaining[i][0].get("category0")]
                   - .04 * brands[remaining[i][0].get("brand")])
        row, score = remaining.pop(best)
        selected.append((row, float(score)))
        categories[row.get("category0")] += 1
        brands[row.get("brand")] += 1
    return selected


def hybrid_features(rows, payload, sources, features):
    """Scores from available candidate generators with explicit segment weights."""
    cold_weights = ({"content": .70, "popularity": .12, "trending": .08, "freshness": .10}
                    if payload["preferences"] else
                    {"popularity": .45, "trending": .35, "freshness": .20})
    weights = {
        "cold": cold_weights,
        "few": {"content": .50, "covis": .28, "popularity": .08, "trending": .06, "freshness": .08},
        "warm": {"content": .32, "covis": .24, "twotower": .18, "als": .12, "popularity": .05, "freshness": .09},
        "session": {"content": .34, "covis": .28, "gru": .20, "trending": .08, "freshness": .10},
    }[payload["segment"]]
    if payload.get("long_term_eligible") and int(payload.get("session_distinct_count", 0)) >= 3:
        weights = {"content": .28, "covis": .24, "gru": .16, "twotower": .14,
                   "als": .08, "trending": .04, "freshness": .06}
    now = datetime.now(timezone.utc)
    values = {name: [] for name in ("content", "covis", "als", "gru", "twotower", "popularity", "trending", "freshness")}
    for row in rows:
        key = row["item_id"]
        for name in ("content", "covis", "als", "gru", "twotower"):
            values[name].append(float(sources.get(name, {}).get(key, 0)))
        values["popularity"].append(math.log1p(payload["popularity"].get(key, 0)))
        values["trending"].append(math.log1p(payload["trending"].get(key, 0)))
        seen = row.get("last_seen_ts")
        age_days = max(0, (now.replace(tzinfo=None) - seen).days) if seen else 365
        values["freshness"].append(math.exp(-age_days / 365))
    normalized = {}
    for name, scores in values.items():
        lo, hi = min(scores, default=0), max(scores, default=0)
        normalized[name] = [(score - lo) / (hi - lo) if hi > lo else 0 for score in scores]
    active_weights = {name: weight for name, weight in weights.items()
                      if name == "freshness" or any(normalized[name])}
    total = sum(active_weights.values()) or 1
    return [sum(weight * normalized[name][i] for name, weight in active_weights.items()) / total
            + .04 * min(features[i]["source_count"], 3) / 3 for i in range(len(rows))]


def recommend(payload):
    from scripts.online_models import score_retrievers, rank_candidates
    rows = catalog_candidates(payload)
    source_scores = {"content": {row["item_id"]: row["content_score"] for row in rows if row["content_score"] > 0},
                     "covis": {row["item_id"]: float(payload["covis"][row["item_id"]]) for row in rows if row["item_id"] in payload["covis"]}}
    model_scores, status = score_retrievers(rows, payload)
    source_scores.update(model_scores)
    features = features_for(rows, payload, source_scores)
    baseline = hybrid_features(rows, payload, source_scores, features)
    scores, ranker, rank_status = rank_candidates(features, baseline)
    status.update(rank_status)
    selected = rerank(rows, scores, payload["limit"])
    items = []
    for row, score in selected:
        items.append(dict(id=str(row["item_id"]), name=row["name"], price=row["price"], originalPrice=row["price"],
            discount=0, rating=0, soldCount=0, image="", images=[], c0_name=row.get("category0") or "",
            c0_display=row.get("category0") or "", c1_name=row.get("category1") or "", c2_name=row.get("category2") or "",
            brand=row.get("brand") or "", condition=row.get("condition") or "", inStock=True,
            stockCount=0, stockKnown=False, description="Chưa có mô tả sản phẩm.", currency="USD", source="merrec", score=score))
    sources = [name for name, values in source_scores.items() if values]
    sources += ["popularity_trending" if payload["popularity"] else "catalog_freshness"]
    return dict(request_id=str(uuid.uuid4()), context=payload["context"], trigger_item_id=payload.get("trigger_item_id"),
        model_name="+".join(sources) + "/" + ranker, segment=payload["segment"], candidate_count=len(rows),
        model_status=status, ranker=ranker, degraded=any(value not in ("ready", "not_applicable", "not_in_use") for value in status.values()), items=items)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    if payload.get("operation") == "item":
        import duckdb
        path = os.environ.get("MERREC_CATALOG_PATH", str(ROOT / "data/processed/recommender/serving/item_catalog_full.parquet"))
        with duckdb.connect() as db:
            db.execute("SET threads=2")
            query = db.execute("SELECT item_id, product_id, name, price, category0, category1, category2, brand, condition, shipper FROM read_parquet(?) WHERE item_id = ? AND price > 0 AND name IS NOT NULL LIMIT 1", [path, payload["item_id"]])
            row = query.fetchone()
            result = dict(zip([column[0] for column in query.description], row)) if row else None
            if result:
                result["price"] = float(result["price"])
    else:
        result = recommend(payload)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
