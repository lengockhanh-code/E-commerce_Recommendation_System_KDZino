"""Compare frozen DCN/LightGBM checkpoints on one single-target candidate file."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
import polars as pl
import torch

from scripts.train_dcn_ranker import DCN, encode, fingerprint, predict
from scripts.train_lightgbm_ranker import encode_features, ranking_metrics, serving_blend

KS = (10, 20, 50, 100)


def validate_query_frame(frame):
    keys = frame[["case_id", "candidate_item_id", "label"]]
    if keys.isna().any().any() or not keys.label.isin([0, 1]).all():
        raise ValueError("Candidate keys/labels must be non-null and labels binary")
    if keys.duplicated(["case_id", "candidate_item_id"]).any():
        raise ValueError("Duplicate candidate within a query")
    if (keys.groupby("case_id").label.sum() > 1).any():
        raise ValueError("Expected at most one target per query")


def combine_metrics(parts, all_cases, positive_cases):
    """Preserve zero-hit cases when batches only score hittable queries."""
    if not 0 < positive_cases <= all_cases:
        raise ValueError("Invalid global query counts")
    if sum(p["positive_cases"] for p in parts) != positive_cases:
        raise ValueError("Scored queries do not match candidate positives")
    out = {"all_cases": all_cases, "positive_cases": positive_cases,
           "candidate_recall": positive_cases / all_cases}
    for name in [f"{metric}@{k}" for k in KS for metric in ("Recall", "NDCG")] + ["MRR@20"]:
        numerator = sum(p[name] * p["all_cases"] for p in parts)
        out[name] = numerator / all_cases
        out["conditional_" + name] = numerator / positive_cases
    return out


def run(args):
    if args.case_batch < 1 or args.threads < 1:
        raise ValueError("Batch and thread counts must be positive")
    if args.output.exists():
        raise FileExistsError("Choose a new output directory; existing results are preserved")
    schema_path = args.lightgbm.with_name("feature_schema.json")
    audit_path = args.dataset.parent / "candidate_audit.json"
    inputs = {name: fingerprint(path) for name, path in (
        ("dataset", args.dataset), ("dcn", args.dcn),
        ("lightgbm", args.lightgbm), ("lightgbm_schema", schema_path))}
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
    checkpoint = torch.load(args.dcn, map_location="cpu", weights_only=False)
    if checkpoint.get("serving_policy") != "allow_repeat":
        raise ValueError("DCN checkpoint must use allow_repeat")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # Serving filtering belongs to retrieval, not the ranker's scoring function.
    # Preserve the saved policy as provenance; do not let it change the shared pool.
    if audit.get("test", {}).get("serving_policy") != "allow_repeat":
        raise ValueError("Shared TEST candidate audit must use allow_repeat")
    saved_test = checkpoint.get("dataset_fingerprints", {}).get("test", {})
    if saved_test.get("sha256") != inputs["dataset"]["sha256"]:
        raise ValueError("TEST file differs from the DCN training run's saved TEST")
    torch.set_num_threads(args.threads)
    model = DCN(checkpoint.get("model_config"))
    model.load_state_dict(checkpoint["model"])
    booster = lgb.Booster(model_file=str(args.lightgbm))
    weight = float(schema["serving_model_weight"])
    if not 0 <= weight <= 1:
        raise ValueError("Invalid saved blend weight")
    names = ("RRF", "DCN", "LightGBM", "LightGBM_frozen_serving_blend")
    parts = {name: [] for name in names}
    scored_rows = 0
    with duckdb.connect() as db:
        db.execute(f"SET threads={args.threads}")
        db.execute("SET memory_limit='2GB'")
        db.from_parquet(str(args.dataset)).create_view("c")
        invalid = db.execute("""SELECT count(*) FROM c WHERE case_id IS NULL
            OR candidate_item_id IS NULL OR label IS NULL OR label NOT IN (0,1)""").fetchone()[0]
        duplicate = db.execute("""SELECT count(*) FROM (SELECT case_id,candidate_item_id
            FROM c GROUP BY ALL HAVING count(*)>1)""").fetchone()[0]
        if invalid or duplicate:
            raise ValueError("Invalid labels/IDs or duplicate candidates in TEST")
        db.execute("CREATE TEMP TABLE queries AS SELECT case_id, sum(label) AS positives FROM c GROUP BY case_id")
        all_cases, positive_cases, max_positive = db.execute("""SELECT count(*),
            count(*) FILTER (WHERE positives>0), max(positives) FROM queries""").fetchone()
        if not all_cases or max_positive != 1:
            raise ValueError("Expected nonempty one-target-per-case TEST")
        total_rows = db.execute("SELECT count(*) FROM c").fetchone()[0]
        cases = db.execute("SELECT case_id FROM queries WHERE positives=1 ORDER BY case_id").fetch_df()
        expected_cases = audit.get("test", {}).get("cases")
        if expected_cases is not None and expected_cases != all_cases:
            raise ValueError("Candidate audit case count differs from TEST")
        print(f"Shared TEST: {total_rows:,} rows; {all_cases} cases; "
              f"{positive_cases} positive cases; coverage {positive_cases/all_cases:.4%}", flush=True)
        for start in range(0, len(cases), args.case_batch):
            chosen = cases.iloc[start:start + args.case_batch]
            db.register("batch_cases", chosen)
            frame = pl.from_arrow(db.execute("""SELECT c.* FROM c SEMI JOIN batch_cases USING(case_id)
                ORDER BY case_id,candidate_item_id""").fetch_arrow_table())
            db.unregister("batch_cases")
            data = frame.to_pandas()
            validate_query_frame(data)
            # Native shared feature values; each checkpoint keeps its TRAIN-only
            # encoding/scaler. No target-dependent feature construction or TEST fitting.
            cats, nums = encode(frame, checkpoint["num_mean"], checkpoint["num_std"])
            dcn_scores = predict(model, cats, nums, 4096)
            encoded, _ = encode_features(data, schema["vocabulary"])
            lgb_scores = booster.predict(encoded, num_threads=args.threads)
            scores = {"RRF": data.rrf_score.to_numpy(), "DCN": dcn_scores,
                      "LightGBM": lgb_scores,
                      "LightGBM_frozen_serving_blend": serving_blend(data, lgb_scores, weight)}
            for name, values in scores.items():
                parts[name].append(ranking_metrics(data, values, len(chosen), ks=KS))
            scored_rows += len(frame)
            print(f"Scored {min(start+len(chosen), len(cases))}/{positive_cases} hittable cases", flush=True)
    results = {name: combine_metrics(parts[name], all_cases, positive_cases) for name in names}
    for name, fp in inputs.items():
        if fingerprint(Path(fp["path"])) != fp:
            raise RuntimeError(f"Input changed during evaluation: {name}")
    report = {
        "protocol": "shared_dcn_expanded_single_target_all_cases",
        "serving_policy": "allow_repeat", "candidate_rows": total_rows,
        "scored_rows": scored_rows, "all_cases": all_cases,
        "positive_cases": positive_cases, "candidate_recall": positive_cases/all_cases,
        "same_test_file_candidates_labels_and_cases": True,
        "target_injected": False, "retrained": False, "test_used_for_selection": False,
        "dcn_epoch": checkpoint.get("epoch"), "lightgbm_trees": booster.current_iteration(),
        "frozen_lightgbm_blend_weight": weight, "input_fingerprints": inputs,
        "lightgbm_saved_serving_policy": schema.get("serving_policy"),
        "per_model_candidate_filtering": False,
        "candidate_audit_history_policy_verified": audit.get("history_policy_verified", False),
        "results": results,
        "limitations": [
            "One last-interaction target/case; not the pre-TEST multi-future benchmark.",
            "Checkpoints keep their original training datasets; this controls TEST inputs only.",
            "LightGBM saved serving policy may differ; fixed shared TEST candidates override serving filtering.",
            "Expanded candidate history policy has not been independently verified.",
            "Serving blend weight was selected on the original LightGBM VAL, not on this TEST.",
            "Unretrieved targets count as zero; queries with no target are not scored because they cannot hit.",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame([{"model": name, **values} for name, values in results.items()]).to_csv(
        args.output / "comparison.csv", index=False)
    lines = ["# DCN và LightGBM trên cùng candidate pool", "",
             f"TEST: {all_cases} case, {positive_cases} target trong pool; coverage {positive_cases/all_cases:.2%}.", "",
             "| Model | Recall@20 | NDCG@20 | Recall@100 | Conditional Recall@20 |",
             "|---|---:|---:|---:|---:|"]
    for name, m in results.items():
        lines.append(f"| {name} | {m['Recall@20']:.2%} | {m['NDCG@20']:.6f} | {m['Recall@100']:.2%} | {m['conditional_Recall@20']:.2%} |")
    lines += ["", "Hai checkpoint giữ nguyên dữ liệu huấn luyện cũ; đây là so sánh cùng TEST, chưa phải train cùng dataset.",
              "Giao thức một target cuối/case, khác benchmark nhiều item tương lai. History policy của pool mở rộng chưa được kiểm chứng độc lập."]
    (args.output / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "results": results}, indent=2), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "training/dcn/runs/retrieval_expanded_20261010/dataset/dcn_test.parquet")
    parser.add_argument("--dcn", type=Path, default=ROOT / "training/dcn/runs/numeric_earlystop_20261010/model/dcn_best.pt")
    parser.add_argument("--lightgbm", type=Path, default=ROOT / "training/lightgbm_ranker/model/lightgbm_ranker.txt")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-batch", type=int, default=128)
    parser.add_argument("--threads", type=int, default=4)
    run(parser.parse_args())
