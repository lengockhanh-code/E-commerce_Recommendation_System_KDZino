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


def attach_product_images(items, dsn=None):
    if not items:
        return items
    item_ids = [str(it["id"]) for it in items if isinstance(it, dict) and "id" in it]
    if not item_ids:
        return items

    image_map = {}

    if dsn:
        try:
            import psycopg
            with psycopg.connect(dsn, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT item_id, image_url
                        FROM product_images
                        WHERE item_id = ANY(%s) AND image_url != 'EMPTY_NO_IMAGE'
                        ORDER BY is_primary DESC, match_score DESC
                    """, (item_ids,))
                    for row in cur.fetchall():
                        iid, url = str(row[0]), str(row[1])
                        if iid not in image_map:
                            image_map[iid] = []
                        if url not in image_map[iid]:
                            image_map[iid].append(url)
        except Exception:
            pass

    missing_ids = [iid for iid in item_ids if iid not in image_map]
    if missing_ids:
        try:
            import sqlite3
            db_path = ROOT / "data/storefront/product_images.sqlite3"
            if db_path.exists():
                with sqlite3.connect(db_path, timeout=3) as db:
                    placeholders = ",".join(["?"] * len(missing_ids))
                    rows = db.execute(f"""
                        SELECT item_id, url
                        FROM verified_images
                        WHERE item_id IN ({placeholders}) AND url != 'EMPTY_NO_IMAGE'
                        ORDER BY position ASC
                    """, missing_ids).fetchall()
                    for row in rows:
                        iid, url = str(row[0]), str(row[1])
                        if iid not in image_map:
                            image_map[iid] = []
                        if url not in image_map[iid]:
                            image_map[iid].append(url)
        except Exception:
            pass

    for it in items:
        if isinstance(it, dict) and "id" in it:
            iid = str(it.get("id"))
            urls = image_map.get(iid, [])
            if urls:
                it["image"] = urls[0]
                it["images"] = urls

    return items



def fetch_detail_similar(trigger_item_id: str, limit: int = 12):
    from similar_products import fetch_similar, MODEL_NAME
    rows = fetch_similar(trigger_item_id, limit)
    return [dict(product_dict(row), score=float(row["title_matches"])) for row in rows], MODEL_NAME


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


def fetch_metadata_similar_fast(dsn, trigger_item_id: str, limit: int = 12):
    """Fast candidate retrieval from PostgreSQL products table with DuckDB and popular backfill."""
    import psycopg
    items = []
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT item_id, name, price, category0, category1, category2, brand, condition, size, color, shipper, is_active
                    FROM products WHERE item_id = %s
                """, (trigger_item_id,))
                target = cur.fetchone()
                if not target:
                    try:
                        from storefront_catalog import read_catalog_parquet
                        parquet_rows = read_catalog_parquet(trigger_item_id)
                        if parquet_rows:
                            p = parquet_rows[0]
                            cur.execute("""
                                INSERT INTO products (
                                    item_id, name, price, category0, category1, category2,
                                    brand, condition, size, color, shipper, is_active
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                                ON CONFLICT (item_id) DO NOTHING
                            """, (
                                p["id"], p.get("name"), float(p.get("price") or 0.0),
                                p.get("c0_name"), p.get("c1_name"), p.get("c2_name"),
                                p.get("brand"), p.get("condition"), p.get("size"), p.get("color"),
                                p.get("shipper")
                            ))
                            conn.commit()
                            cur.execute("""
                                SELECT item_id, name, price, category0, category1, category2, brand, condition, size, color, shipper, is_active
                                FROM products WHERE item_id = %s
                            """, (trigger_item_id,))
                            target = cur.fetchone()
                    except Exception:
                        pass

                if target:
                    t_id, t_name, t_price, t_c0, t_c1, t_c2, t_brand = target[0], target[1], target[2], target[3], target[4], target[5], target[6]
                    cur.execute("""
                        SELECT item_id, name, price, category0, category1, category2, brand, condition, size, color, shipper, is_active
                        FROM products
                        WHERE is_active = TRUE AND item_id != %s AND (
                            (category1 IS NOT NULL AND category1 = %s)
                            OR (category0 IS NOT NULL AND category0 = %s)
                            OR (brand IS NOT NULL AND brand != '__UNK__' AND brand = %s)
                        )
                        ORDER BY
                            (CASE WHEN category1 IS NOT NULL AND category1 = %s THEN 2.0 ELSE 0 END +
                             CASE WHEN category0 IS NOT NULL AND category0 = %s THEN 1.0 ELSE 0 END +
                             CASE WHEN brand IS NOT NULL AND brand != '__UNK__' AND brand = %s THEN 1.5 ELSE 0 END) DESC,
                            price DESC
                        LIMIT %s
                    """, (t_id, t_c1, t_c0, t_brand, t_c1, t_c0, t_brand, limit))
                    cols = [desc[0] for desc in cur.description]
                    for idx, row in enumerate(cur.fetchall()):
                        d = dict(zip(cols, row))
                        p = product_dict(d)
                        p["score"] = round(1.0 - (idx * 0.05), 2)
                        items.append(p)
    except Exception:
        items = []

    if len(items) < limit:
        try:
            duck_items, _ = fetch_metadata_similar_duckdb(trigger_item_id, limit=limit)
            existing = set(it["id"] for it in items)
            for dit in duck_items:
                if dit["id"] not in existing and len(items) < limit:
                    items.append(dit)
                    existing.add(dit["id"])
        except Exception:
            pass

    if len(items) < limit:
        try:
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    existing_list = list(set([it["id"] for it in items] + [str(trigger_item_id)]))
                    cur.execute("""
                        SELECT item_id, name, price, category0, category1, category2, brand, condition, size, color, shipper, is_active
                        FROM products
                        WHERE is_active = TRUE AND item_id NOT IN (SELECT unnest(%s::text[]))
                        ORDER BY price DESC
                        LIMIT %s
                    """, (existing_list, limit - len(items)))
                    cols = [desc[0] for desc in cur.description]
                    for idx, row in enumerate(cur.fetchall()):
                        d = dict(zip(cols, row))
                        p = product_dict(d)
                        p["score"] = 0.1
                        items.append(p)
        except Exception:
            pass

    return items[:limit], "content_based_v1"


