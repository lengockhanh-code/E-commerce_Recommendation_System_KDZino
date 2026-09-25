"""Read the MerRec serving catalog and resolve illustrative images on demand.

Invoked by the Next.js server, never by the browser directly.
"""
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path(os.environ.get("MERREC_CATALOG_PATH", ROOT / "data/processed/recommender/serving/item_catalog_full.parquet"))


def clean(value):
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in ("__unk__", "nan", "none", "null") else text


def product(row):
    return dict(id=str(row["item_id"]), name=clean(row["name"]), price=row["price"],
                originalPrice=row["price"], discount=0, rating=0, soldCount=0,
                image="", images=[], c0_name=clean(row["category0"]),
                c0_display=clean(row["category0"]), c1_name=clean(row["category1"]),
                c2_name=clean(row["category2"]), brand=clean(row["brand"]),
                condition=clean(row["condition"]), shipper=clean(row["shipper"]),
                size=clean(row.get("size")), color=clean(row.get("color")),
                inStock=True, stockCount=0, stockKnown=False,
                description=clean(row.get("description")),
                currency="USD", source="merrec")


def read_catalog(item_id=None):
    import duckdb
    with duckdb.connect() as db:
        db.execute("SET threads=2")
        if item_id:
            result = db.execute("SELECT * FROM read_parquet(?) WHERE item_id = ? LIMIT 1", [str(CATALOG), item_id])
        else:
            result = db.execute("""SELECT * FROM read_parquet(?)
                WHERE name IS NOT NULL AND price > 0
                QUALIFY row_number() OVER (PARTITION BY category0 ORDER BY item_id) <= 8
                ORDER BY category0, item_id""", [str(CATALOG)])
        columns = [col[0] for col in result.description]
        return [product(dict(zip(columns, row))) for row in result.fetchall()]


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
