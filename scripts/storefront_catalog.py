"""Read the MerRec serving catalog from PostgreSQL or parquet on demand.

Invoked by Next.js server functions and route handlers.
"""
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

CATALOG = Path(os.environ.get("MERREC_CATALOG_PATH", ROOT / "data/processed/recommender/serving/item_catalog_full.parquet"))


def clean(value):
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in ("__unk__", "nan", "none", "null") else text


def product(row):
    return dict(
        id=str(row["item_id"]),
        name=clean(row.get("name")),
        price=float(row.get("price") or 0.0),
        originalPrice=float(row.get("price") or 0.0),
        discount=0,
        rating=0,
        soldCount=0,
        image="",
        images=[],
        c0_name=clean(row.get("category0")),
        c0_display=clean(row.get("category0")),
        c1_name=clean(row.get("category1")),
        c2_name=clean(row.get("category2")),
        brand=clean(row.get("brand")),
        condition=clean(row.get("condition")),
        shipper=clean(row.get("shipper")),
        size=clean(row.get("size")),
        color=clean(row.get("color")),
        inStock=bool(row.get("is_active", True)),
        stockCount=99,
        stockKnown=False,
        description=clean(row.get("description")),
        currency="USD",
        source="merrec"
    )


def read_catalog_postgres(dsn, item_id=None):
    import psycopg
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            if item_id:
                cur.execute("""
                    SELECT item_id, product_id, name, price, category0, category1, category2,
                           brand, condition, size, color, shipper, is_active
                    FROM products
                    WHERE item_id = %s AND is_active = TRUE
                    LIMIT 1
                """, (str(item_id),))
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return [product(dict(zip(cols, r))) for r in rows]
            else:
                cur.execute("""
                    WITH ranked AS (
                        SELECT item_id, product_id, name, price, category0, category1, category2,
                               brand, condition, size, color, shipper, is_active,
                               ROW_NUMBER() OVER (PARTITION BY category0 ORDER BY item_id) as rn
                        FROM products
                        WHERE is_active = TRUE AND name IS NOT NULL AND price > 0
                    )
                    SELECT item_id, product_id, name, price, category0, category1, category2,
                           brand, condition, size, color, shipper, is_active
                    FROM ranked
                    WHERE rn <= 8
                    ORDER BY category0, item_id
                """)
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return [product(dict(zip(cols, r))) for r in rows]


def read_catalog_parquet(item_id=None):
    import duckdb
    with duckdb.connect() as db:
        db.execute("SET threads=2")
        if item_id:
            result = db.execute("SELECT * FROM read_parquet(?) WHERE item_id = ? LIMIT 1", [str(CATALOG), str(item_id)])
        else:
            result = db.execute("""SELECT * FROM read_parquet(?)
                WHERE name IS NOT NULL AND price > 0
                QUALIFY row_number() OVER (PARTITION BY category0 ORDER BY item_id) <= 8
                ORDER BY category0, item_id""", [str(CATALOG)])
        columns = [col[0] for col in result.description]
        return [product(dict(zip(columns, row))) for row in result.fetchall()]


def sync_single_product_postgres(dsn, p):
    import psycopg
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("""
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
                """, (
                    str(p["id"]), p.get("name"), float(p.get("price") or 0.0),
                    p.get("c0_name"), p.get("c1_name"), p.get("c2_name"),
                    p.get("brand"), p.get("condition"), p.get("size"), p.get("color"),
                    p.get("shipper"), True
                ))
                conn.commit()
    except Exception:
        pass


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


def read_catalog(item_id=None):
    dsn = os.environ.get("DATABASE_URL")
    force_parquet = os.environ.get("MERREC_FORCE_PARQUET") == "1"

    rows = []
    if dsn and not force_parquet:
        try:
            rows = read_catalog_postgres(dsn, item_id)
            if not rows and item_id:
                parquet_rows = read_catalog_parquet(item_id)
                if parquet_rows:
                    sync_single_product_postgres(dsn, parquet_rows[0])
                    rows = parquet_rows
        except Exception:
            rows = read_catalog_parquet(item_id)
    else:
        rows = read_catalog_parquet(item_id)

    return attach_product_images(rows, dsn)


