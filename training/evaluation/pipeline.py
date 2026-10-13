"""MerRec temporal multi-target benchmark inspired by published Shopee evaluation.

Frozen pre-TEST retrieval, shared candidate union, then fixed DCN/LightGBM.
This is a logged-interaction benchmark, not impression-level CTR or an A/B test.
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import polars as pl
import torch

from .future_items import build_future_cases
from .nextitem import MODELS, fingerprint, inputs, parquet_source, sqlpath, write_json
from .retrievers import artifacts, reverse_mapping
from scripts.train_dcn_ranker import DCN, encode, predict
from scripts.train_lightgbm_ranker import encode_features

ROOT = Path(__file__).resolve().parents[2]
KS = (20, 50, 100)
TOPK = dict(content=150, covis=250, als=200, gru=200, twotower=300)


def metrics(targets, predictions, ks=KS):
    groups = targets.groupby("user_id").item_id.agg(set).to_dict()
    total = sum(map(len, groups.values()))
    result = {"users": len(groups), "targets": total}
    for k in ks:
        hits, recalls, ndcgs, covered = 0, [], [], 0
        discount = 1 / np.log2(np.arange(1, k + 1) + 1)
        for user, relevant in groups.items():
            top = list(predictions.get(user, []))[:k]
            if len(top) != len(set(top)):
                raise ValueError("Duplicate predictions within user")
            flags = np.asarray([item in relevant for item in top])
            count = int(flags.sum())
            hits += count
            covered += count > 0
            recalls.append(count / len(relevant))
            ndcgs.append(float((flags * discount[:len(top)]).sum() /
                               discount[:min(k, len(relevant))].sum()))
        result.update({f"hits@{k}": hits, f"users_with_hit@{k}": covered,
                       f"avg_hits@{k}": hits / len(groups) if groups else None,
                       # Missing recommendation slots count as zero at fixed K.
                       f"Precision@{k}": hits / (k * len(groups)) if groups else None,
                       f"Recall@{k}": float(np.mean(recalls)) if groups else None,
                       f"micro_Recall@{k}": hits / total if total else None,
                       f"NDCG@{k}": float(np.mean(ndcgs)) if groups else None})
    return result


def dcn_feature_frame(frame, checkpoint):
    """Apply the retriever rank normalization saved with this DCN checkpoint.

    Shared candidates remain unchanged for RRF and LightGBM. Target labels are
    never used in candidate selection or feature construction.
    """
    topk = checkpoint.get('source_topk')
    if not topk:
        return frame
    expressions = []
    for source, limit in topk.items():
        if source not in MODELS or limit < 2:
            raise ValueError('Invalid checkpoint retrieval normalization')
        rank = pl.col(f'{source}_rank')
        expressions.append(pl.when(rank < 9999)
            .then(1.0 - (rank - 1.0) / (limit - 1))
            .otherwise(0.0).cast(pl.Float32).alias(f'{source}_score_norm'))
    return frame.with_columns(expressions)


def ranker_metrics(targets, pool_predictions, predictions, ks=KS):
    """Evaluate ordering only, conditioning on targets present in a fixed pool.

    Predictions keep their original order and irrelevant candidates. We only
    change the ground-truth denominator, never add targets or filter the list.
    Users without reachable targets remain in the end-to-end report, not this
    diagnostic. Macro and micro denominators are explicit in the result.
    """
    groups = targets.groupby('user_id').item_id.agg(set).to_dict()
    reachable = []
    for user, relevant in groups.items():
        pool = set(pool_predictions.get(user, []))
        top = list(predictions.get(user, []))[:max(ks)]
        if len(top) != len(set(top)) or any(item not in pool for item in top):
            raise ValueError('Ranker predictions must be unique items from the fixed pool')
        reachable.extend((user, item) for item in relevant & pool)
    ground_truth = pd.DataFrame(reachable, columns=['user_id', 'item_id'])
    result = metrics(ground_truth, predictions, ks)
    result.update({'protocol': 'ranker_ordering_retrieved_targets_only',
                   'all_users': len(groups), 'all_target_pairs': sum(map(len, groups.values())),
                   'users_without_retrieved_target': len(groups)-result['users'],
                   'pool_target_pairs': len(reachable),
                   'ndcg_ideal_definition': 'min(K, distinct relevant targets in the fixed pool per user)',
                   'test_targets_used_for_ranking': False})
    return result


def exclusive_hits(targets, routes, k=100):
    """Count user/item hits contributed by exactly one route at equal top-K."""
    ground_truth = set(zip(targets.user_id, targets.item_id))
    sets = {name: {(u, item) for u, items in pred.items() for item in items[:k]}
            for name, pred in routes.items()}
    result = {}
    for name, items in sets.items():
        others = set().union(*(v for n, v in sets.items() if n != name))
        count = len((items - others) & ground_truth)
        result[name] = {"exclusive_hits": count,
                        "exclusive_micro_recall": count / len(ground_truth) if ground_truth else None}
    return result


def candidate_discrimination(frame, targets, column):
    """AUC/GAUC proxy: observed future items versus unobserved candidates.

    Unobserved is not equivalent to exposed-but-not-clicked. Never label this CTR.
    GAUC weights eligible user groups by candidate count; single-class groups skip.
    """
    from sklearn.metrics import roc_auc_score
    relevant = set(zip(targets.user_id, targets.item_id))
    data = frame[["user_id", "candidate_item_id", column]].copy()
    data["label"] = [(u, i) in relevant for u, i in zip(data.user_id, data.candidate_item_id)]
    auc = float(roc_auc_score(data.label, data[column])) if data.label.nunique() == 2 else None
    weighted, denominator, eligible = 0., 0, 0
    for _, group in data.groupby("user_id", sort=False):
        if group.label.nunique() == 2:
            weighted += len(group) * roc_auc_score(group.label, group[column])
            denominator += len(group)
            eligible += 1
    return {"future_item_candidate_AUC": auc,
            "future_item_candidate_GAUC": weighted / denominator if denominator else None,
            "GAUC_eligible_users": eligible,
            "GAUC_excluded_single_class_users": data.user_id.nunique() - eligible,
            "negative_definition": "candidate not observed in future TEST; not impression-level click negative"}


def restore_sources(cache, users, output, cohort_hash):
    frames, provenance = [], {}
    for model in MODELS:
        directory = cache / model
        manifest = json.loads((directory / "evaluation_manifest.json").read_text(encoding="utf-8"))
        p, artifact_paths = artifacts(model, ROOT)
        if manifest["spec"]["artifacts"] != fingerprint(artifact_paths):
            raise ValueError(f"{model}: artifacts changed since cached inference")
        if manifest["spec"]["cohort_hash"] != cohort_hash:
            raise ValueError(f"{model}: wrong history/user cohort")
        frame = pd.read_parquet(directory / "test_nextitem_predictions.parquet")
        if list(frame.user_id) != list(users.user_id):
            raise ValueError(f"{model}: cache user order differs")
        predictions = dict(zip(frame.user_id, frame.predicted_item_ids.map(list)))
        if model == "covis":
            parts = sorted(directory.glob("test_nextitem_candidates_*.parquet"))
            with duckdb.connect() as db:
                db.execute("SET memory_limit='1GB'")
                wanted = pd.DataFrame([(u, item) for u, items in predictions.items() for item in items],
                                      columns=["user_id", "item_id"])
                db.register("wanted", wanted)
                source = parquet_source(parts)
                rows = db.execute(f"""SELECT w.user_id,w.item_id,sum(c.score) score
                    FROM {source} c JOIN wanted w ON c.user_id=w.user_id AND c.dst_item_id=w.item_id
                    GROUP BY w.user_id,w.item_id""").fetchall()
                scores = {(str(u), str(item)): float(s) for u, item, s in rows}
                records = [(u, item, scores[u, item], rank) for u, items in predictions.items()
                           for rank, item in enumerate(items, 1)]
            cache_paths = parts
        else:
            score_path = directory / ("test_nextitem_index_predictions.npz" if model == "twotower"
                                      else "scan_progress.npz")
            with np.load(score_path, allow_pickle=False) as data:
                indices, values = data["ids"], data["scores"]
            if indices.shape[0] != len(users):
                raise ValueError("Score cache row count differs")
            if model == "content":
                entries = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
                mapping, offset, wanted_ids = {}, 0, set(map(int, indices.ravel()))
                for entry in entries:
                    local = [i for i in wanted_ids if offset <= i < offset + entry["items"]]
                    if local:
                        ids = np.load(p / "matrix_shards" / entry["item_ids"], mmap_mode="r", allow_pickle=False)
                        mapping.update({i: str(ids[i - offset]) for i in local})
                    offset += entry["items"]
            else:
                name = "train_val_item_map.parquet" if model == "als" else "train_item_map.parquet"
                mapping = reverse_mapping(p / "mappings" / name, indices, output)
            records = []
            for user, ids, scores in zip(users.user_id, indices, values):
                mapped = [mapping[int(i)] for i in ids if i >= 0]
                if mapped != predictions[user]:
                    raise ValueError(f"{model}: score/index mapping differs from prediction cache")
                for rank, (i, score) in enumerate(zip(ids, scores), 1):
                    if i >= 0:
                        records.append((user, mapping[int(i)], float(score), rank))
            cache_paths = [score_path]
        frame = pl.DataFrame(records, schema=["user_id", "candidate_item_id", "score", "rank"], orient="row")
        if not frame["score"].is_finite().all():
            raise ValueError(f"{model}: nonfinite retrieval score")
        path = output / f"{model}_sources.parquet"
        frame.write_parquet(path)
        frames.append(path)
        provenance[model] = {"cache": fingerprint(cache_paths + [directory / "test_nextitem_predictions.parquet"]),
                             "metadata": manifest["metadata"], "artifacts": manifest["spec"]["artifacts"],
                             "artifacts_verified": True}
        print(f"Verified {model}: {len(frame):,} scored candidates", flush=True)
    return frames, provenance


def build_features(db, paths, output):
    ctes, columns, flags, rrf = [], [], [], []
    for model, path in zip(MODELS, paths):
        ctes.append(f"{model} AS (SELECT * FROM read_parquet({sqlpath(path)}))")
        columns += [f"coalesce({model}.score,0)::FLOAT {model}_score",
                    f"coalesce({model}.rank,9999)::INTEGER {model}_rank",
                    f"coalesce(1.0-({model}.rank-1.0)/{TOPK[model]-1},0)::FLOAT {model}_score_norm",
                    f"coalesce(1.0/({model}.rank+1.0),0)::FLOAT {model}_rr"]
        flags.append(f"CASE WHEN {model}.rank IS NOT NULL THEN 1 ELSE 0 END")
        rrf.append(f"coalesce(1.0/(60+{model}.rank),0)")
    keys = " UNION ".join(f"SELECT user_id,candidate_item_id FROM {m}" for m in MODELS)
    joins = " ".join(f"LEFT JOIN {m} USING(user_id,candidate_item_id)" for m in MODELS)
    catalog = ROOT / "data/processed/recommender/serving/item_catalog_full.parquet"
    popularity = ROOT / "data/processed/recommender/tables/05_top_popularity_train.csv"
    cats = ",".join(f"coalesce(c.{name},'unknown') candidate_{name}" for name in
                    ("product_id", "brand", "category0", "category1", "category2", "condition", "shipper"))
    sql = f"""WITH {','.join(ctes)}, keys AS ({keys}), fused AS (
        SELECT keys.*, {','.join(columns)}, {'+'.join(flags)} source_count,
            ({'+'.join(rrf)})::FLOAT rrf_score FROM keys {joins})
        SELECT f.*,f.user_id case_id,{cats},coalesce(c.price,0)::FLOAT candidate_price,
            coalesce(p.interactions,0)::FLOAT candidate_popularity
        FROM fused f LEFT JOIN read_parquet({sqlpath(catalog)}) c ON c.item_id=f.candidate_item_id
        LEFT JOIN read_csv_auto({sqlpath(popularity)}) p ON CAST(p.item_id AS VARCHAR)=f.candidate_item_id"""
    path = output / "shared_candidates.parquet"
    db.execute(f"COPY ({sql}) TO {sqlpath(path)} (FORMAT PARQUET, COMPRESSION ZSTD)")
    return path


def run(output, cache, dcn_path, lightgbm_path):
    import lightgbm as lgb
    output.mkdir(parents=True, exist_ok=False)
    ranker_fingerprints = fingerprint([dcn_path, lightgbm_path])
    users, targets, history, manifest = build_future_cases(ROOT, output)
    paths, provenance = restore_sources(cache, users, output, manifest["inference_cohort_hash"])
    target_map = targets.groupby("user_id").item_id.agg(set).to_dict()
    routes = {}
    for model, path in zip(MODELS, paths):
        frame = pd.read_parquet(path).sort_values(["user_id", "rank"])
        routes[model] = frame.groupby("user_id").candidate_item_id.agg(list).to_dict()
    with duckdb.connect() as db:
        db.execute("SET threads=2")
        db.execute("SET memory_limit='2GB'")
        candidates = build_features(db, paths, output)
        frame = pl.read_parquet(candidates)
        checkpoint = torch.load(dcn_path, map_location="cpu", weights_only=False)
        torch.set_num_threads(4)
        model = DCN(checkpoint.get("model_config"))
        model.load_state_dict(checkpoint["model"])
        cats, nums = encode(dcn_feature_frame(frame, checkpoint), checkpoint["num_mean"], checkpoint["num_std"])
        dcn_scores = predict(model, cats, nums, 4096)
        schema = json.loads(lightgbm_path.with_name("feature_schema.json").read_text(encoding="utf-8"))
        encoded, _ = encode_features(frame.to_pandas(), schema["vocabulary"])
        lgb_scores = lgb.Booster(model_file=str(lightgbm_path)).predict(encoded, num_threads=4)
        if not np.isfinite(lgb_scores).all():
            raise ValueError("Nonfinite LightGBM scores")
        scored = frame.select("user_id", "candidate_item_id", "rrf_score").with_columns(
            pl.Series("dcn_score", dcn_scores), pl.Series("lightgbm_score", lgb_scores))
        scored.write_parquet(output / "ranker_scores.parquet")
        discrimination = {name: candidate_discrimination(scored.to_pandas(), targets, column)
                          for name, column in (("RRF", "rrf_score"), ("DCN", "dcn_score"), ("LightGBM", "lightgbm_score"))}
        for name, column in (("RRF", "rrf_score"), ("DCN", "dcn_score"), ("LightGBM", "lightgbm_score")):
            ordered = scored.sort(["user_id", column, "candidate_item_id"], descending=[False, True, False])
            predictions = ordered.group_by("user_id", maintain_order=True).agg(pl.col("candidate_item_id").head(100))
            routes[name] = dict(zip(predictions["user_id"], predictions["candidate_item_id"].to_list()))
            predictions.write_parquet(output / f"{name.lower()}_top100.parquet")
    records = []
    anchors = pd.read_parquet(ROOT / "training/evaluation/results/test_nextitem/test_next_item_cases.parquet")
    if list(anchors.user_id) != list(users.user_id) or not np.array_equal(
            anchors.target_ts.to_numpy(), users.history_cutoff_ts.to_numpy()):
        raise ValueError("Single-target anchor differs from multi-future history cutoff")
    first_targets = anchors[["user_id", "target_item_id"]].rename(columns={"target_item_id": "item_id"})
    first_records = [{"model": name, "protocol": "first_next_item_same_pre_test_anchor",
                      **metrics(first_targets, pred)} for name, pred in routes.items()]
    for name, pred in routes.items():
        for group, gt in (("ALL", targets), ("WARM", targets[targets.is_train_item]),
                          ("COLD", targets[~targets.is_train_item]),
                          ("POSITIVE", targets[targets.is_positive]),
                          ("PURCHASE", targets[targets.is_purchase])):
            records.append({"model": name, "target_group": group, **metrics(gt, pred)})
    pool = scored.group_by("user_id").agg(pl.col("candidate_item_id"))
    pool_preds = dict(zip(pool["user_id"], pool["candidate_item_id"].to_list()))
    pool_hits = sum(len(set(pool_preds.get(u, [])) & gt) for u, gt in target_map.items())
    ordering = [{'model': name, **ranker_metrics(targets, pool_preds, routes[name])}
                for name in ('RRF', 'DCN', 'LightGBM')]
    for name in MODELS:
        _, artifact_paths = artifacts(name, ROOT)
        if provenance[name]["artifacts"] != fingerprint(artifact_paths):
            raise RuntimeError(f"{name}: artifacts changed during evaluation")
    if ranker_fingerprints != fingerprint([dcn_path, lightgbm_path]):
        raise RuntimeError("Ranker checkpoint changed during evaluation")
    report = {"protocol": "merrec_shopee_inspired_temporal_future_items_v1",
              "sources": ["https://arxiv.org/html/2310.19394", "https://arxiv.org/html/2509.18091"],
              "policy": "allow_repeat", "users": len(users), "future_targets": len(targets),
              "history_sources": ["TRAIN", "VAL"], "history_rows": len(history),
              "prediction_time": "before first TEST event per user; fixed snapshot over TEST",
              "retrieval_top_k_per_source": 100, "candidate_rows": len(scored),
              "candidate_target_hits": pool_hits, "candidate_micro_recall": pool_hits / len(targets),
              "exclusive_contribution_at100": exclusive_hits(targets, {m: routes[m] for m in MODELS}),
              "ranking_candidate_proxy": discrimination,
              "conditional_ranker_metrics": ordering,
              "cache_provenance": provenance,
              "ranker_checkpoints": ranker_fingerprints,
              "dcn_feature_source_topk": checkpoint.get('source_topk'),
              "precision_definition": "future target hits divided by K recommendation slots per evaluated user",
              "test_used_for_training_or_selection": False, "targets_used_for_candidate_selection": False,
              "single_next_item_same_anchor": first_records,
              "limitations": ["Not a reproduction of Shopee private data or production architecture",
                  "No impression log: cannot report production CTR/CVR or exposure-based AUC/GAUC",
                  "Existing content catalog/IDF includes future catalog metadata (transductive)",
                  "Rankers trained on final-interaction pools; pre-TEST multi-future context/candidates differ",
                  "Per-source Recall@500 unavailable: verified caches contain top100",
                  "Long-tail percentile not evaluated: full TRAIN item frequency table unavailable",
                  "No online A/B test; existing static Two-Tower and GRU epoch8 artifacts preserved"],
              "results": records}
    pd.DataFrame(records).to_csv(output / "metrics.csv", index=False)
    pd.DataFrame(first_records).to_csv(output / "single_next_item_metrics.csv", index=False)
    pd.DataFrame(ordering).to_csv(output / 'conditional_ranker_metrics.csv', index=False)
    write_json(output / "summary.json", report)
    print(pd.DataFrame(records).query("target_group=='ALL'").to_string(index=False), flush=True)
    return report
