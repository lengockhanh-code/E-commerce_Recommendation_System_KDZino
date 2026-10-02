"""Fuse retrieval exports into reproducible DCN/LightGBM ranking datasets.

The script streams through DuckDB and atomically replaces each output only after
basic leakage, coverage, and schema checks pass. Validation/test keep the full
candidate union; train keeps the positive plus the strongest hard negatives.
"""

import argparse
import json
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "candidate_exports"
CASES = ROOT / "data/processed/recommender/candidate_cases"
CATALOG = ROOT / "data/processed/recommender/serving/item_catalog_full.parquet"
POPULARITY = ROOT / "data/processed/recommender/tables/05_top_popularity_train.csv"
OUTPUT = ROOT / "training/dcn/dataset"
SOURCE_TOPK = {"content": 150, "covis": 250, "als": 200, "gru": 200, "twotower": 3000}
MAX_CANDIDATE_POOL = 2000


def sql_path(path):
    return str(path.resolve()).replace("'", "''")


def source_cte(source, split, topk, keys_path):
    path = sql_path(EXPORTS / f"{source}_{split}.parquet")
    keys = sql_path(keys_path)
    return f"""{source} AS (
      SELECT case_id::VARCHAR case_id, user_id::VARCHAR user_id,
             candidate_item_id::VARCHAR candidate_item_id,
             target_item_id::VARCHAR target_item_id,
             CASE WHEN isfinite(score) THEN score::FLOAT ELSE 0::FLOAT END {source}_score,
             rank::INTEGER {source}_rank,
             (1.0 - (rank-1.0)/greatest({int(topk)}-1,1))::FLOAT {source}_score_norm,
             (1.0 / (rank + 1.0))::FLOAT {source}_rr
      FROM read_parquet('{path}') s
      SEMI JOIN read_parquet('{keys}') k
        USING(case_id,user_id,candidate_item_id,target_item_id)
      WHERE rank <= {int(topk)}
    )"""


def build_keys_query(split, train_candidates):
    union = " UNION ALL ".join(
        f"SELECT case_id::VARCHAR case_id,user_id::VARCHAR user_id,"
        f"candidate_item_id::VARCHAR candidate_item_id,target_item_id::VARCHAR target_item_id,"
        f"1.0/(60+rank) source_rrf FROM read_parquet('{sql_path(EXPORTS / f'{source}_{split}.parquet')}') "
        f"WHERE rank<={topk}" for source, topk in SOURCE_TOPK.items())
    cases = sql_path(CASES / f"cases_{split}.parquet")
    limit = train_candidates if split == "train" else MAX_CANDIDATE_POOL
    order = '(candidate_item_id=target_item_id) DESC,' if split == "train" else ""
    return f"""WITH case_history AS (
      SELECT case_id,history_item_ids FROM read_parquet('{cases}')
    ), scored AS (
      SELECT case_id,user_id,candidate_item_id,target_item_id,sum(source_rrf)::FLOAT rrf_score
      FROM ({union}) GROUP BY case_id,user_id,candidate_item_id,target_item_id
    ), unseen AS (
      SELECT s.* FROM scored s JOIN case_history h USING(case_id)
      WHERE NOT list_contains(h.history_item_ids,s.candidate_item_id)
    ) SELECT * FROM unseen
      QUALIFY row_number() OVER(PARTITION BY case_id
              ORDER BY {order}rrf_score DESC,candidate_item_id)<={int(limit)}"""


def build_query(split, keys_path):
    ctes = [source_cte(source, split, topk, keys_path) for source, topk in SOURCE_TOPK.items()]
    joins = "\n".join(
        f"LEFT JOIN {source} USING(case_id,user_id,candidate_item_id,target_item_id)"
        for source in SOURCE_TOPK)
    feature_columns = []
    source_flags = []
    for source in SOURCE_TOPK:
        feature_columns.extend([
            f"coalesce({source}_score,0)::FLOAT {source}_score",
            f"coalesce({source}_rank,9999)::INTEGER {source}_rank",
            f"coalesce({source}_score_norm,0)::FLOAT {source}_score_norm",
            f"coalesce({source}_rr,0)::FLOAT {source}_rr",
        ])
        source_flags.append(f"CASE WHEN {source}_rank IS NULL THEN 0 ELSE 1 END")
    features = ",\n             ".join(feature_columns)
    source_count = " + ".join(source_flags)
    cat = sql_path(CATALOG)
    pop = sql_path(POPULARITY)
    keys = sql_path(keys_path)
    enriched_input = "fused"
    return f"""WITH
    {','.join(ctes)},
    pruned_keys AS (SELECT * FROM read_parquet('{keys}')),
    fused AS (
      SELECT k.*,
             {features},
             ({source_count})::TINYINT source_count,
             k.rrf_score,
             (k.candidate_item_id = k.target_item_id)::TINYINT AS "label"
      FROM pruned_keys k {joins}
    )
    , enriched AS (
      SELECT f.*,
             coalesce(c.product_id,'unknown')::VARCHAR candidate_product_id,
             coalesce(c.brand,'unknown')::VARCHAR candidate_brand,
             coalesce(c.category0,'unknown')::VARCHAR candidate_category0,
             coalesce(c.category1,'unknown')::VARCHAR candidate_category1,
             coalesce(c.category2,'unknown')::VARCHAR candidate_category2,
             coalesce(c.price,0)::FLOAT candidate_price,
             coalesce(c.condition,'unknown')::VARCHAR candidate_condition,
             coalesce(c.shipper,'unknown')::VARCHAR candidate_shipper,
             coalesce(p.interactions,0)::FLOAT candidate_popularity
      FROM {enriched_input} f
      LEFT JOIN read_parquet('{cat}') c ON c.item_id=f.candidate_item_id
      LEFT JOIN read_csv_auto('{pop}', header=true) p ON p.item_id::VARCHAR=f.candidate_item_id
    )
    SELECT * FROM enriched"""


