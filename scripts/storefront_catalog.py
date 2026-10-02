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


def read_catalog(item_id=None):
    dsn = os.environ.get("DATABASE_URL")
    force_parquet = os.environ.get("MERREC_FORCE_PARQUET") == "1"

    if dsn and not force_parquet:
        try:
            rows = read_catalog_postgres(dsn, item_id)
            if rows:
                return rows
            if item_id:
                parquet_rows = read_catalog_parquet(item_id)
                if parquet_rows:
                    sync_single_product_postgres(dsn, parquet_rows[0])
                    return parquet_rows
            return rows
        except Exception:
            return read_catalog_parquet(item_id)
    else:
        return read_catalog_parquet(item_id)


def search_images(item):
    from ddgs import DDGS
    query = " ".join(dict.fromkeys(filter(None, [item["name"], item.get("brand"), item.get("c1_name")])))[:240]
    tokens = set(re.findall(r"\w+", item["name"].lower()))
    results = DDGS(timeout=12).images(query, max_results=12, safesearch="moderate")
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
        print(json.dumps(get_recommendations(context=ctx, trigger_item_id=trig, limit=limit), ensure_ascii=False))
    elif operation == "log-event":
        payload = json.load(sys.stdin)
        dsn = os.environ.get("DATABASE_URL")
        if dsn:
            import psycopg
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO user_events (
                            user_id, session_id, item_id, event_type, source_page,
                            recommendation_request_id, position, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        payload.get("user_id"), payload.get("session_id"), payload["item_id"],
                        payload["event_type"], payload.get("source_page"),
                        payload.get("recommendation_request_id"), payload.get("position"),
                        json.dumps(payload.get("metadata")) if payload.get("metadata") else None
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
