"""Unified Prediction Case Generator using DuckDB (Zero OOM, Fast Parquet Streaming).

Generates deterministic prediction cases for TRAIN, VAL, TEST splits.
NO LEAKAGE:
- TRAIN: history uses interactions before target within TRAIN.
- VAL: history uses TRAIN + interactions in VAL before target.
- TEST: history uses TRAIN + VAL + interactions in TEST before target.
"""

import sys
import time
from pathlib import Path
import duckdb
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "data" / "processed" / "recommender" / "candidate_cases"
CASES_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PARQUET = (ROOT / "data" / "processed" / "recommender" / "model_data" / "interactions" / "split=train" / "data_0.parquet").as_posix()
VAL_PARQUET = (ROOT / "data" / "processed" / "recommender" / "model_data" / "interactions" / "split=val" / "data_0.parquet").as_posix()
TEST_PARQUET = (ROOT / "data" / "processed" / "recommender" / "model_data" / "interactions" / "split=test" / "data_0.parquet").as_posix()

def build_cases(max_train_cases=10000, max_val_cases=3000, max_test_cases=5000):
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Building Unified Candidate Prediction Cases with DuckDB ===")
    t0 = time.time()
    
    con = duckdb.connect()
    con.execute("SET memory_limit='4GB';")

    # 1. Process TRAIN split
    print(f"\n[*] Generating TRAIN cases (limit={max_train_cases:,})...")
    con.execute(f"""
        CREATE OR REPLACE TABLE train_users AS
        SELECT user_id, COUNT(*) as cnt
        FROM read_parquet('{TRAIN_PARQUET}')
        GROUP BY user_id
        HAVING cnt >= 2
        ORDER BY user_id
        LIMIT {max_train_cases};
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE train_targets AS
        SELECT u.user_id, t.item_id as target_item_id, t.ts as target_ts
        FROM train_users u
        JOIN (
            SELECT user_id, item_id, ts,
                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ts DESC) as rn
            FROM read_parquet('{TRAIN_PARQUET}')
        ) t ON u.user_id = t.user_id AND t.rn = 1;
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE cases_train_raw AS
        SELECT 
            'train_' || t.user_id || '_' || EPOCH_MS(t.target_ts)::VARCHAR || '_' || t.target_item_id as case_id,
            'train' as split,
            t.user_id,
            t.target_item_id,
            t.target_ts,
            ARRAY_AGG(i.item_id ORDER BY i.ts ASC) as history_item_ids
        FROM train_targets t
        JOIN read_parquet('{TRAIN_PARQUET}') i ON t.user_id = i.user_id AND i.ts < t.target_ts
        GROUP BY t.user_id, t.target_item_id, t.target_ts;
    """)

    df_train = con.execute("SELECT * FROM cases_train_raw").pl()
    out_train = CASES_DIR / "cases_train.parquet"
    df_train.write_parquet(out_train, compression="zstd")
    print(f"✅ Saved {df_train.height:,} TRAIN cases -> {out_train.name}")

    # 2. Process VAL split (history uses TRAIN + VAL before target)
    print(f"\n[*] Generating VAL cases (limit={max_val_cases:,})...")
    con.execute(f"""
        CREATE OR REPLACE TABLE val_users AS
        SELECT user_id, COUNT(*) as cnt
        FROM read_parquet('{VAL_PARQUET}')
        GROUP BY user_id
        HAVING cnt >= 1
        ORDER BY user_id
        LIMIT {max_val_cases};
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE val_targets AS
        SELECT u.user_id, t.item_id as target_item_id, t.ts as target_ts
        FROM val_users u
        JOIN (
            SELECT user_id, item_id, ts,
                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ts DESC) as rn
            FROM read_parquet('{VAL_PARQUET}')
        ) t ON u.user_id = t.user_id AND t.rn = 1;
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE cum_train_val AS
        SELECT user_id, item_id, ts FROM read_parquet('{TRAIN_PARQUET}')
        UNION ALL
        SELECT user_id, item_id, ts FROM read_parquet('{VAL_PARQUET}');
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE cases_val_raw AS
        SELECT 
            'val_' || t.user_id || '_' || EPOCH_MS(t.target_ts)::VARCHAR || '_' || t.target_item_id as case_id,
            'val' as split,
            t.user_id,
            t.target_item_id,
            t.target_ts,
            ARRAY_AGG(i.item_id ORDER BY i.ts ASC) as history_item_ids
        FROM val_targets t
        JOIN cum_train_val i ON t.user_id = i.user_id AND i.ts < t.target_ts
        GROUP BY t.user_id, t.target_item_id, t.target_ts;
    """)

    df_val = con.execute("SELECT * FROM cases_val_raw").pl()
    out_val = CASES_DIR / "cases_val.parquet"
    df_val.write_parquet(out_val, compression="zstd")
    print(f"✅ Saved {df_val.height:,} VAL cases -> {out_val.name}")

    # 3. Process TEST split (history uses TRAIN + VAL + TEST before target)
    print(f"\n[*] Generating TEST cases (limit={max_test_cases:,})...")
    con.execute(f"""
        CREATE OR REPLACE TABLE test_users AS
        SELECT user_id, COUNT(*) as cnt
        FROM read_parquet('{TEST_PARQUET}')
        GROUP BY user_id
        HAVING cnt >= 1
        ORDER BY user_id
        LIMIT {max_test_cases};
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE test_targets AS
        SELECT u.user_id, t.item_id as target_item_id, t.ts as target_ts
        FROM test_users u
        JOIN (
            SELECT user_id, item_id, ts,
                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ts DESC) as rn
            FROM read_parquet('{TEST_PARQUET}')
        ) t ON u.user_id = t.user_id AND t.rn = 1;
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE cum_train_val_test AS
        SELECT user_id, item_id, ts FROM cum_train_val
        UNION ALL
        SELECT user_id, item_id, ts FROM read_parquet('{TEST_PARQUET}');
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE cases_test_raw AS
        SELECT 
            'test_' || t.user_id || '_' || EPOCH_MS(t.target_ts)::VARCHAR || '_' || t.target_item_id as case_id,
            'test' as split,
            t.user_id,
            t.target_item_id,
            t.target_ts,
            ARRAY_AGG(i.item_id ORDER BY i.ts ASC) as history_item_ids
        FROM test_targets t
        JOIN cum_train_val_test i ON t.user_id = i.user_id AND i.ts < t.target_ts
        GROUP BY t.user_id, t.target_item_id, t.target_ts;
    """)

    df_test = con.execute("SELECT * FROM cases_test_raw").pl()
    out_test = CASES_DIR / "cases_test.parquet"
    df_test.write_parquet(out_test, compression="zstd")
    print(f"✅ Saved {df_test.height:,} TEST cases -> {out_test.name}")

    print(f"\n🎉 UNIFIED PREDICTION CASES GENERATED IN {time.time() - t0:.2f}s!")
    return True

if __name__ == "__main__":
    build_cases()
