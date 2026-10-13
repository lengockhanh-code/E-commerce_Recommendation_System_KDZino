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


def interest_profile(history, metadata, decay_hours):
    """Time/action weighted metadata profile; repeated click+view is one item."""
    per_item = {}
    weights = {"view": 1.0, "click": 1.0, "like": 2.5, "unlike": -2.5,
               "cart": 3.0, "offer": 2.0, "buy_start": 2.5, "buy_comp": 4.0}
    for event in history:
        if event["event_type"] not in weights or event["item_id"] not in metadata:
            continue
        value = weights[event["event_type"]] * math.exp(-max(0.0, float(event.get("age_hours", 0))) / decay_hours)
        previous = per_item.get(event["item_id"], 0)
        per_item[event["item_id"]] = value if value < 0 or previous < 0 else max(previous, value)
    result = {key: Counter() for key in ("category0", "category1", "category2", "brand")}
    for item_id, weight in per_item.items():
        row = metadata[item_id]
        c0, c1, brand, c2 = row[1], row[2], row[3], row[5]
        c0 = c0 if c0 and c0 != "__UNK__" else None
        if c0: result["category0"][c0] += weight
        if c1 and c1 != "__UNK__": result["category1"][(c0, c1)] += weight
        if c2 and c2 != "__UNK__": result["category2"][(c0, c1, c2)] += weight
        if brand and brand != "__UNK__": result["brand"][(c0, brand)] += weight
    result["distinct_items"] = sum(value > 0 for value in per_item.values())
    return result


def interest_affinity(row, profile):
    c0, c1, c2, brand = (row.get(name) for name in ("category0", "category1", "category2", "brand"))
    keys = {"category0": c0, "category1": (c0, c1), "category2": (c0, c1, c2), "brand": (c0, brand)}
    total = 0.0
    for name, weight in (("category0", .20), ("category1", .45), ("category2", .25), ("brand", .10)):
        counts = profile[name]
        mass = sum(max(0.0, value) for value in counts.values())
        if mass:
            key = keys[name]
            value = counts[key]
            if isinstance(key, tuple) and key[0] is not None:
                value += counts[(None, *key[1:])]
            total += weight * max(0.0, value) / mass
    return total


