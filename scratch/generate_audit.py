import json
import duckdb
from pathlib import Path

ROOT = Path(".")
dataset = ROOT / "training/dcn/dataset"

SOURCE_TOPK = {"content": 150, "covis": 250, "als": 200, "gru": 200, "twotower": 300}

audit = {}

with duckdb.connect() as db:
    for split in ("train", "val", "test"):
        path = dataset / f"dcn_{split}.parquet"
        res = db.execute(f"""
            SELECT count(*), count(distinct case_id), sum(label)
            FROM read_parquet('{path.as_posix()}')
        """).fetchone()
        rows, cases, positives = res
        recall = float(positives) / float(cases) if cases else 0.0
        
        sources = {}
        for source in SOURCE_TOPK:
            hits = db.execute(f"""
                SELECT count(distinct case_id)::DOUBLE / {cases}
                FROM read_parquet('{path.as_posix()}')
                WHERE label = 1 AND {source}_rank < 9999
            """).fetchone()[0]
            sources[source] = float(hits)
        
        audit[split] = {
            "rows": int(rows),
            "cases": int(cases),
            "positives": int(positives),
            "avg_candidates": float(rows) / float(cases) if cases else 0.0,
            "candidate_recall": recall,
            "serving_policy": "exclude_history",
            "source_recall": sources
        }

(dataset / "candidate_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
print("candidate_audit.json successfully generated:")
print(json.dumps(audit, indent=2))
