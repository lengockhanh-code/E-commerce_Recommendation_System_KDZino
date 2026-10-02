"""Train and audit a LightGBM ranker on the exact DCN candidate splits.

Only queries containing a positive item contribute LambdaRank gradients. Metrics
are reported both conditional on retrieval success and across *all* queries.
The held-out test split is evaluated once, after validation has selected trees.
"""

import argparse
import json
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "training/dcn/dataset"
OUTPUT = ROOT / "training/lightgbm_ranker"
CATEGORICAL = ["candidate_brand", "candidate_category0", "candidate_category1",
               "candidate_category2", "candidate_condition", "candidate_shipper"]
NUMERICAL = [f"{source}_{suffix}" for source in ("content", "covis", "als", "gru", "twotower")
             for suffix in ("score", "rank", "score_norm", "rr")]
NUMERICAL += ["source_count", "rrf_score", "candidate_price", "candidate_popularity"]
FEATURES = CATEGORICAL + NUMERICAL


def validate_candidate_audit(dataset):
    audit_path = dataset / "candidate_audit.json"
    if not audit_path.is_file():
        raise ValueError("Missing candidate_audit.json; rebuild ranker datasets first")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    for split in ("train", "val", "test"):
        details = audit.get(split, {})
        if details.get("serving_policy") != "exclude_history":
            raise ValueError(f"{split}: offline candidates do not match exclude-history serving policy")
        if float(details.get("candidate_recall", 0)) < 0.20:
            raise ValueError(f"{split}: candidate recall is below the 20% training gate")
    return audit


def load_positive_queries(path):
    """Keep all candidates in hittable queries, including their negatives."""
    with duckdb.connect() as db:
        db.execute("SET threads=2")
        db.execute("SET memory_limit='2GB'")
        db.from_parquet(str(path)).create_view("candidates")
        all_cases, positive_cases = db.execute("""
            SELECT count(*), sum(CASE WHEN positives > 0 THEN 1 ELSE 0 END)
            FROM (SELECT case_id, sum(label) AS positives FROM candidates GROUP BY case_id)
        """).fetchone()
        columns = ", ".join(f'c."{column}"' for column in
                            ["case_id", "candidate_item_id", "label", *FEATURES])
        frame = db.execute(f"""SELECT {columns} FROM candidates c
            SEMI JOIN (SELECT case_id FROM candidates GROUP BY case_id
                       HAVING sum(label) > 0) p USING (case_id)
            ORDER BY c.case_id, c.candidate_item_id""").fetch_df()
    if not positive_cases or frame.empty:
        raise ValueError(f"No positive queries in {path}")
    return frame, int(all_cases), int(positive_cases)


def encode_features(frame, vocabulary=None):
    if vocabulary is None:
        vocabulary = {}
        for column in CATEGORICAL:
            vocabulary[column] = sorted(frame[column].fillna("unknown").astype(str).unique().tolist())
    encoded = pd.DataFrame(index=frame.index)
    for column in CATEGORICAL:
        lookup = {name: index for index, name in enumerate(vocabulary[column])}
        encoded[column] = pd.Categorical(
            frame[column].fillna("unknown").astype(str).map(lookup),
            categories=range(len(lookup)), ordered=False)
    for column in NUMERICAL:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=np.float32, copy=True)
        # Missing retrieval sources can contain +/-inf; preserve missingness as NaN.
        values[~np.isfinite(values)] = np.nan
        encoded[column] = values
    return encoded[FEATURES], vocabulary


def group_sizes(frame):
    sizes = frame.groupby("case_id", sort=False).size().to_numpy(dtype=np.int32)
    if int(sizes.sum()) != len(frame):
        raise ValueError("Query groups do not match candidate rows")
    return sizes


def ranking_metrics(frame, scores, all_cases, ks=(10, 20, 50)):
    """One target per request; count un-retrieved requests as zero hits."""
    if len(scores) != len(frame):
        raise ValueError("Score count differs from candidate count")
    data = frame[["case_id", "candidate_item_id", "label"]].copy()
    data["score"] = np.asarray(scores, dtype=np.float64)
    if not np.isfinite(data["score"]).all():
        raise ValueError("Ranker produced a non-finite score")
    data.sort_values(["case_id", "score", "candidate_item_id"],
                     ascending=[True, False, True], inplace=True, kind="stable")
    data["rank"] = data.groupby("case_id", sort=False).cumcount() + 1
    positive = data.loc[data.label > 0].groupby("case_id", sort=False)["rank"].min()
    ranks = positive.to_numpy(dtype=np.float64)
    if not len(ranks) or len(ranks) > all_cases:
        raise ValueError("Invalid positive query count")
    result = {"all_cases": all_cases, "positive_cases": len(ranks),
              "candidate_recall": len(ranks) / all_cases}
    for k in ks:
        hits = ranks <= k
        dcg = np.where(hits, 1 / np.log2(ranks + 1), 0)
        result[f"Recall@{k}"] = float(hits.sum() / all_cases)
        result[f"NDCG@{k}"] = float(dcg.sum() / all_cases)
        result[f"conditional_Recall@{k}"] = float(hits.mean())
        result[f"conditional_NDCG@{k}"] = float(dcg.mean())
    result["MRR@20"] = float(np.where(ranks <= 20, 1 / ranks, 0).sum() / all_cases)
    return result


