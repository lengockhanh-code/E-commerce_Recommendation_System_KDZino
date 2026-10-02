"""MerRec Recommendation Engine & Logging Pipeline

Generates contextual product recommendations (Home, Product Detail, Cart),
persists recommendation requests & rank positions in PostgreSQL,
and provides Content-Based Filtering & pluggable interface for trained ML models
operating on the full 30M+ product catalog.
"""

import json
import os
import re
from pathlib import Path
import sys
import uuid
import time
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
load_dotenv(ROOT / ".env")


def clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    return None if s.lower() in ("__unk__", "nan", "none", "null", "") else s


def product_dict(row):
    return dict(
        id=str(row["item_id"]),
        name=clean_str(row.get("name")),
        price=float(row.get("price") or 0.0),
        originalPrice=float(row.get("price") or 0.0),
        discount=0,
        rating=0,
        soldCount=0,
        image="",
        images=[],
        c0_name=clean_str(row.get("category0")),
        c0_display=clean_str(row.get("category0")),
        c1_name=clean_str(row.get("category1")),
        c2_name=clean_str(row.get("category2")),
        brand=clean_str(row.get("brand")),
        condition=clean_str(row.get("condition")),
        shipper=clean_str(row.get("shipper")),
        size=clean_str(row.get("size")),
        color=clean_str(row.get("color")),
        inStock=bool(row.get("is_active", True)),
        stockCount=99,
        stockKnown=False,
        description=clean_str(row.get("description")),
        currency="USD",
        source="merrec"
    )


def fetch_metadata_similar_duckdb(trigger_item_id: str, limit: int = 12):
    """
    Performs high-precision Content-Based Filtering using DuckDB over the full 30,000,000+ item catalog.
    Extracts text tokens from target name & matches title, brand, category0/1/2, and price proximity.
    """
    import duckdb

    catalog_path = ROOT / "data" / "processed" / "recommender" / "serving" / "item_catalog_full.parquet"
    if not catalog_path.exists():
        catalog_path = ROOT / "data" / "processed" / "recommender" / "serving" / "item_catalog_preview.parquet"

    con = duckdb.connect()
    parquet_str = catalog_path.as_posix()

    target_row = con.execute(f"""
        SELECT item_id, name, brand, category0, category1, category2, price
        FROM read_parquet('{parquet_str}')
        WHERE item_id = '{trigger_item_id}'
        LIMIT 1
    """).fetchone()

    if not target_row:
        popular_rows = con.execute(f"""
            SELECT item_id, name, brand, category0, category1, category2, price, condition, shipper
            FROM read_parquet('{parquet_str}')
            WHERE item_id != '{trigger_item_id}'
            LIMIT {limit}
        """).fetchall()
        cols = ["item_id", "name", "brand", "category0", "category1", "category2", "price", "condition", "shipper"]
        return [product_dict(dict(zip(cols, r))) for r in popular_rows], "parquet_popular_v1"

    t_id, t_name, t_brand, t_c0, t_c1, t_c2, t_price = (
        target_row[0], target_row[1], target_row[2], target_row[3], target_row[4], target_row[5], target_row[6]
    )

    t_name_str = (t_name or "").lower()
    stopwords = {"and", "the", "for", "with", "out", "new", "set", "pack", "lot", "from", "that", "this", "other", "arts", "crafts", "a", "an", "in", "on", "of", "to", "is", "it"}
    tokens = [w for w in re.findall(r'\w+', t_name_str) if len(w) > 2 and w not in stopwords]

    token_cases = []
    token_likes = []
    for t in tokens:
        t_clean = t.replace("'", "''")
        token_cases.append(f"(CASE WHEN name ILIKE '%{t_clean}%' THEN 0.3 ELSE 0 END)")
        token_likes.append(f"name ILIKE '%{t_clean}%'")

    token_score_expr = " + ".join(token_cases) if token_cases else "0.0"
    like_where_clause = " OR ".join(token_likes) if token_likes else "1=1"

    c0_clean = (t_c0 or "").replace("'", "''")
    c1_clean = (t_c1 or "").replace("'", "''")
    c2_clean = (t_c2 or "").replace("'", "''")
    brand_clean = (t_brand or "").replace("'", "''")

    query = f"""
        SELECT item_id, name, brand, category0, category1, category2, price, condition, shipper,
               (
                   (CASE WHEN category2 = '{c2_clean}' AND category2 != 'Other Arts & Crafts' THEN 0.35 ELSE 0 END) +
                   (CASE WHEN category1 = '{c1_clean}' THEN 0.25 ELSE 0 END) +
                   (CASE WHEN category0 = '{c0_clean}' THEN 0.10 ELSE 0 END) +
                   (CASE WHEN brand = '{brand_clean}' AND brand != '__UNK__' THEN 0.25 ELSE 0 END) +
                   (CASE WHEN price > 0 AND abs(price - {float(t_price or 0.0)}) / {max(float(t_price or 1.0), 1.0)} <= 0.30 THEN 0.15 ELSE 0 END) +
                   {token_score_expr}
               ) as sim_score
        FROM read_parquet('{parquet_str}')
        WHERE item_id != '{t_id}'
          AND ({like_where_clause})
        ORDER BY sim_score DESC, item_id
        LIMIT {limit}
    """

    rows = con.execute(query).fetchall()
    cols = ["item_id", "name", "brand", "category0", "category1", "category2", "price", "condition", "shipper", "sim_score"]

    results = []
    for r in rows:
        d = dict(zip(cols, r))
        p = product_dict(d)
        p["score"] = float(d["sim_score"] or 0.5)
        results.append(p)

    # If results is fewer than limit, fill up with same category1 products
    if len(results) < limit:
        needed = limit - len(results)
        existing_ids = set(p["id"] for p in results)
        existing_ids.add(str(t_id))

        fallback_query = f"""
            SELECT item_id, name, brand, category0, category1, category2, price, condition, shipper
            FROM read_parquet('{parquet_str}')
            WHERE category0 = '{c0_clean}' AND item_id != '{t_id}'
            LIMIT {needed + 10}
        """
        f_rows = con.execute(fallback_query).fetchall()
        f_cols = ["item_id", "name", "brand", "category0", "category1", "category2", "price", "condition", "shipper"]
        for fr in f_rows:
            fd = dict(zip(f_cols, fr))
            if fd["item_id"] not in existing_ids:
                p = product_dict(fd)
                p["score"] = 0.1
                results.append(p)
                if len(results) >= limit:
                    break

    return results[:limit], "content_based_v1"


