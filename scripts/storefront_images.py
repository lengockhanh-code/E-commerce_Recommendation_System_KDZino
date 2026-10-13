"""Verified image URLs with durable local storage and a PostgreSQL outbox."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import BytesIO
import ipaddress
import json
import os
from pathlib import Path
import socket
import sqlite3
import time
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data/storefront/product_images.sqlite3"
EMPTY_RESULT_TTL_SECONDS = 60


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.execute("""CREATE TABLE IF NOT EXISTS verified_images (
        item_id TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL,
        source TEXT NOT NULL, score REAL NOT NULL, position INTEGER NOT NULL,
        verified_at REAL NOT NULL, PRIMARY KEY(item_id, url))""")
    db.execute("""CREATE TABLE IF NOT EXISTS image_outbox (
        item_id TEXT PRIMARY KEY, product_json TEXT NOT NULL)""")
    try:
        with db:
            yield db
    finally:
        db.close()


def read_images(item_id):
    with connect() as db:
        rows = db.execute("SELECT url,title,source,score,verified_at FROM verified_images WHERE item_id=? ORDER BY position", (item_id,)).fetchall()
    if rows:
        actual_images = [row for row in rows if row[0] != "EMPTY_NO_IMAGE"]
        if not actual_images:
            return [] if time.time() - max(row[4] for row in rows) < EMPTY_RESULT_TTL_SECONDS else None
        return [dict(zip(("url", "title", "source", "score"), row)) for row in actual_images]
    return None


def save_images(item, images):
    with connect() as db:
        if not images:
            db.execute("INSERT OR REPLACE INTO verified_images VALUES (?,?,?,?,?,?,?)",
                       (item["id"], "EMPTY_NO_IMAGE", "None", "None", 0.0, 0, time.time()))
            return
        db.execute("DELETE FROM verified_images WHERE item_id=? AND url='EMPTY_NO_IMAGE'", (item["id"],))
        for position, image in enumerate(images):
            db.execute("INSERT OR REPLACE INTO verified_images VALUES (?,?,?,?,?,?,?)",
                       (item["id"], image["url"], image.get("title", ""), image.get("source", ""), image.get("score", 0), position, time.time()))
        db.execute("INSERT OR REPLACE INTO image_outbox VALUES (?,?)", (item["id"], json.dumps(item)))


def sync_postgres():
    # A failed database connection must never lose images or prevent the page loading.
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return False
    try:
        import psycopg
        with connect() as local:
            pending = local.execute("SELECT item_id,product_json FROM image_outbox LIMIT 20").fetchall()
            if not pending:
                return True
            with psycopg.connect(dsn, connect_timeout=2, options="-c statement_timeout=3000") as db:
                for item_id, payload in pending:
                    item = json.loads(payload)
                    # Serialize writers for the same product, without requiring a new unique index.
                    db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (item_id,))
                    db.execute("""INSERT INTO products (item_id,name,price,category0,category1,category2,brand,condition,shipper)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (item_id) DO NOTHING""",
                        (item_id,item["name"],item["price"],item.get("c0_name"),item.get("c1_name"),item.get("c2_name"),item.get("brand"),item.get("condition"),item.get("shipper")))
                    for image in read_images(item_id):
                        db.execute("""INSERT INTO product_images (item_id,image_url,source,match_score,is_primary)
                            SELECT %s,%s,%s,%s,FALSE WHERE NOT EXISTS
                            (SELECT 1 FROM product_images WHERE item_id=%s AND image_url=%s)""",
                            (item_id,image["url"],image["source"],image["score"],item_id,image["url"]))
                db.commit()
            # Remove only the exact outbox payload committed above.
            local.executemany("DELETE FROM image_outbox WHERE item_id=? AND product_json=?", pending)
        return True
    except Exception:
        return False


def public_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 443):
            return False
        try:
            addresses = socket.getaddrinfo(parsed.hostname, 443)
            return bool(addresses) and all(ipaddress.ip_address(address[4][0]).is_global for address in addresses)
        except Exception:
            return False
    except Exception:
        return False


def valid_image(candidate):
    import requests
    from PIL import Image
    try:
        url = candidate["url"]
        start = time.monotonic()
        for _ in range(4):
            if not public_url(url):
                return False
            with requests.get(url, stream=True, timeout=(3, 4), allow_redirects=False,
                              headers={"User-Agent": "Mozilla/5.0"}) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("Location", ""))
                    continue
                if response.status_code != 200 or not response.headers.get("Content-Type", "").lower().startswith("image/"):
                    return False
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 8 * 1024 * 1024 or time.monotonic() - start > 8:
                        return False
                with Image.open(BytesIO(content)) as image:
                    if image.width < 40 or image.height < 40:
                        return False
                    image.verify()
                return True
        return False
    except Exception:
        return False


def read_postgres_images(item_id):
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return None
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=2) as db:
            with db.cursor() as cur:
                cur.execute("""
                    SELECT image_url, image_url, source, match_score
                    FROM product_images
                    WHERE item_id = %s AND image_url != 'EMPTY_NO_IMAGE'
                    ORDER BY is_primary DESC, match_score DESC
                """, (item_id,))
                rows = cur.fetchall()
                if rows:
                    return [dict(zip(("url", "title", "source", "score"), r)) for r in rows]
    except Exception:
        pass
    return None


def reference_images(item):
    """Verified same-type illustrations, explicitly not images of this item.

    Never store these in verified_images/product_images under the target ID.
    """
    import re
    try:
        from scripts.similar_products import title_tokens, TYPE_PATTERNS
    except ModuleNotFoundError:
        from similar_products import title_tokens, TYPE_PATTERNS
    tokens = set(title_tokens(item.get("name"), item.get("brand")))
    types = [pattern for pattern in TYPE_PATTERNS if re.search(pattern, str(item.get("name", "")).lower())]
    categories = [item.get(key) for key in ("c0_name", "c1_name", "c2_name")]
    dsn = os.environ.get("DATABASE_URL")
    # An unspecified product type is too broad for an illustrative fallback.
    if not dsn or len(tokens) < 2 or not types or not all(categories):
        return []
    try:
        import psycopg
        token_list = sorted(tokens)[:12]
        score = " + ".join("CASE WHEN p.name ILIKE %s THEN 1 ELSE 0 END" for _ in token_list)
        with psycopg.connect(dsn, connect_timeout=2, options="-c statement_timeout=3000") as db:
            rows = db.execute(f"""SELECT p.item_id,p.name,p.brand,i.image_url,i.source,({score}) AS matches
                FROM products p JOIN product_images i ON i.item_id=p.item_id
                WHERE p.category0=%s AND p.category1=%s AND p.category2=%s AND p.item_id!=%s
                  AND i.image_url LIKE 'https://%%'
                ORDER BY matches DESC,i.is_primary DESC,i.match_score DESC LIMIT 30""",
                (*[f"%{token}%" for token in token_list], *categories, item["id"])).fetchall()
        candidates, seen = [], set()
        for source_id, name, brand, url, source, _ in rows:
            common = tokens & set(title_tokens(name, brand))
            if len(common) < 2 or not all(re.search(pattern, name.lower()) for pattern in types) or url in seen:
                continue
            seen.add(url)
            candidates.append({"url": url, "title": name, "source": source or "",
                               "reference": True, "reference_item_id": str(source_id), "score": 0})
            if len(candidates) == 3:
                break
        with ThreadPoolExecutor(max_workers=3) as pool:
            verified = list(pool.map(valid_image, candidates))
        return [image for image, ok in zip(candidates, verified) if ok][:1]
    except Exception:
        return []


def resolve_images(item, search):
    saved = read_images(item["id"])
    if saved is not None:
        return saved
    pg_images = read_postgres_images(item["id"])
    if pg_images:
        save_images(item, pg_images)
        return pg_images
    try:
        candidates = search(item)
    except Exception as error:
        references = reference_images(item)
        if references:
            return references
        raise RuntimeError("Image search is temporarily unavailable") from error
    if not candidates:
        references = reference_images(item)
        if references:
            return references
        save_images(item, [])
        return []
    with ThreadPoolExecutor(max_workers=5) as pool:
        valid = list(pool.map(valid_image, candidates))
    images = [image for image, ok in zip(candidates, valid) if ok]
    if not images:
        references = reference_images(item)
        if references:
            return references
    save_images(item, images)
    if images:
        sync_postgres()
    return images