def serving_blend(frame, model_scores, model_weight):
    """Mirror online rank-normalized model + min-max baseline blending."""
    scored = pd.DataFrame({"case_id": frame.case_id.to_numpy(),
                           "model": np.asarray(model_scores, dtype=np.float64),
                           "baseline": frame.rrf_score.to_numpy(dtype=np.float64)})
    scored["model_norm"] = scored.groupby("case_id", sort=False)["model"].rank(
        method="first", pct=True)
    grouped = scored.groupby("case_id", sort=False)["baseline"]
    low, high = grouped.transform("min"), grouped.transform("max")
    scored["baseline_norm"] = np.where(high > low, (scored.baseline - low) / (high - low), 0.0)
    return (model_weight * scored.model_norm +
            (1 - model_weight) * scored.baseline_norm).to_numpy()


def choose_blend_weight(frame, model_scores, all_cases):
    candidates = []
    for weight in np.linspace(0, 1, 21):
        metrics = ranking_metrics(frame, serving_blend(frame, model_scores, weight), all_cases)
        candidates.append((metrics["NDCG@20"], metrics["NDCG@10"], -weight, weight, metrics))
    return max(candidates)[3:]


def train(args):
    validate_candidate_audit(args.dataset)
    paths = {split: args.dataset / f"dcn_{split}.parquet" for split in ("train", "val", "test")}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    train_frame, train_all, train_positive = load_positive_queries(paths["train"])
    val_frame, val_all, val_positive = load_positive_queries(paths["val"])
    print(f"Training: {train_positive}/{train_all} hittable queries; "
          f"validation: {val_positive}/{val_all}", flush=True)
    if set(train_frame.case_id).intersection(val_frame.case_id):
        raise ValueError("Train and validation case IDs overlap")
    x_train, vocabulary = encode_features(train_frame)
    x_val, _ = encode_features(val_frame, vocabulary)
    y_train = train_frame.label.to_numpy(dtype=np.int8)
    y_val = val_frame.label.to_numpy(dtype=np.int8)
    ranker = lgb.LGBMRanker(
        objective="lambdarank", metric="ndcg", n_estimators=args.trees,
        learning_rate=0.03, num_leaves=15, max_depth=6, min_child_samples=100,
        min_data_per_group=50, reg_lambda=5.0, feature_fraction=0.8,
        lambdarank_truncation_level=30, label_gain=[0, 1],
        n_jobs=args.threads, random_state=42, verbosity=-1)
    ranker.fit(x_train, y_train, group=group_sizes(train_frame),
               eval_set=[(x_val, y_val)], eval_group=[group_sizes(val_frame)],
               # A single metric makes early stopping deterministic. NDCG@20 is
               # less noisy than @10 with only 142 hittable validation queries.
               eval_at=[20], categorical_feature=CATEGORICAL,
               callbacks=[lgb.early_stopping(50, first_metric_only=True, verbose=True),
                          lgb.log_evaluation(25)])
    iteration = ranker.best_iteration_ or args.trees
    val_scores = ranker.predict(x_val, num_iteration=iteration)
    val_result = ranking_metrics(val_frame, val_scores, val_all)
    val_baseline = ranking_metrics(val_frame, val_frame.rrf_score.to_numpy(), val_all)
    blend_weight, val_serving = choose_blend_weight(val_frame, val_scores, val_all)

    # Test is never used to select features, hyperparameters or early stopping.
    del x_train, x_val, train_frame, val_frame, y_train, y_val
    test_frame, test_all, test_positive = load_positive_queries(paths["test"])
    x_test, _ = encode_features(test_frame, vocabulary)
    test_scores = ranker.predict(x_test, num_iteration=iteration)
    test_result = ranking_metrics(test_frame, test_scores, test_all)
    test_baseline = ranking_metrics(test_frame, test_frame.rrf_score.to_numpy(), test_all)
    test_serving = ranking_metrics(
        test_frame, serving_blend(test_frame, test_scores, blend_weight), test_all)
    accepted = (blend_weight > 0 and
                val_serving["NDCG@20"] > val_baseline["NDCG@20"] and
                test_serving["NDCG@20"] >= test_baseline["NDCG@20"] and
                test_serving["NDCG@10"] >= test_baseline["NDCG@10"])
    report = {
        "dataset": {split: str(path) for split, path in paths.items()},
        "train_all_cases": train_all, "train_positive_cases": train_positive,
        "val_all_cases": val_all, "val_positive_cases": val_positive,
        "test_all_cases": test_all, "test_positive_cases": test_positive,
        "best_iteration": iteration, "features": FEATURES,
        "val": val_result, "val_rrf_baseline": val_baseline,
        "serving_model_weight": blend_weight, "val_serving_blend": val_serving,
        "test": test_result, "test_rrf_baseline": test_baseline,
        "test_serving_blend": test_serving,
        "accepted_for_serving": accepted,
        "selection_rule": "blend weight selected on val; test NDCG@10 and @20 must not regress",
        "note": "Ranking metrics include zero for requests without a retrieved positive candidate."
    }
    args.output.mkdir(parents=True, exist_ok=True)
    model_path = args.output / "model/lightgbm_ranker.txt"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    ranker.booster_.save_model(str(model_path), num_iteration=iteration)
    (args.output / "model/feature_schema.json").write_text(
        json.dumps({"features": FEATURES, "categorical": CATEGORICAL,
                    "vocabulary": vocabulary, "missing_numeric": "NaN",
                    "serving_model_weight": blend_weight,
                    "serving_policy": "exclude_history",
                    "accepted_for_serving": accepted}, ensure_ascii=False), encoding="utf-8")
    metric_path = args.output / "metrics/summary.json"
    metric_path.parent.mkdir(parents=True, exist_ok=True)
    metric_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--trees", type=int, default=500)
    parser.add_argument("--threads", type=int, default=2)
    train(parser.parse_args())