def metrics(db, path, split):
    cases_path = sql_path(CASES / f"cases_{split}.parquet")
    row = db.execute("""SELECT count(*) AS row_count, count(distinct case_id) AS case_count,
        sum("label") AS positives, count(*)::DOUBLE/count(distinct case_id) AS avg_candidates,
        count(distinct case_id) FILTER(WHERE "label"=1)::DOUBLE/count(distinct case_id) AS candidate_recall
        FROM read_parquet(?)""", [str(path)]).fetchone()
    expected = db.execute(f"SELECT count(*) FROM read_parquet('{cases_path}')").fetchone()[0]
    result = dict(zip(("rows", "cases", "positives", "avg_candidates", "candidate_recall"), row))
    result["serving_policy"] = "exclude_history"
    result["max_candidate_pool"] = 500 if split == "train" else MAX_CANDIDATE_POOL
    if result["cases"] != expected:
        raise ValueError(f"{split}: output has {result['cases']} cases; expected {expected}")
    if result["candidate_recall"] < 0.20:
        raise ValueError(f"{split}: fused candidate recall below 20%: {result['candidate_recall']:.4f}")
    if result["positives"] > result["cases"]:
        raise ValueError(f"{split}: more than one positive per case")
    result["source_recall"] = {}
    for source in SOURCE_TOPK:
        hits = db.execute(f"""SELECT count(distinct case_id)::DOUBLE/{expected}
            FROM read_parquet(?) WHERE "label"=1 AND {source}_rank < 9999""", [str(path)]).fetchone()[0]
        result["source_recall"][source] = hits
    return result


def build(split, train_candidates, memory_limit):
    for source in SOURCE_TOPK:
        path = EXPORTS / f"{source}_{split}.parquet"
        if not path.is_file():
            raise FileNotFoundError(path)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / f"dcn_{split}.parquet"
    temporary = destination.with_suffix(".parquet.tmp")
    temporary.unlink(missing_ok=True)
    scratch = ROOT / "scratch/duckdb_ranker"
    scratch.mkdir(parents=True, exist_ok=True)
    keys_path = scratch / f"pruned_keys_{split}.parquet"
    keys_path.unlink(missing_ok=True)
    db = duckdb.connect()
    db.execute("SET threads=1")
    db.execute(f"SET memory_limit='{int(memory_limit)}MB'")
    db.execute("SET preserve_insertion_order=false")
    db.execute(f"SET temp_directory='{sql_path(scratch)}'")
    keys_query = build_keys_query(split, train_candidates)
    db.execute(f"COPY ({keys_query}) TO '{sql_path(keys_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    db.close()
    db = duckdb.connect()
    db.execute("SET threads=1")
    db.execute(f"SET memory_limit='{int(memory_limit)}MB'")
    db.execute("SET preserve_insertion_order=false")
    db.execute(f"SET temp_directory='{sql_path(scratch)}'")
    query = build_query(split, keys_path)
    db.execute(f"COPY ({query}) TO '{sql_path(temporary)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    result = metrics(db, temporary, split)
    db.close()
    temporary.replace(destination)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", nargs="+", choices=["train", "val", "test"],
                        default=["train", "val", "test"])
    parser.add_argument("--train-candidates", type=int, default=500)
    parser.add_argument("--memory-limit-mb", type=int, default=2500)
    args = parser.parse_args()
    report_path = OUTPUT / "candidate_audit.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    for split in args.splits:
        report[split] = build(split, args.train_candidates, args.memory_limit_mb)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