def interest_focus(profile):
    if profile["distinct_items"] < 2:
        return None
    for name, fields in (("category1", ("category0", "category1")), ("category0", ("category0",))):
        positive = {key: value for key, value in profile[name].items() if value > 0}
        if positive:
            key = max(positive, key=positive.get)
            if positive[key] / sum(positive.values()) >= .65:
                if isinstance(key, tuple) and key[0] is None:
                    return dict(fields=("category1",), values=(key[1],))
                return dict(fields=fields, values=key if isinstance(key, tuple) else (key,))
    return None


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
        seed_rows = db.execute("SELECT item_id, category0, category1, brand, name, category2 FROM catalog WHERE item_id IN (SELECT unnest(?))", [seeds]).fetchall()
        seed_by_id = {row[0]: row for row in seed_rows}
        categories += [row[1] for row in seed_rows if row[1] and row[1] != "__UNK__"]
        subcats = [row[2] for row in seed_rows if row[2] and row[2] != "__UNK__"]
        leaf_categories = list({row[5] for row in seed_rows if row[5] and row[5] != "__UNK__"})
        brands = [row[3] for row in seed_rows if row[3] and row[3] != "__UNK__"]
        import re
        tokens = list(dict.fromkeys(word.lower() for row in seed_rows for word in re.findall(r"\w+", row[4] or "") if len(word) > 3))[:30]
        excluded = list(set(payload.get("exclude", []) + seeds + [event["item_id"] for event in payload.get("history", [])]))
        # Bound expensive title tokenization to a metadata candidate pool. Doing
        # regexp/list intersections on all 30M catalog rows exceeds web timeouts.
        result = db.execute("""WITH metadata_pool AS (
            SELECT *,
            (CASE WHEN list_contains(?, category0) THEN 1.0 ELSE 0 END +
             CASE WHEN list_contains(?, category1) THEN 0.6 ELSE 0 END +
             CASE WHEN list_contains(?, brand) THEN 0.4 ELSE 0 END) AS metadata_score
            FROM catalog WHERE name IS NOT NULL AND price > 0
              AND NOT list_contains(?, item_id)
              AND (NOT ? OR list_contains(?, category0) OR list_contains(?, category1) OR list_contains(?, brand))
              AND (NOT ? OR list_contains(?, category2))
            ORDER BY metadata_score DESC, last_seen_ts DESC NULLS LAST, item_id
            LIMIT 10000
        ) SELECT *, metadata_score +
             0.1 * len(list_intersect(regexp_split_to_array(lower(coalesce(name, '')), '\\W+'), ?)) AS content_score
            FROM metadata_pool
            ORDER BY content_score DESC, last_seen_ts DESC NULLS LAST, item_id
            LIMIT 1000""", [categories, subcats, brands, excluded,
                             bool(categories or subcats or brands), categories, subcats, brands,
                             bool(leaf_categories), leaf_categories, tokens])
        columns = [c[0] for c in result.description]
        rows = {str(row[0]): dict(zip(columns, row)) for row in result.fetchall()}
        for row in rows.values():
            row["content_score"] = float(row["content_score"])
            row["price"] = float(row["price"])
        extra_ids = list(dict.fromkeys(list(payload["covis"]) + list(payload.get("twotower_recall_scores", {}))
            + list(payload["popularity"]) + list(payload["trending"])))[:1500]
        if extra_ids:
            result = db.execute("SELECT *, 0.0 AS content_score FROM catalog WHERE item_id IN (SELECT unnest(?)) AND item_id NOT IN (SELECT unnest(?)) AND name IS NOT NULL AND price > 0", [extra_ids, excluded])
            columns = [c[0] for c in result.description]
            for values in result.fetchall():
                row = dict(zip(columns, values))
                row["price"] = float(row["price"])
                row["content_score"] = float(row.get("category0") in categories) + .6 * (row.get("category1") in subcats) + .4 * (row.get("brand") in brands)
                rows.setdefault(str(row["item_id"]), row)
        # Home preferences express affinity rather than a hard catalog filter.
        # Replenish an exhausted personalized pool with real, unseen catalog items.
        # This is an intentional retrieval source, not a dependency-error fallback.
        if payload.get("context") == "home" and not rows:
            result = db.execute("""SELECT *, 0.0 AS content_score FROM catalog
                WHERE name IS NOT NULL AND price > 0 AND NOT list_contains(?, item_id)
                ORDER BY last_seen_ts DESC NULLS LAST, item_id LIMIT 300""",
                [excluded + list(rows)])
            columns = [c[0] for c in result.description]
            for values in result.fetchall():
                row = dict(zip(columns, values))
                row["price"] = float(row["price"])
                row["content_score"] = float(row.get("category0") in categories) + .6 * (row.get("category1") in subcats) + .4 * (row.get("brand") in brands)
                rows.setdefault(str(row["item_id"]), row)
        # Preserve stable preference independently of recent sequential intent.
        long_profile = interest_profile(payload.get("history", []), seed_by_id, 24 * 30)
        recent_events = payload.get("recent_history", [e for e in payload.get("history", []) if e.get("age_hours", 0) <= 24 * 7])
        recent_profile = interest_profile(recent_events, seed_by_id, 24)
        payload["interest_focus"] = interest_focus(recent_profile) if payload.get("context") == "home" else None
        for row in rows.values():
            row["long_term_score"] = interest_affinity(row, long_profile)
            row["recent_score"] = interest_affinity(row, recent_profile)
            row["content_score"] += 1.5 * row["long_term_score"] + 3.0 * row["recent_score"]
        # Preserve union of sources while bounding the candidate pool.
        prioritized = sorted(rows.values(), key=lambda r: (
            r["content_score"] + math.log1p(payload["covis"].get(r["item_id"], 0)) +
            .1 * math.log1p(payload["popularity"].get(r["item_id"], 0))), reverse=True)
        if payload.get("context") != "home" and payload["preferences"] and not payload.get("history") and not seeds:
            prioritized = [row for row in prioritized if row["content_score"] > 0]
        ann_ids = set(payload.get("twotower_recall_scores", {}))
        reserved = [row for row in prioritized if row["item_id"] in ann_ids][:300]
        reserved_ids = {row["item_id"] for row in reserved}
        return reserved + [row for row in prioritized if row["item_id"] not in reserved_ids][:2000-len(reserved)]


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


def are_titles_too_similar(name1, name2):
    if not name1 or not name2:
        return False
    STOP_WORDS = {"a", "an", "and", "the", "for", "with", "from", "this", "that", "new", "used", "vintage", "old", "size", "set", "lot", "pack", "bundle", "sale", "free", "shipping", "brand", "by"}
    import re
    w1 = set(re.findall(r"\b[a-z0-9]{3,}\b", name1.lower())) - STOP_WORDS
    w2 = set(re.findall(r"\b[a-z0-9]{3,}\b", name2.lower())) - STOP_WORDS
    if not w1 or not w2:
        return False
    inter = len(w1 & w2)
    union = len(w1 | w2)
    jaccard = inter / union
    containment = inter / min(len(w1), len(w2))
    return jaccard >= 0.5 or (containment >= 0.75 and inter >= 2)


