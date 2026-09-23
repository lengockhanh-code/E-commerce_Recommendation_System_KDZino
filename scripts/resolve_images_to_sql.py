"""Search all catalog parts; checkpoint in SQLite and stream an importable SQL file."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from pathlib import Path
import sqlite3
import time
import unicodedata
import uuid
from urllib.parse import urlparse

from ddgs import DDGS
if __package__:
    from .merrec_image_resolver.resolve_images_on_demand import (
        build_query, candidate_score, iter_csv_rows_from_path,
    )
else:
    from merrec_image_resolver.resolve_images_on_demand import (
        build_query, candidate_score, iter_csv_rows_from_path,
    )

CATALOG_DIR = Path(__file__).resolve().parents[1] / "data" / "catalog"

SCHEMA = "CREATE TABLE IF NOT EXISTS product_images (item_id INTEGER PRIMARY KEY, image_url TEXT, status TEXT, match_score REAL, source_page TEXT);\n"


def group_key(row, args):
    # Preserve punctuation and Unicode so distinct model names are not merged.
    fields = ("name", "brand_name", "c0_name", "c1_name", "c2_name", "color")
    values = [" ".join(unicodedata.normalize("NFC", str(row.get(k) or "")).casefold().split())
              for k in fields]
    return json.dumps([args.min_score, args.max_results, *values], ensure_ascii=False)


def sql_row(row):
    def literal(value):
        if value is None:
            return "NULL"
        if isinstance(value, (int, float)):
            return str(value)
        return "'" + str(value).replace("'", "''") + "'"
    return (f"DELETE FROM product_images WHERE item_id={int(row[0])};\n"
            "INSERT INTO product_images (item_id,image_url,status,match_score,source_page) VALUES ("
            + ",".join(map(literal, row)) + ");\n")


def resolve(row, args):
    query = build_query(row)
    if not query:
        return (None, "no_match", 0.0, None, None)
    for attempt in range(3):
        try:
            candidates = DDGS(timeout=15).images(
                query=query, region="us-en", safesearch="moderate",
                max_results=args.max_results, backend="auto") or []
            candidates = [c for c in candidates if
                          urlparse(c.get("image") or "").scheme in ("http", "https")
                          and urlparse(c.get("image") or "").netloc]
            if not candidates:
                return (None, "no_match", 0.0, None, None)
            best = max(candidates, key=lambda c: candidate_score(row, c))
            score = candidate_score(row, best)
            return (best["image"] if score >= args.min_score else None,
                    "ok" if score >= args.min_score else "no_match",
                    score, best.get("url"), None)
        except Exception as exc:
            error = str(exc)
            time.sleep(attempt + 1)
    return (None, "error", 0.0, None, error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default=str(CATALOG_DIR / "catalog_split"))
    parser.add_argument("--db", default=str(CATALOG_DIR / "product_images.db"))
    parser.add_argument("--sql", default=str(CATALOG_DIR / "product_images.sql"))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--min-score", type=float, default=55)
    parser.add_argument("--limit", type=int, default=0, help="0 = all products")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.limit < 0:
        parser.error("workers must be positive and limit must be nonnegative")
    files = sorted(Path(args.input_dir).glob("product_catalog_part_*.csv"))
    if not files:
        files = sorted(Path(args.input_dir).glob("product_catalog_part_*.zip"))
    if not files and not args.export_only:
        parser.error("No catalog parts found")
    if Path(args.db).resolve() == Path(args.sql).resolve():
        parser.error("DB and SQL must use different paths")
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(SCHEMA)
    con.execute("CREATE TABLE IF NOT EXISTS search_details (item_id INTEGER PRIMARY KEY, signature TEXT, error TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS signature_idx ON search_details(signature)")
    con.execute("CREATE TABLE IF NOT EXISTS image_groups (signature TEXT PRIMARY KEY, image_url TEXT, status TEXT, match_score REAL, source_page TEXT, error TEXT, run_id TEXT)")
    con.commit()
    # Rebuild from committed checkpoints, including after an interrupted write.
    with open(args.sql, "w", encoding="utf-8", newline="\n") as output:
        output.write("-- SQLite SQL. Missing URLs are NULL. status=error can be retried.\n" + SCHEMA)
        for row in con.execute("SELECT item_id,image_url,status,match_score,source_page FROM product_images"):
            output.write(sql_row(row))
        output.flush()
        if args.export_only:
            con.close()
            return
        counts = {"ok": 0, "no_match": 0, "error": 0}
        processed = 0
        consecutive_errors = 0
        pending = deque()
        in_flight = {}
        run_id = uuid.uuid4().hex
        searched_groups = 0
        reused_items = 0

        def save_next():
            nonlocal processed, consecutive_errors
            item_id, signature, future, cached = pending.popleft()
            result = cached if future is None else future.result()
            url, status, score, source, error = result
            record = (item_id, url, status, score, source)
            con.execute("INSERT OR REPLACE INTO product_images VALUES (?,?,?,?,?)", record)
            con.execute("INSERT OR REPLACE INTO search_details VALUES (?,?,?)", (item_id, signature, error))
            con.execute("INSERT OR REPLACE INTO image_groups VALUES (?,?,?,?,?,?,?)",
                        (signature, url, status, score, source, error, run_id))
            in_flight.pop(signature, None)
            con.commit()
            output.write(sql_row(record))
            output.flush()
            processed += 1
            counts[status] += 1
            consecutive_errors = consecutive_errors + 1 if status == "error" else 0
            print(f"processed={processed} counts={counts} searched_groups={searched_groups} reused_items={reused_items} item_id={item_id} status={status}", flush=True)
            if error:
                print(f"search_error={error}", flush=True)
            if consecutive_errors >= 20:
                raise RuntimeError("Stopped after 20 consecutive search errors. Fix connection and rerun; error rows will be retried.")

        try:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for path in files:
                    print(f"Reading {path.name}", flush=True)
                    for row in iter_csv_rows_from_path(path):
                        if args.limit and processed + len(pending) >= args.limit:
                            break
                        item_id = int(row["item_id"])
                        signature = group_key(row, args)
                        existing = con.execute("SELECT image_url,status,match_score,source_page FROM product_images WHERE item_id=?", (item_id,)).fetchone()
                        if existing and existing[1] != "error":
                            # Migrate committed results using the original CSV metadata,
                            # never the older punctuation-stripping signature.
                            con.execute("INSERT OR IGNORE INTO image_groups VALUES (?,?,?,?,?,?,?)",
                                        (signature, *existing, None, run_id))
                            con.commit()
                            continue
                        cached = con.execute("SELECT image_url,status,match_score,source_page,error FROM image_groups WHERE signature=? AND (status!='error' OR run_id=?)", (signature, run_id)).fetchone()
                        future = None
                        if cached:
                            reused_items += 1
                        elif signature in in_flight:
                            future = in_flight[signature]
                            reused_items += 1
                        else:
                            future = pool.submit(resolve, row, args)
                            in_flight[signature] = future
                            searched_groups += 1
                        pending.append((item_id, signature, future, cached))
                        if len(pending) >= args.workers * 2:
                            save_next()
                    if args.limit and processed + len(pending) >= args.limit:
                        break
                while pending:
                    save_next()
            print(f"DONE processed={processed} counts={counts} searched_groups={searched_groups} reused_items={reused_items} SQL={args.sql}", flush=True)
        finally:
            con.close()


if __name__ == "__main__":
    main()
