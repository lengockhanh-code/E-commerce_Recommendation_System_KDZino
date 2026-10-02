"""Adapters for trusted, local MerRec artifacts. Missing models are explicit.

Retrieval scores are computed over the bounded catalog/co-visitation candidate
union, rather than scanning multi-GB embeddings on every web request.
"""

import os
from pathlib import Path
import math
import json

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(os.environ.get("MERREC_MODEL_ROOT", ROOT / "artifacts/merrec_models"))
SOURCES = ("content", "covis", "als", "gru", "twotower")
TOPK = {"content": 150, "covis": 250, "als": 200, "gru": 200, "twotower": 300}


def mapped_indices(path, ids, id_column="item_id", index_column="item_idx"):
    import duckdb
    with duckdb.connect() as db:
        db.execute("SET threads=2")
        rows = db.execute(f'SELECT "{id_column}", "{index_column}" FROM read_parquet(?) WHERE CAST("{id_column}" AS VARCHAR) IN (SELECT unnest(?))', [str(path), ids]).fetchall()
        return {str(key): int(value) for key, value in rows}


def als_scores(rows, payload):
    import numpy as np
    # A memory mapped serving export avoids decompressing 4 GB per request.
    path = Path(os.environ.get("MERREC_ALS_FACTORS_PATH", ARTIFACTS / "ALS/serving/item_factors.npy"))
    if not path.is_file():
        return {}, "needs_mmap_export"
    factors = np.load(path, mmap_mode="r", allow_pickle=False)
    ids = [row["item_id"] for row in rows]
    history = list(dict.fromkeys(event["item_id"] for event in payload["history"]))
    mapping = mapped_indices(ARTIFACTS / "ALS/mappings/train_val_item_map.parquet", ids + history)
    known = [mapping[key] for key in history if key in mapping and mapping[key] < len(factors)]
    if not known:
        return {}, "unmapped_history"
    # Fold in a new online user with fixed, trained item factors (implicit ALS).
    vectors = np.asarray(factors[known], dtype=np.float64)
    gram_path = path.with_name("item_gram.npy")
    if not gram_path.is_file():
        return {}, "needs_mmap_export"
    gram = np.load(gram_path, allow_pickle=False)
    alpha = float(os.environ.get("MERREC_ALS_ALPHA", "40"))
    regularization = float(os.environ.get("MERREC_ALS_REGULARIZATION", "0.15"))
    user = np.linalg.solve(gram + alpha * vectors.T @ vectors + regularization * np.eye(vectors.shape[1]),
                           (1 + alpha) * vectors.sum(axis=0))
    return {key: float(np.dot(factors[mapping[key]], user)) for key in ids if key in mapping and mapping[key] < len(factors)}, "ready"


def gru_scores(rows, payload):
    import torch
    import torch.nn.functional as F
    torch.set_num_threads(2)
    path = ARTIFACTS / "GRU4Rec/model/gru4rec_best_model.pt"
    if not path.is_file():
        return {}, "missing_artifact"
    # Trusted local training checkpoint only; never accept an artifact path from a request.
    checkpoint = torch.load(path, map_location="cpu", weights_only=False, mmap=True)
    state = checkpoint.get("model", checkpoint)
    ids = [row["item_id"] for row in rows]
    history = payload["history"][-100:]
    mapping = mapped_indices(ARTIFACTS / "GRU4Rec/mappings/train_item_map.parquet", ids + [e["item_id"] for e in history])
    history = [e for e in history if e["item_id"] in mapping]
    if not history:
        return {}, "unmapped_history"
    event_ids = {"view": 1, "view_item": 1, "click": 1, "like": 2, "cart": 3, "add_to_cart": 3,
                 "offer": 4, "buy_start": 5, "buy_comp": 6, "purchase": 6}
    item_ids = torch.tensor([[mapping[e["item_id"]] for e in history]])
    events = torch.tensor([[event_ids.get(e["event_type"], 1) for e in history]])
    hidden = state["input_proj.bias"].numel()
    layers = len([key for key in state if key.startswith("gru.weight_ih_l")])
    gru = torch.nn.GRU(hidden, hidden, num_layers=layers, batch_first=True)
    gru.load_state_dict({key[4:]: value for key, value in state.items() if key.startswith("gru.")})
    gru.eval()
    with torch.inference_mode():
        x = torch.cat((F.embedding(item_ids, state["item_emb.weight"]), F.embedding(events, state["event_emb.weight"])), dim=-1)
        x = F.linear(x, state["input_proj.weight"], state["input_proj.bias"])
        x = F.layer_norm(x, (hidden,), state["input_ln.weight"], state["input_ln.bias"])
        encoded, _ = gru(x)
        encoded = F.layer_norm(encoded, (hidden,), state["out_ln.weight"], state["out_ln.bias"])
        query = F.normalize(encoded[:, -1], dim=-1)
        known = [key for key in ids if key in mapping]
        vectors = F.embedding(torch.tensor([mapping[key] for key in known], dtype=torch.long), state["item_emb.weight"])
        vectors = F.normalize(F.linear(vectors, state["item_out.weight"]), dim=-1)
        values = (vectors @ query[0]).tolist()
    return dict(zip(known, values)), "ready"