def get_recommendations_postgres(dsn, context="home", trigger_item_id=None, user_id=None, session_id=None, limit=12):
    import psycopg

    req_id = str(uuid.uuid4())
    model_used = "content_based_v1" if context in ("product_detail", "cart") else "overall_popular_v1"
    items = []

    if context == "product_detail":
        items, model_used = fetch_detail_similar(trigger_item_id, limit=limit)
        if len(items) < limit and trigger_item_id:
            fast_items, _ = fetch_metadata_similar_fast(dsn, trigger_item_id, limit=limit)
            existing = set(it["id"] for it in items)
            for fit in fast_items:
                if fit["id"] not in existing and len(items) < limit:
                    items.append(fit)
                    existing.add(fit["id"])
    elif trigger_item_id:
        items, model_used = fetch_metadata_similar_fast(dsn, trigger_item_id, limit=limit)
    else:
        recent_interacted_items = []
        try:
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    if user_id or session_id:
                        cur.execute("""
                            SELECT item_id
                            FROM user_events
                            WHERE (
                                (user_id IS NOT NULL AND user_id = %s)
                                OR (session_id IS NOT NULL AND session_id = %s)
                                OR (metadata->>'client_session_id' = %s)
                            )
                            ORDER BY event_time DESC
                            LIMIT 10
                        """, (
                            str(user_id) if user_id else None,
                            str(session_id) if session_id else None,
                            str(session_id) if session_id else None
                        ))
                        recent_rows = cur.fetchall()
                        recent_interacted_items = [r[0] for r in recent_rows if r[0]]
        except Exception:
            recent_interacted_items = []

        if recent_interacted_items:
            latest_seed = recent_interacted_items[0]
            rec_items, _ = fetch_metadata_similar_fast(dsn, latest_seed, limit=limit + len(recent_interacted_items))
            interacted_set = set(recent_interacted_items)
            filtered = [it for it in rec_items if it["id"] not in interacted_set]
            items = filtered[:limit] if filtered else rec_items[:limit]
            model_used = "session_personalized_v1"
        else:
            # Cold-start: diverse mix across top distinct categories
            try:
                with psycopg.connect(dsn, connect_timeout=5) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            WITH RankedProducts AS (
                                SELECT p.item_id, p.product_id, p.name, p.price, p.category0, p.category1, p.category2,
                                       p.brand, p.condition, p.size, p.color, p.shipper, p.is_active,
                                       COALESCE(e.event_cnt, 0) as event_cnt,
                                       ROW_NUMBER() OVER (
                                           PARTITION BY COALESCE(p.category0, 'Other')
                                           ORDER BY COALESCE(e.event_cnt, 0) DESC, p.price DESC
                                       ) as cat_rank
                                FROM products p
                                LEFT JOIN (
                                    SELECT item_id, COUNT(*) as event_cnt
                                    FROM user_events
                                    GROUP BY item_id
                                ) e ON p.item_id = e.item_id
                                WHERE p.is_active = TRUE AND p.name IS NOT NULL AND p.price > 0
                            )
                            SELECT item_id, product_id, name, price, category0, category1, category2,
                                   brand, condition, size, color, shipper, is_active, event_cnt
                            FROM RankedProducts
                            ORDER BY cat_rank ASC, event_cnt DESC, price DESC
                            LIMIT %s
                        """, (limit,))
                        rows = cur.fetchall()
                        cols = [desc[0] for desc in cur.description]
                        for idx, r in enumerate(rows):
                            d = dict(zip(cols, r))
                            p = product_dict(d)
                            p["score"] = round(1.0 - (idx * 0.05), 2)
                            items.append(p)
                        model_used = "diverse_category_coldstart_v1"
            except Exception:
                items = []

    if not items and trigger_item_id and context != "product_detail":
        items, model_used = fetch_metadata_similar_duckdb(trigger_item_id, limit=limit)

    # Sync recommended items to PostgreSQL & log recommendation request
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                p_rows = []
                seen_p_ids = set()
                for it in items:
                    iid = it.get("id")
                    if not iid or iid in seen_p_ids:
                        continue
                    seen_p_ids.add(iid)
                    p_rows.append((
                        iid, it["name"], it["price"],
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

                # Ensure valid user_id
                v_user_id = None
                if user_id:
                    try:
                        cur.execute("SELECT id FROM users WHERE id = %s", (str(user_id),))
                        if cur.fetchone():
                            v_user_id = str(user_id)
                    except Exception:
                        v_user_id = None

                # Ensure valid session_id in user_sessions
                v_session_id = None
                if session_id:
                    try:
                        sess_uuid = str(uuid.UUID(str(session_id)))
                        cur.execute("""
                            INSERT INTO user_sessions (id, user_id, device_type, source)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING
                        """, (sess_uuid, v_user_id, "web", context))
                        v_session_id = sess_uuid
                    except Exception:
                        v_session_id = None

                v_trig = None
                if trigger_item_id:
                    try:
                        cur.execute("SELECT item_id FROM products WHERE item_id = %s", (str(trigger_item_id),))
                        if cur.fetchone():
                            v_trig = str(trigger_item_id)
                    except Exception:
                        v_trig = None

                cur.execute("""
                    INSERT INTO recommendation_requests (
                        id, user_id, session_id, context, trigger_item_id, model_name
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (req_id, v_user_id, v_session_id, context, v_trig, model_used))

                rec_item_rows = []
                seen_rec_item_ids = set()
                for idx, item in enumerate(items):
                    iid = item.get("id")
                    if not iid or iid in seen_rec_item_ids:
                        continue
                    seen_rec_item_ids.add(iid)
                    rank_pos = idx + 1
                    score = item.get("score", 0.5)
                    rec_item_rows.append((req_id, iid, rank_pos, score, model_used))

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
        "items": attach_product_images(items, dsn)
    }


def get_recommendations_parquet(context="home", trigger_item_id=None, limit=12):
    if context == "product_detail":
        items, model_name = fetch_detail_similar(trigger_item_id, limit=limit)
    elif trigger_item_id and context == "cart":
        items, model_name = fetch_metadata_similar_duckdb(trigger_item_id, limit=limit)
    else:
        items, _ = fetch_metadata_similar_duckdb(trigger_item_id or "100003961", limit=limit)
        model_name = "parquet_baseline_v1"

    dsn = os.environ.get("DATABASE_URL")
    return {
        "request_id": str(uuid.uuid4()),
        "context": context,
        "trigger_item_id": trigger_item_id,
        "model_name": model_name,
        "items": attach_product_images(items, dsn)
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