def rerank(rows, scores, limit, focus=None):
    # Greedy maximal-marginal-relevance style selection with category, brand, and title diversity.
    remaining = list(zip(rows, scores))
    categories, brands = Counter(), Counter()
    selected = []
    while remaining and len(selected) < limit:
        page = selected[-(len(selected) % 12):] if len(selected) % 12 else []
        if focus:
            def matches(row):
                return tuple(row.get(field) for field in focus["fields"]) == tuple(focus["values"])
            focused_count = sum(matches(row) for row, _ in page)
            wanted = [i for i, (row, _) in enumerate(remaining) if matches(row) == (focused_count < 9)]
        else:
            wanted = list(range(len(remaining)))
        if not wanted:
            wanted = list(range(len(remaining)))
        eligible = [
            i for i in wanted
            if (focus or categories[remaining[i][0].get("category0")] < 4)
            and not any(are_titles_too_similar(remaining[i][0].get("name"), row.get("name")) for row, _ in page)
        ]
        if not eligible:
            eligible = [i for i in wanted if focus or categories[remaining[i][0].get("category0")] < 4]
        if not eligible:
            eligible = wanted
        page_categories = Counter(row.get("category0") for row, _ in page) if focus else categories
        page_brands = Counter(row.get("brand") for row, _ in page) if focus else brands
        best = max(eligible, key=lambda i: float(remaining[i][1])
                   - (.015 if focus else .09) * page_categories[remaining[i][0].get("category0")]
                   - .04 * page_brands[remaining[i][0].get("brand")])
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
        "few": {"recent": .38, "long_term": .12, "content": .20, "covis": .18, "popularity": .04, "trending": .03, "freshness": .05},
        "warm": {"recent": .22, "long_term": .17, "content": .18, "covis": .15, "twotower": .14, "als": .09, "freshness": .05},
        "session": {"recent": .40, "long_term": .12, "content": .12, "covis": .14, "gru": .12, "trending": .04, "freshness": .06},
    }[payload["segment"]]
    if payload.get("long_term_eligible") and int(payload.get("recent_distinct_count", payload.get("session_distinct_count", 0))) >= 3:
        weights = {"recent": .32, "long_term": .14, "content": .10, "covis": .12, "gru": .14,
                   "twotower": .10, "als": .05, "freshness": .03}
    now = datetime.now(timezone.utc)
    values = {name: [] for name in ("content", "covis", "als", "gru", "twotower", "recent", "long_term", "popularity", "trending", "freshness")}
    for row in rows:
        key = row["item_id"]
        for name in ("content", "covis", "als", "gru", "twotower"):
            values[name].append(float(sources.get(name, {}).get(key, 0)))
        values["recent"].append(float(row.get("recent_score", 0)))
        values["long_term"].append(float(row.get("long_term_score", 0)))
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
    from scripts.online_models import score_retrievers, rank_candidates, retrievers_for, twotower_candidates
    if "twotower" in retrievers_for(payload):
        try:
            recall, recall_status = twotower_candidates(payload)
        except (ImportError, OSError, ValueError, RuntimeError, KeyError, IndexError):
            recall, recall_status = {}, "unavailable_or_incompatible"
        payload.update(twotower_recall_scores=recall, twotower_recall_status=recall_status)
    rows = catalog_candidates(payload)
    source_scores = {"content": {row["item_id"]: row["content_score"] for row in rows if row["content_score"] > 0},
                     "covis": {row["item_id"]: float(payload["covis"][row["item_id"]]) for row in rows if row["item_id"] in payload["covis"]}}
    model_scores, status = score_retrievers(rows, payload)
    source_scores.update(model_scores)
    features = features_for(rows, payload, source_scores)
    baseline = hybrid_features(rows, payload, source_scores, features)
    scores, ranker, rank_status = rank_candidates(features, baseline,
        configured_override=payload.get("ranker_override"), blend_weight=payload.get("blend_weight"),
        dcn_path=payload.get("dcn_path"))
    if rows and payload.get("ranker_override") and ranker != payload["ranker_override"]:
        raise RuntimeError("Experiment ranker unavailable")
    status.update(rank_status)
    selected = rerank(rows, scores, payload["limit"], payload.get("interest_focus"))
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
        retrieval_modes={"twotower": payload.get("twotower_query_mode")},
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