def twotower_scores(rows, payload):
    import torch
    import faiss
    import numpy as np
    torch.set_num_threads(2)
    mapping = mapped_indices(ARTIFACTS / "TwoTower/mappings/train_user_map.parquet", [payload.get("user_id") or ""], "user_id", "user_idx")
    user_index = mapping.get(payload.get("user_id"))
    if user_index is None:
        return {}, "unmapped_online_user"
    checkpoint = torch.load(ARTIFACTS / "TwoTower/model/two_tower_best_model.pt", map_location="cpu", weights_only=False, mmap=True)
    vector = checkpoint["model"]["user.weight"][user_index].float().numpy()
    vector = vector / max(np.linalg.norm(vector), 1e-12)
    index = faiss.read_index(str(ARTIFACTS / "TwoTower/index/items_ivfpq.faiss"))
    if index.d != len(vector):
        return {}, "incompatible_index"
    # Use the trained ANN item tower and map index IDs explicitly, never by row position.
    faiss.ParameterSpace().set_index_parameter(index, "nprobe", 24)
    scores, indices = index.search(vector.reshape(1, -1), 300)
    candidate_map = mapped_indices(ARTIFACTS / "TwoTower/mappings/train_item_map.parquet", [row["item_id"] for row in rows])
    lookup = dict(zip(indices[0].tolist(), scores[0].tolist()))
    return {key: float(lookup[idx]) for key, idx in candidate_map.items() if idx in lookup}, "ready"


def retrievers_for(payload):
    """Return model retrievers whose training assumptions match this request."""
    wanted = set()
    if int(payload.get("session_distinct_count", 0)) >= 3 or payload.get("segment") == "session":
        wanted.add("gru")
    if payload.get("long_term_eligible") or payload.get("segment") == "warm":
        wanted.update(("als", "twotower"))
    return wanted


def score_retrievers(rows, payload):
    scores, statuses = {}, {}
    wanted = retrievers_for(payload)
    for name, function in (("als", als_scores), ("gru", gru_scores), ("twotower", twotower_scores)):
        if name not in wanted or not rows:
            statuses[name] = "not_applicable"
            continue
        try:
            values, statuses[name] = function(rows, payload)
            scores[name] = {key: value for key, value in values.items() if math.isfinite(value)}
        except (ImportError, OSError, ValueError, RuntimeError, KeyError, IndexError):
            statuses[name] = "unavailable_or_incompatible"
    return scores, statuses


def dcn_predict(features):
    import numpy as np
    import polars as pl
    import torch
    import torch.nn.functional as F
    torch.set_num_threads(2)
    path = Path(os.environ.get("MERREC_DCN_PATH", ROOT / "training/dcn/model/dcn_best.pt"))
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    state = checkpoint["model"]
    columns = checkpoint["cat_columns"]
    frame = pl.DataFrame(features)
    embeddings = []
    for column in columns:
        buckets = checkpoint["hash_buckets"][column]
        ids = frame.select((pl.col(column).cast(pl.String).fill_null("unknown").hash(seed=42) % (buckets - 1) + 1)).to_numpy().reshape(-1)
        embeddings.append(F.embedding(torch.tensor(ids.astype(np.int64)), state[f"embeddings.{column}.weight"]))
    numeric = np.array([[feature[col] for col in checkpoint["num_columns"]] for feature in features], dtype=np.float32)
    for i, name in enumerate(checkpoint["num_columns"]):
        if name.endswith("_rank"):
            numeric[:, i] = 1 / (numeric[:, i] + 1)
        elif name in ("candidate_price", "candidate_popularity"):
            numeric[:, i] = np.log1p(np.clip(numeric[:, i], 0, 1e8))
    numeric = (numeric - checkpoint["num_mean"]) / checkpoint["num_std"]
    with torch.inference_mode():
        x0 = torch.cat(embeddings + [torch.from_numpy(numeric)], dim=1)
        cross = x0
        layer = 0
        while f"cross_layers.{layer}.weight" in state:
            cross = x0 * (cross * state[f"cross_layers.{layer}.weight"]).sum(dim=1, keepdim=True) + state[f"cross_layers.{layer}.bias"] + cross
            layer += 1
        deep = x0
        for layer in (0, 4, 8):
            deep = F.relu(F.linear(deep, state[f"deep.{layer}.weight"], state[f"deep.{layer}.bias"]))
            deep = F.layer_norm(deep, (deep.shape[1],), state[f"deep.{layer + 2}.weight"], state[f"deep.{layer + 2}.bias"])
        return F.linear(torch.cat((cross, deep), dim=1), state["output.weight"], state["output.bias"]).flatten().tolist()


