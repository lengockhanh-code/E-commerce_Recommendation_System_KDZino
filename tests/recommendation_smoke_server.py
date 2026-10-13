"""Isolated HTTP boundary for browser smoke tests; never opens production DB."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
fixture = ROOT / "training/evaluation/results/ab_browser_smoke_20261012"
fixture.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + str(fixture / "fixture.sqlite")
os.environ["MERREC_AB_ENABLED"] = "1"
os.environ["MERREC_CATALOG_PATH"] = str(fixture / "catalog.parquet")

import duckdb
from backend.src.main import app
from backend.src.database.connection import Base, engine, SessionLocal, get_db
from backend.src.services import recommendation_experiment, personalization_service

# Small blocks let the browser cross several retrieval boundaries quickly.
recommendation_experiment.SNAPSHOT_SIZE = 24
personalization_service.SNAPSHOT_SIZE = 24

# Only this explicitly named disposable fixture is initialized here.
assert engine.url.get_backend_name() == "sqlite" and "ab_browser_smoke_20261012" in str(engine.url)
Base.metadata.create_all(engine)
with duckdb.connect() as db:
    db.execute("""COPY (SELECT CAST(i AS VARCHAR) AS item_id, CAST(i AS VARCHAR) AS product_id,
        'Product ' || i AS name, 10.0+i AS price, CASE WHEN i<40 THEN 'Electronics' ELSE 'Beauty' END AS category0,
        'Demo' AS category1, 'Test' AS category2, 'Brand' AS brand, 'Good' AS condition, 'seller' AS shipper,
        TIMESTAMP '2026-01-01' + i * INTERVAL '1 day' AS last_seen_ts FROM range(80) t(i))
        TO ? (FORMAT PARQUET)""", [os.environ["MERREC_CATALOG_PATH"]])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18080, log_level="warning")
