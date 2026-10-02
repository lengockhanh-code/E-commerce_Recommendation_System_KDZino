"""Sync product metadata from item_catalog_full.parquet into PostgreSQL.

Idempotent batch catalog synchronization script.
Reads metadata from dataset and updates PostgreSQL `products` table.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

CATALOG_DEFAULT = ROOT / "data/processed/recommender/serving/item_catalog_full.parquet"


def clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("__unk__", "nan", "none", "null", ""):
        return None
    return s


def clean_float(val):
    if val is None:
        return None
    try:
        f = float(val)
        return f if f >= 0 else None
    except (ValueError, TypeError):
        return None


def sync_catalog(catalog_path, dsn, batch_size=10000, limit=None, sync_deactivations=False):
    import duckdb
    import psycopg

    start_time = time.monotonic()
    catalog_file = Path(catalog_path)
    if not catalog_file.exists():
        raise FileNotFoundError(f"Catalog file not found: {catalog_file}")

    print(f"Opening catalog parquet: {catalog_file}")
    
    with duckdb.connect() as duck:
        duck.execute("SET threads=4")
        query = f"SELECT * FROM read_parquet('{catalog_file.as_posix()}')"
        if limit and limit > 0:
            query += f" LIMIT {int(limit)}"
        
        rel = duck.query(query)
        columns = [col[0] for col in rel.description]
        print(f"Catalog schema columns: {columns}")
        
        # Ensure database tables exist using migration SQL
        migration_file = ROOT / "database/migrations/001_initial_schema_and_constraints.sql"
        with psycopg.connect(dsn, connect_timeout=10) as conn:
            if migration_file.exists():
                print(f"Applying schema migration: {migration_file.name}")
                with conn.cursor() as cur:
                    cur.execute(migration_file.read_text(encoding="utf-8"))
                conn.commit()

        processed_ids = set()
        total_inserted_updated = 0

        # Fetch in chunks using duckdb fetchmany
        row_stream = rel.fetchmany(batch_size)
        batch_idx = 0

        with psycopg.connect(dsn, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                while row_stream:
                    batch_idx += 1
                    batch_tuples = []
                    for raw_row in row_stream:
                        row = dict(zip(columns, raw_row))
                        item_id = clean_str(row.get("item_id"))
                        if not item_id:
                            continue

                        processed_ids.add(item_id)
                        product_id = clean_str(row.get("product_id"))
                        name = clean_str(row.get("name"))
                        price = clean_float(row.get("price"))
                        category0 = clean_str(row.get("category0"))
                        category1 = clean_str(row.get("category1"))
                        category2 = clean_str(row.get("category2"))
                        brand = clean_str(row.get("brand"))
                        condition = clean_str(row.get("condition"))
                        shipper = clean_str(row.get("shipper"))
                        last_seen_ts = row.get("last_seen_ts")

                        batch_tuples.append((
                            item_id, product_id, name, price,
                            category0, category1, category2,
                            brand, condition, shipper, last_seen_ts
                        ))

                    if batch_tuples:
                        cur.executemany("""
                            INSERT INTO products (
                                item_id, product_id, name, price,
                                category0, category1, category2,
                                brand, condition, shipper, last_seen_ts, is_active
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                            ON CONFLICT (item_id) DO UPDATE SET
                                product_id = EXCLUDED.product_id,
                                name = EXCLUDED.name,
                                price = EXCLUDED.price,
                                category0 = EXCLUDED.category0,
                                category1 = EXCLUDED.category1,
                                category2 = EXCLUDED.category2,
                                brand = EXCLUDED.brand,
                                condition = EXCLUDED.condition,
                                shipper = EXCLUDED.shipper,
                                last_seen_ts = EXCLUDED.last_seen_ts,
                                is_active = TRUE
                        """, batch_tuples)
                        conn.commit()

                    total_inserted_updated += len(batch_tuples)
                    print(f"Batch {batch_idx}: Upserted {len(batch_tuples)} products (Total: {total_inserted_updated})")
                    row_stream = rel.fetchmany(batch_size)

                # Soft mark products missing from dataset if requested
                deactivated_count = 0
                if sync_deactivations and processed_ids:
                    print("Checking for products to soft-deactivate...")
                    cur.execute("""
                        UPDATE products
                        SET is_active = FALSE
                        WHERE item_id NOT IN %s AND is_active = TRUE
                    """, (tuple(processed_ids),))
                    deactivated_count = cur.rowcount
                    conn.commit()

        elapsed = time.monotonic() - start_time
        summary = {
            "status": "success",
            "total_processed": len(processed_ids),
            "upserted": total_inserted_updated,
            "deactivated": deactivated_count if sync_deactivations else 0,
            "elapsed_seconds": round(elapsed, 2)
        }
        print(f"Catalog Sync Completed successfully in {summary['elapsed_seconds']}s")
        print(json.dumps(summary, indent=2))
        return summary


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Sync parquet catalog to PostgreSQL")
    parser.add_argument("--catalog", default=os.environ.get("MERREC_CATALOG_PATH", str(CATALOG_DEFAULT)))
    parser.add_argument("--batch-size", type=int, default=10000)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sync-deactivations", action="store_true")

    args = parser.parse_args()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    sync_catalog(
        catalog_path=args.catalog,
        dsn=dsn,
        batch_size=args.batch_size,
        limit=args.limit,
        sync_deactivations=args.sync_deactivations
    )
