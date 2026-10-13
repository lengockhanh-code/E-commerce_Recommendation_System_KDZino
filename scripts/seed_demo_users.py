"""Create repeatable local demo accounts from TRAIN histories; never reset accounts."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import sys
import uuid
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE_USERS = ("10000892", "10003043", "10008898")
PREFIX = "merrec-demo:"


def prepare():
    import duckdb
    with duckdb.connect(config={"threads": 2}) as db:
        db.read_parquet(str(ROOT / "training/evaluation/results/test_nextitem/test_next_item_history.parquet")).create_view("history")
        db.read_parquet(str(ROOT / "data/processed/recommender/serving/item_catalog_full.parquet")).create_view("catalog")
        db.read_parquet(str(ROOT / "artifacts/merrec_models/TwoTower/mappings/train_user_map.parquet")).create_view("users_map")
        result = db.execute("""WITH history_items AS (
            SELECT h.*, row_number() OVER (PARTITION BY h.user_id,h.item_id ORDER BY ts DESC,event_id) item_rank
            FROM history h JOIN users_map m ON h.user_id=CAST(m.user_id AS VARCHAR)
            WHERE lower(source_split)='train' AND h.user_id IN (SELECT unnest(?))
        ), ranked AS (
            SELECT h.*, row_number() OVER (PARTITION BY user_id ORDER BY ts DESC,item_id) history_rank
            FROM history_items h WHERE item_rank=1
        ) SELECT h.user_id,h.item_id,h.ts,h.event_id,c.name,c.price,c.category0,c.category1,
                 c.category2,c.brand,c.condition,c.shipper
          FROM ranked h JOIN catalog c ON CAST(c.item_id AS VARCHAR)=h.item_id
          WHERE history_rank<=30 ORDER BY h.user_id,h.ts,h.item_id""", [list(SOURCE_USERS)])
        columns = [col[0] for col in result.description]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    for user_id in SOURCE_USERS:
        if len([r for r in rows if r["user_id"] == user_id]) < 10:
            raise ValueError("Insufficient mapped TRAIN history for demo user")
    return rows


def seed(rows, credentials_path):
    import psycopg
    from psycopg.types.json import Jsonb
    from backend.src.security.hashing import hash_password
    dsn = os.environ["DATABASE_URL"]
    if urlparse(dsn).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Demo seeding is restricted to a local database")
    credentials = json.loads(credentials_path.read_text(encoding="utf-8")) if credentials_path.exists() else []
    with psycopg.connect(dsn, connect_timeout=5, options="-c statement_timeout=10000") as db:
        db.execute("SELECT pg_advisory_xact_lock(hashtext('merrec-demo-users-v1'))")
        for number, dataset_id in enumerate(SOURCE_USERS, 1):
            email = f"warm{number}@demo.merrec.example.com"
            account = next((a for a in credentials if a["email"] == email), None)
            existing = db.execute("SELECT u.id,a.provider_account_id FROM users u LEFT JOIN auth_accounts a ON a.user_id=u.id AND a.provider='local' WHERE u.email=%s", (email,)).fetchone()
            if existing and (not account or existing[1] != PREFIX + dataset_id):
                raise ValueError("Existing account is not owned by this seed; refusing to modify")
            if not account:
                account = {"email": email, "password": secrets.token_urlsafe(15), "dataset_user_id": dataset_id,
                           "user_id": str(uuid.uuid4()), "name": f"Demo Warm {number}"}
                credentials.append(account)
            if not existing:
                db.execute("INSERT INTO users(id,email,full_name,is_active,is_verified) VALUES (%s,%s,%s,TRUE,FALSE)",
                           (account["user_id"], email, account["name"]))
                db.execute("INSERT INTO auth_accounts(id,user_id,provider,provider_account_id,provider_email,password_hash) VALUES (%s,%s,'local',%s,%s,%s)",
                           (str(uuid.uuid4()), account["user_id"], PREFIX + dataset_id, email, hash_password(account["password"])))
            history = [r for r in rows if r["user_id"] == dataset_id]
            for position, row in enumerate(history):
                db.execute("""INSERT INTO products(item_id,name,price,category0,category1,category2,brand,condition,shipper)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(item_id) DO NOTHING""",
                    tuple(row[key] for key in ("item_id", "name", "price", "category0", "category1", "category2", "brand", "condition", "shipper")))
                event_key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"merrec-demo-v1/{dataset_id}/{row['item_id']}"))
                metadata = {"demo": True, "dataset_user_id": dataset_id, "source_split": "TRAIN",
                            "original_event_id": row["event_id"], "original_timestamp": row["ts"].isoformat(),
                            "note": "Demo view history reconstructed from TRAIN; timestamps shifted"}
                when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2, minutes=len(history)-position)
                db.execute("""INSERT INTO user_events(user_id,item_id,event_type,event_time,source_page,metadata,event_key)
                    VALUES (%s,%s,'view',%s,'demo_seed',%s,%s) ON CONFLICT(event_key) DO NOTHING""",
                    (account["user_id"], row["item_id"], when, Jsonb(metadata), event_key))
            categories = list(dict.fromkeys(row["category0"] for row in history))
            from backend.src.services.preferences_service import CATEGORIES
            preferences = [key for key, values in CATEGORIES.items() if any(c in values for c in categories)][:3]
            db.execute("INSERT INTO user_preferences(user_id,categories) VALUES (%s,%s) ON CONFLICT(user_id) DO NOTHING", (account["user_id"], Jsonb(preferences)))
        # Store credentials outside Git. Never emit passwords or hashes to logs.
        credentials_path.parent.mkdir(parents=True, exist_ok=True)
        credentials_path.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8")
    return [{"email": a["email"], "dataset_user_id": a["dataset_user_id"], "user_id": a["user_id"]} for a in credentials]


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows = prepare()
    if args.apply:
        print(json.dumps(seed(rows, ROOT / ".cache/demo-accounts.json")))
    else:
        print(json.dumps({u: sum(r["user_id"] == u for r in rows) for u in SOURCE_USERS}))