def get_recommendations_postgres(dsn, context="home", trigger_item_id=None, user_id=None, session_id=None, limit=12):
    import psycopg

    req_id = str(uuid.uuid4())
    model_used = "content_based_v1" if context in ("product_detail", "cart") else "overall_popular_v1"
    items = []

    if context in ("product_detail", "cart") and trigger_item_id:
        items, model_used = fetch_metadata_similar_duckdb(trigger_item_id, limit=limit)
    else:
        try:
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT p.item_id, p.product_id, p.name, p.price, p.category0, p.category1, p.category2,
                               p.brand, p.condition, p.size, p.color, p.shipper, p.is_active,
                               COALESCE(e.event_cnt, 0) as event_cnt
                        FROM products p
                        LEFT JOIN (
                            SELECT item_id, COUNT(*) as event_cnt
                            FROM user_events
                            GROUP BY item_id
                        ) e ON p.item_id = e.item_id
                        WHERE p.is_active = TRUE AND p.name IS NOT NULL AND p.price > 0
                        ORDER BY event_cnt DESC, p.item_id
                        LIMIT %s
                    """, (limit,))
                    rows = cur.fetchall()
                    cols = [desc[0] for desc in cur.description]
                    for idx, r in enumerate(rows):
                        d = dict(zip(cols, r))
                        p = product_dict(d)
                        p["score"] = round(1.0 - (idx * 0.05), 2)
                        items.append(p)
        except Exception:
            items = []

    if not items and trigger_item_id:
        items, model_used = fetch_metadata_similar_duckdb(trigger_item_id, limit=limit)

    # Sync recommended items to PostgreSQL & log recommendation request
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                # Sync product records into products table if not present
                p_rows = []
                for it in items:
                    p_rows.append((
                        it["id"], it["name"], it["price"],
                        it.get("c0_name"), it.get("c1_name"), it.get("c2_name"),
                        it.get("brand"), it.get("condition"), it.get("size"), it.get("color"),
                        it.get("shipper"), True
                    ))
                if p_rows:
                    cur.executemany("""
                        INSERT INTO products (
                            item_id, name, price, category0, category1, category2,
                            brand, condition, size, color, shipper, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (item_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            price = EXCLUDED.price,
                            category0 = EXCLUDED.category0,
                            category1 = EXCLUDED.category1,
                            category2 = EXCLUDED.category2,
                            brand = EXCLUDED.brand
                    """, p_rows)

                # Log recommendation request
                cur.execute("""
                    INSERT INTO recommendation_requests (
                        id, user_id, session_id, context, trigger_item_id, model_name
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (req_id, user_id, session_id, context, trigger_item_id, model_used))

                rec_item_rows = []
                for idx, item in enumerate(items):
                    rank_pos = idx + 1
                    score = item.get("score", 0.5)
                    rec_item_rows.append((req_id, item["id"], rank_pos, score, model_used))

                if rec_item_rows:
                    cur.executemany("""
                        INSERT INTO recommendation_items (
                            request_id, item_id, rank_position, score, source_model
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (request_id, item_id) DO NOTHING
                    """, rec_item_rows)

                conn.commit()
    except Exception as e:
        print(f"Warning: Failed to log recommendation request to DB: {e}", file=sys.stderr)

    return {
        "request_id": req_id,
        "context": context,
        "trigger_item_id": trigger_item_id,
        "model_name": model_used,
        "items": items
    }


def get_recommendations_parquet(context="home", trigger_item_id=None, limit=12):
    if trigger_item_id and context in ("product_detail", "cart"):
        items, model_name = fetch_metadata_similar_duckdb(trigger_item_id, limit=limit)
    else:
        items, _ = fetch_metadata_similar_duckdb(trigger_item_id or "100003961", limit=limit)
        model_name = "parquet_baseline_v1"

    return {
        "request_id": str(uuid.uuid4()),
        "context": context,
        "trigger_item_id": trigger_item_id,
        "model_name": model_name,
        "items": items
    }


def get_recommendations(context="home", trigger_item_id=None, user_id=None, session_id=None, limit=12):
    dsn = os.environ.get("DATABASE_URL")
    force_parquet = os.environ.get("MERREC_FORCE_PARQUET") == "1"

    if dsn and not force_parquet:
        return get_recommendations_postgres(dsn, context, trigger_item_id, user_id, session_id, limit)
    else:
        return get_recommendations_parquet(context, trigger_item_id, limit)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ctx = sys.argv[1] if len(sys.argv) > 1 else "home"
    trig = sys.argv[2] if len(sys.argv) > 2 else None
    res = get_recommendations(context=ctx, trigger_item_id=trig, limit=12)
    print(json.dumps(res, ensure_ascii=False))
