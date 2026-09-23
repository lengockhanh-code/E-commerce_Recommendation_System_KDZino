
from pathlib import Path
import os, json, gc
import numpy as np
import duckdb

from .paths import PROJECT_ROOT, MODEL_SPECIFIC_DIR

DUCKDB_TEMP = MODEL_SPECIFIC_DIR / "duckdb_temp"
DUCKDB_TEMP.mkdir(parents=True, exist_ok=True)

def connect_duckdb(memory_limit="8GB"):
    db_path = MODEL_SPECIFIC_DIR / "model_training.duckdb"
    con = duckdb.connect(str(db_path))
    threads = max(1, min(6, (os.cpu_count() or 4) - 2))
    con.execute(f"SET threads={threads}")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET temp_directory='{DUCKDB_TEMP.as_posix()}'")
    con.execute("SET max_temp_directory_size='150GB'")
    return con

def valid_file(path):
    path = Path(path)
    return path.exists() and path.is_file() and path.stat().st_size > 0

def valid_parquet(path, con=None):
    path = Path(path)
    if not valid_file(path):
        return False
    own = False
    if con is None:
        con = connect_duckdb()
        own = True
    try:
        con.execute(
            f"SELECT 1 FROM read_parquet('{path.as_posix()}') LIMIT 1"
        ).fetchone()
        return True
    except Exception:
        return False
    finally:
        if own:
            con.close()

def atomic_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)

def stable_hash(text, buckets, seed=42):
    from sklearn.utils import murmurhash3_32
    text = "__UNK__" if text is None else str(text)
    return int(murmurhash3_32(text, seed=seed, positive=True) % buckets)
