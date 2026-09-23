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
        rows = db.execute("SELECT url,title,source,score FROM verified_images WHERE item_id=? ORDER BY position", (item_id,)).fetchall()
    return [dict(zip(("url", "title", "source", "score"), row)) for row in rows]


def save_images(item, images):
    if not images:
        return
    with connect() as db:
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
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.port not in (None, 443):
        return False
    addresses = socket.getaddrinfo(parsed.hostname, 443)
    return bool(addresses) and all(ipaddress.ip_address(address[4][0]).is_global for address in addresses)


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


def resolve_images(item, search):
    saved = read_images(item["id"])
    if saved:
        sync_postgres()
        return saved
    candidates = search(item)
    with ThreadPoolExecutor(max_workers=5) as pool:
        valid = list(pool.map(valid_image, candidates))
    images = [image for image, ok in zip(candidates, valid) if ok]
    save_images(item, images)
    sync_postgres()
    return images