def lightgbm_predict(features):
    """Use the exact feature schema and category coding saved by training."""
    import lightgbm as lgb
    import numpy as np
    import pandas as pd

    default_model = ROOT / "training/lightgbm_ranker/model/lightgbm_ranker.txt"
    path = Path(os.environ.get("MERREC_LIGHTGBM_PATH", default_model))
    if not path.is_absolute():
        path = ROOT / path
    schema_path = path.with_name("feature_schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    expected = schema["features"]
    frame = pd.DataFrame(features)
    if any(column not in frame.columns for column in expected):
        raise ValueError("missing LightGBM feature")
    encoded = pd.DataFrame(index=frame.index)
    for column in schema["categorical"]:
        vocabulary = schema["vocabulary"][column]
        lookup = {value: index for index, value in enumerate(vocabulary)}
        encoded[column] = pd.Categorical(
            frame[column].fillna("unknown").astype(str).map(lookup),
            categories=range(len(lookup)), ordered=False)
    for column in expected:
        if column in schema["categorical"]:
            continue
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=np.float32, copy=True)
        values[~np.isfinite(values)] = np.nan
        encoded[column] = values
    model = lgb.Booster(model_file=str(path))
    if model.feature_name() != expected:
        raise ValueError("LightGBM feature schema differs from checkpoint")
    return model.predict(encoded[expected], num_threads=2).tolist()


def rank_candidates(features, baseline):
    if not features:
        return [], "empty", {}
    configured = os.environ.get("MERREC_RANKER", "rules")
    statuses = {}
    if configured not in ("dcn", "lightgbm"):
        return baseline, "hybrid_feature_ranker_v2", {"dcn": "not_applicable", "lightgbm": "not_in_use"}
    if configured == "lightgbm":
        model_path = Path(os.environ.get(
            "MERREC_LIGHTGBM_PATH", ROOT / "training/lightgbm_ranker/model/lightgbm_ranker.txt"))
        if not model_path.is_absolute():
            model_path = ROOT / model_path
        try:
            serving_schema = json.loads(
                model_path.with_name("feature_schema.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            return baseline, "hybrid_feature_ranker_v2", {
                "lightgbm": "unavailable_or_incompatible", "dcn": "not_in_use"}
        if not serving_schema.get("accepted_for_serving", False):
            return baseline, "hybrid_feature_ranker_v2", {
                "lightgbm": "rejected_by_offline_gate", "dcn": "not_in_use"}
        if serving_schema.get("serving_policy") != "exclude_history":
            return baseline, "hybrid_feature_ranker_v2", {
                "lightgbm": "offline_online_policy_mismatch", "dcn": "not_in_use"}
    predictions = []
    fn = dcn_predict if configured == "dcn" else lightgbm_predict
    for name, predictor in ((configured, fn),):
        try:
            values = predictor(features)
            if len(values) != len(features) or not all(math.isfinite(v) for v in values):
                raise ValueError("invalid prediction")
            # Rank normalization makes hybrid scores comparable.
            order = sorted(range(len(values)), key=lambda i: values[i])
            normalized = [0.0] * len(values)
            for rank, idx in enumerate(order):
                normalized[idx] = rank / max(1, len(values) - 1)
            predictions.append((name, normalized))
            statuses[name] = "ready"
        except (ImportError, OSError, ValueError, RuntimeError, KeyError):
            statuses[name] = "unavailable_or_incompatible"
    if not predictions:
        statuses["dcn" if configured == "lightgbm" else "lightgbm"] = "not_in_use"
        return baseline, "hybrid_feature_ranker_v2", statuses
    # Preserve explicit interest signals while the offline ranker adapts to live traffic.
    model_weight = .65
    if configured == "lightgbm":
        model_weight = float(serving_schema["serving_model_weight"])
    lo, hi = min(baseline), max(baseline)
    scores = [model_weight * sum(values[i] for _, values in predictions) / len(predictions) +
              (1 - model_weight) * (baseline[i] - lo) / max(hi - lo, 1e-8) for i in range(len(features))]
    statuses["dcn" if configured == "lightgbm" else "lightgbm"] = "not_in_use"
    return scores, configured, statuses