def search_images(item):
    from ddgs import DDGS
    # Broad categories and noisy catalog brands can overwhelm the actual title.
    query = item["name"][:240]
    tokens = set(re.findall(r"\w+", item["name"].lower()))
    results = []
    failures = 0
    # Explicit backends: auto groups both engines under the same provider and
    # can stop after Bing fails. Keep retries bounded within the bridge budget.
    for backend in ("bing", "duckduckgo"):
        try:
            results = DDGS(timeout=5).images(query, backend=backend, max_results=12, safesearch="moderate")
            if results:
                break
        except Exception:
            failures += 1
            print(f"image_search_failed backend={backend}", file=sys.stderr)
    if not results and failures:
        raise RuntimeError("Image search providers unavailable")
    images, seen = [], set()
    for result in results:
        url = result.get("image", "")
        parsed = urlparse(url)
        title_tokens = set(re.findall(r"\w+", result.get("title", "").lower()))
        if parsed.scheme != "https" or not parsed.hostname or url in seen:
            continue
        score = len(tokens & title_tokens) / max(1, len(tokens))
        if score < 0.3:
            continue
        seen.add(url)
        images.append(dict(url=url, title=result.get("title", ""), source=result.get("url", ""), score=score))
    return sorted(images, key=lambda image: image["score"], reverse=True)[:5]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    operation = sys.argv[1]
    if operation == "export":
        target = ROOT / "frontend/src/lib/catalog-preview.json"
        target.write_text(json.dumps(read_catalog(), ensure_ascii=False), encoding="utf-8")
        print(str(target))
    elif operation == "detail":
        rows = read_catalog(sys.argv[2])
        print(json.dumps(rows[0] if rows else None, ensure_ascii=False, allow_nan=False))
    elif operation == "images":
        from storefront_images import resolve_images
        print(json.dumps(resolve_images(json.load(sys.stdin), search_images), ensure_ascii=False))
    elif operation == "sync-images":
        from storefront_images import sync_postgres
        print(json.dumps({"synced": sync_postgres()}))
    elif operation == "recommendations":
        from recommendation_engine import get_recommendations
        ctx = sys.argv[2] if len(sys.argv) > 2 else "home"
        trig = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "null" else None
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 12
        sess = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != "null" else None
        usr = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != "null" else None
        print(json.dumps(get_recommendations(context=ctx, trigger_item_id=trig, user_id=usr, session_id=sess, limit=limit), ensure_ascii=False))
    elif operation == "log-event":
        payload = json.load(sys.stdin)
        dsn = os.environ.get("DATABASE_URL")
        if dsn:
            import psycopg
            item_id = str(payload.get("item_id", "")).strip()
            raw_event_type = str(payload.get("event_type", "view"))
            event_type_map = {
                "click": "view",
                "view": "view",
                "view_item": "view",
                "like": "like",
                "unlike": "like",
                "cart": "cart",
                "add_to_cart": "cart",
                "offer": "offer",
                "offer_make": "offer",
                "buy_start": "buy_start",
                "buy_comp": "buy_comp",
                "purchase": "buy_comp",
            }
            event_type = event_type_map.get(raw_event_type, "view")
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    if item_id:
                        cur.execute("SELECT item_id FROM products WHERE item_id = %s", (item_id,))
                        if not cur.fetchone():
                            parquet_rows = read_catalog_parquet(item_id)
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
                            else:
                                cur.execute("""
                                    INSERT INTO products (item_id, name, price, is_active)
                                    VALUES (%s, %s, 0.0, TRUE)
                                    ON CONFLICT (item_id) DO NOTHING
                                """, (item_id, "Sản phẩm"))

                    valid_user_id = None
                    raw_user_id = payload.get("user_id")
                    if raw_user_id:
                        try:
                            cur.execute("SELECT id FROM users WHERE id = %s", (str(raw_user_id),))
                            if cur.fetchone():
                                valid_user_id = str(raw_user_id)
                        except Exception:
                            valid_user_id = None

                    valid_session_id = None
                    raw_session_id = payload.get("session_id")
                    if raw_session_id:
                        try:
                            import uuid as _uuid
                            sess_uuid = str(_uuid.UUID(str(raw_session_id)))
                            cur.execute("""
                                INSERT INTO user_sessions (id, user_id, device_type, source)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (id) DO NOTHING
                            """, (sess_uuid, valid_user_id, "web", payload.get("source_page", "storefront")))
                            valid_session_id = sess_uuid
                        except Exception:
                            valid_session_id = None

                    valid_rec_id = None
                    raw_rec_id = payload.get("recommendation_request_id")
                    if raw_rec_id:
                        try:
                            cur.execute("SELECT id FROM recommendation_requests WHERE id = %s", (str(raw_rec_id),))
                            if cur.fetchone():
                                valid_rec_id = str(raw_rec_id)
                        except Exception:
                            valid_rec_id = None

                    # Dataset interaction format alignment
                    dataset_event_id_map = {
                        "view": "item_view",
                        "click": "item_view",
                        "like": "item_like",
                        "unlike": "item_unlike",
                        "cart": "item_add_to_cart_tap",
                        "add_to_cart": "item_add_to_cart_tap",
                        "offer": "offer_make",
                        "buy_start": "buy_start",
                        "buy_comp": "buy_comp",
                        "purchase": "buy_comp"
                    }
                    dataset_weights = {
                        "view": 1.0, "like": 2.5, "cart": 3.0, "offer": 2.0, "buy_start": 2.5, "buy_comp": 4.0
                    }
                    event_id = dataset_event_id_map.get(raw_event_type, "item_view")
                    event_weight = dataset_weights.get(event_type, 1.0)
                    is_strong = 1 if event_type in ("like", "cart", "offer", "buy_start", "buy_comp") else 0
                    is_purch = 1 if event_type == "buy_comp" else 0

                    cur.execute("""
                        SELECT name, price, category0, category1, category2, brand, condition, shipper
                        FROM products WHERE item_id = %s
                    """, (item_id,))
                    p_info = cur.fetchone()

                    metadata = payload.get("metadata") or payload.get("extra_data") or {}
                    if not isinstance(metadata, dict):
                        metadata = {"raw": metadata}
                    if raw_session_id:
                        metadata["client_session_id"] = str(raw_session_id)
                    if raw_rec_id and not valid_rec_id:
                        metadata["client_rec_id"] = str(raw_rec_id)

                    metadata.update({
                        "event_id": event_id,
                        "event_group": event_type,
                        "event_weight": event_weight,
                        "is_strong_positive": is_strong,
                        "is_purchase": is_purch,
                        "client_event_type": raw_event_type,
                    })
                    if p_info:
                        metadata.update({
                            "name": p_info[0],
                            "price": float(p_info[1] or 0.0),
                            "category0": p_info[2],
                            "category1": p_info[3],
                            "category2": p_info[4],
                            "brand": p_info[5],
                            "condition": p_info[6],
                            "shipper": p_info[7],
                        })

                    cur.execute("""
                        INSERT INTO user_events (
                            user_id, session_id, item_id, event_type, source_page,
                            recommendation_request_id, position, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        valid_user_id, valid_session_id, item_id,
                        event_type, payload.get("source_page"),
                        valid_rec_id, payload.get("position"),
                        json.dumps(metadata) if metadata else None
                    ))
                    conn.commit()
            print(json.dumps({"status": "logged"}))
        else:
            print(json.dumps({"status": "skipped_no_db"}))
    elif operation == "create-order":
        import time, uuid
        payload = json.load(sys.stdin)
        dsn = os.environ.get("DATABASE_URL")
        if dsn:
            import psycopg
            order_id = str(uuid.uuid4())
            user_id = payload.get("user_id")
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    # 1. Resolve or create user in users table
                    valid_user_id = None
                    if user_id:
                        try:
                            cur.execute("SELECT id FROM users WHERE id = %s", (str(user_id),))
                            row = cur.fetchone()
                            if row:
                                valid_user_id = str(row[0])
                        except Exception:
                            valid_user_id = None

                    if not valid_user_id:
                        guest_email = "guest_checkout@kdzino.local"
                        cur.execute("SELECT id FROM users WHERE email = %s", (guest_email,))
                        row = cur.fetchone()
                        if row:
                            valid_user_id = str(row[0])
                        else:
                            guest_id = str(uuid.uuid4())
                            cur.execute(
                                "INSERT INTO users (id, email, username, full_name, is_active) VALUES (%s, %s, %s, %s, TRUE)",
                                (guest_id, guest_email, "guest_checkout", "Khách hàng")
                            )
                            valid_user_id = guest_id

                    # 2. Ensure every order item exists in products table
                    for item in payload.get("items", []):
                        item_id = str(item["item_id"])
                        cur.execute("SELECT item_id FROM products WHERE item_id = %s", (item_id,))
                        if not cur.fetchone():
                            parquet_rows = read_catalog_parquet(item_id)
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
                            else:
                                cur.execute("""
                                    INSERT INTO products (item_id, name, price, is_active)
                                    VALUES (%s, %s, %s, TRUE)
                                    ON CONFLICT (item_id) DO NOTHING
                                """, (item_id, item.get("product_name", "Sản phẩm"), float(item.get("unit_price", 0))))

                    # 3. Create order
                    cur.execute("""
                        INSERT INTO orders (id, user_id, status, total_amount, shipping_address, payment_method)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        order_id, valid_user_id, "pending",
                        float(payload.get("total_amount", 0)),
                        json.dumps(payload.get("shipping_address")),
                        payload.get("payment_method", "cod")
                    ))

                    # 4. Insert order items
                    for item in payload.get("items", []):
                        cur.execute("""
                            INSERT INTO order_items (order_id, item_id, product_name, quantity, unit_price)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            order_id, str(item["item_id"]), item.get("product_name", ""),
                            int(item.get("quantity", 1)), float(item.get("unit_price", 0))
                        ))
                    conn.commit()
            print(json.dumps({"status": "created", "order_id": order_id}))
        else:
            print(json.dumps({"status": "local_mock", "order_id": f"local-{int(time.time())}"}))
    elif operation == "get-orders":
        user_id = sys.argv[2] if len(sys.argv) > 2 else None
        dsn = os.environ.get("DATABASE_URL")
        orders = []
        if dsn and user_id:
            import psycopg
            try:
                with psycopg.connect(dsn, connect_timeout=5) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id, user_id, status, total_amount, shipping_address, payment_method, created_at
                            FROM orders
                            WHERE user_id = %s
                            ORDER BY created_at DESC
                        """, (str(user_id),))
                        order_rows = cur.fetchall()
                        for o_row in order_rows:
                            o_id = str(o_row[0])
                            cur.execute("""
                                SELECT id, item_id, product_name, quantity, unit_price
                                FROM order_items
                                WHERE order_id = %s
                            """, (o_id,))
                            items = [
                                dict(id=i[0], item_id=i[1], product_name=i[2], quantity=i[3], unit_price=i[4])
                                for i in cur.fetchall()
                            ]
                            orders.append(dict(
                                id=o_id,
                                user_id=str(o_row[1]),
                                status=o_row[2],
                                total_amount=o_row[3],
                                shipping_address=o_row[4],
                                payment_method=o_row[5],
                                created_at=o_row[6].isoformat() if o_row[6] else None,
                                items=items
                            ))
            except Exception:
                orders = []
        print(json.dumps(orders, ensure_ascii=False))
