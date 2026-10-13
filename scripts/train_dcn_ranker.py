"""Retrain the notebook DCN with finite TRAIN features and all-case TEST metrics."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

import duckdb
import numpy as np
import polars as pl
import torch
from torch import nn

from scripts.train_lightgbm_ranker import ranking_metrics, validate_candidate_audit

HASH_BUCKETS = {
    "user_id": 50000, "candidate_item_id": 100000,
    "candidate_product_id": 50000, "candidate_brand": 10000,
    "candidate_category0": 2000, "candidate_category1": 5000,
    "candidate_category2": 10000, "candidate_condition": 512,
    "candidate_shipper": 512,
}
SOURCES = ("content", "covis", "als", "gru", "twotower")
NUM_COLUMNS = ["source_count", "rrf_score", "candidate_price", "candidate_popularity"]
NUM_COLUMNS += [f"{source}_{suffix}" for source in SOURCES
                for suffix in ("score", "score_norm", "rank", "rr")]

MODEL_PROFILES = {
    "legacy": {"categorical_features": list(HASH_BUCKETS), "embedding_dim": 8,
               "hidden_dims": [256, 128, 64], "cross_layers": 3, "dropout": .15},
    # Retrieval features retain personalization without memorizing sparse IDs.
    "compact": {"categorical_features": list(HASH_BUCKETS)[3:], "embedding_dim": 4,
                "hidden_dims": [64, 32], "cross_layers": 2, "dropout": .35},
    "numeric": {"categorical_features": [], "embedding_dim": 4,
                "hidden_dims": [32, 16], "cross_layers": 1, "dropout": .5,
                "numeric_clip": 5.},
}


class CrossLayer(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(dim) * .01)
        self.bias = nn.Parameter(torch.zeros(dim))

    def forward(self, x0, x):
        return x0 * (x * self.weight).sum(1, keepdim=True) + self.bias + x


class DCN(nn.Module):
    def __init__(self, config=None):
        super().__init__()
        self.config = dict(MODEL_PROFILES["legacy"] if config is None else config)
        columns = self.config["categorical_features"]
        if len(set(columns)) != len(columns) or any(k not in HASH_BUCKETS for k in columns):
            raise ValueError("Invalid DCN categorical features")
        self.cat_indices = [list(HASH_BUCKETS).index(k) for k in columns]
        embedding_dim = self.config["embedding_dim"]
        self.embeddings = nn.ModuleDict({k: nn.Embedding(HASH_BUCKETS[k], embedding_dim)
                                         for k in columns})
        dim = len(columns) * embedding_dim + len(NUM_COLUMNS)
        self.cross_layers = nn.ModuleList([CrossLayer(dim) for _ in range(self.config["cross_layers"])])
        layers = []
        width = dim
        for hidden in self.config["hidden_dims"]:
            layers += [nn.Linear(width, hidden), nn.ReLU(),
                       nn.LayerNorm(hidden), nn.Dropout(self.config["dropout"])]
            width = hidden
        self.deep = nn.Sequential(*layers)
        self.output = nn.Linear(dim + width, 1)

    def forward(self, cats, nums):
        if self.config.get("numeric_clip") is not None:
            nums = nums.clamp(-self.config["numeric_clip"], self.config["numeric_clip"])
        x0 = torch.cat([self.embeddings[k](cats[:, i])
                        for i, k in zip(self.cat_indices, self.embeddings)] + [nums], dim=1)
        cross = x0
        for layer in self.cross_layers:
            cross = layer(x0, cross)
        return self.output(torch.cat([cross, self.deep(x0)], dim=1)).squeeze(1)


def numeric_features(frame):
    """Impute null/NaN/Inf to zero before transforms and TRAIN standardization."""
    x = frame.select(NUM_COLUMNS).to_numpy().astype(np.float32, copy=True)
    x[~np.isfinite(x)] = 0
    for i, name in enumerate(NUM_COLUMNS):
        if name.endswith("_rank"):
            x[:, i] = 1 / (np.maximum(x[:, i], 0) + 1)
        elif name in ("candidate_price", "candidate_popularity"):
            x[:, i] = np.log1p(np.clip(x[:, i], 0, 1e8))
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite transformed DCN features")
    return x


def fit_scaler(x):
    mean = x.mean(axis=0, dtype=np.float64).astype(np.float32)
    std = x.std(axis=0, dtype=np.float64).astype(np.float32)
    std[std < 1e-6] = 1
    if not np.isfinite(mean).all() or not np.isfinite(std).all():
        raise ValueError("Invalid TRAIN scaler")
    return mean, std


def encode(frame, mean, std):
    cats = frame.select([
        (pl.col(k).cast(pl.String).fill_null("unknown").hash(seed=42)
         % (v - 1) + 1).cast(pl.Int32).alias(k)
        for k, v in HASH_BUCKETS.items()
    ]).to_numpy()
    nums = (numeric_features(frame) - mean) / std
    if not np.isfinite(nums).all():
        raise ValueError("Nonfinite standardized DCN features")
    return torch.from_numpy(cats), torch.from_numpy(nums)


def select_training_candidates(frame, negatives=199):
    """Train pointwise DCN on hittable queries with RRF hard negatives.

    This is a training sampling policy, not a restriction on evaluation cases.
    Queries missing the target cannot teach within-query target ordering.
    """
    if negatives < 1:
        raise ValueError("Need at least one negative per training query")
    if frame["label"].null_count() or not frame["label"].is_in([0, 1]).all():
        raise ValueError("Expected binary labels")
    positives = frame.filter(pl.col("label") == 1)
    if not len(positives):
        raise ValueError("No positive training queries")
    if positives["case_id"].n_unique() != len(positives):
        raise ValueError("Expected one target per training query")
    hittable = frame.join(positives.select("case_id"), on="case_id", how="semi")
    negative_rows = (hittable.filter(pl.col("label") == 0)
                     .sort(["case_id", "rrf_score", "candidate_item_id"],
                           descending=[False, True, False])
                     .group_by("case_id", maintain_order=True).head(negatives))
    negative_rows = negative_rows.select(positives.columns)
    return pl.concat([positives, negative_rows], how="vertical_relaxed").sort(
        ["case_id", "candidate_item_id"])


def positive_weight(labels):
    values = np.asarray(labels, dtype=np.float32)
    if not np.isfinite(values).all() or not np.isin(values, [0, 1]).all():
        raise ValueError("Expected finite binary training labels")
    positives = float(values.sum())
    negatives = len(values) - positives
    if not positives or not negatives:
        raise ValueError("Need positive and negative training examples")
    return negatives / positives


def load_split(path, training=False, negatives=199):
    with duckdb.connect() as db:
        db.execute("SET threads=2")
        db.execute("SET memory_limit='2GB'")
        db.from_parquet(str(path)).create_view("c")
        counts = db.execute("""SELECT count(*), sum(CASE WHEN n>0 THEN 1 ELSE 0 END),
                    max(n) FROM (SELECT case_id,sum(label) n FROM c GROUP BY case_id)
                    """).fetchone()
        if counts[2] != 1:
            raise ValueError("Expected one target per query")
        # TRAIN uses hittable queries. VAL/TEST skip their unnecessary scoring
        # but retain all queries (including retrieval failures) in counts[0].
        sql = """SELECT c.* FROM c SEMI JOIN
            (SELECT case_id FROM c GROUP BY case_id HAVING sum(label)>0) p
            USING(case_id) ORDER BY case_id,candidate_item_id"""
        frame = pl.from_arrow(db.execute(sql).fetch_arrow_table())
        if training:
            frame = select_training_candidates(frame, negatives=negatives)
    return frame, int(counts[0]), int(counts[1])


@torch.inference_mode()
def predict(model, cats, nums, batch_size):
    model.eval()
    chunks = []
    for start in range(0, len(nums), batch_size):
        # Raw logits preserve ordering without sigmoid saturation ties.
        chunks.append(model(cats[start:start+batch_size].long(),
                            nums[start:start+batch_size]).numpy())
    scores = np.concatenate(chunks)
    if not np.isfinite(scores).all():
        raise ValueError("DCN produced nonfinite scores")
    return scores


def evaluate(frame, scores, all_cases):
    data = frame.select(["case_id", "candidate_item_id", "label"]).to_pandas()
    return ranking_metrics(data, scores, all_cases, ks=(10, 20, 50, 100))


def fingerprint(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            sha.update(chunk)
    return {"path": str(path), "size": path.stat().st_size, "sha256": sha.hexdigest()}


def training_probe(path, mean, std, negatives=499, cases=256):
    """Fixed TRAIN diagnostic sample; never used for model selection."""
    with duckdb.connect() as db:
        db.execute("SET threads=2")
        db.execute("SET memory_limit='2GB'")
        db.from_parquet(str(path)).create_view('c')
        selected = "SELECT case_id FROM c GROUP BY case_id HAVING sum(label)=1 ORDER BY hash(case_id,42),case_id LIMIT ?"
        query = f'''SELECT c.* FROM c SEMI JOIN ({selected}) p USING(case_id)
            QUALIFY row_number() OVER(PARTITION BY case_id ORDER BY label DESC,rrf_score DESC,candidate_item_id)<=?
            ORDER BY case_id,candidate_item_id'''
        frame = pl.from_arrow(db.execute(query, [cases, negatives+1]).fetch_arrow_table())
    cats, nums = encode(frame, mean, std)
    return frame.select(['case_id','candidate_item_id','label']), cats, nums


def matched_val_probe(frame, cats, nums, negatives):
    """Diagnostic only: same positive + hard-negative budget as TRAIN probe.

    Official VAL still ranks the complete pool and counts retrieval misses.
    """
    selected = select_training_candidates(frame.with_row_index('_row'), negatives)
    indices = torch.from_numpy(selected['_row'].to_numpy().astype(np.int64))
    return selected.select(['case_id','candidate_item_id','label']), cats[indices], nums[indices]


def prepare_streamed_split(path, cache, training=False, negatives=199, mean=None, std=None):
    """Encode Arrow batches to disk, sampling before materializing any TRAIN rows."""
    import pyarrow.parquet as pq
    cache.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect()
    db.execute("SET threads=2")
    db.execute("SET memory_limit='3GB'")
    db.execute("SET preserve_insertion_order=false")
    db.execute(f"SET temp_directory='{str(cache).replace(chr(39),chr(39)*2)}'")
    db.from_parquet(str(path)).create_view('c')
    db.execute('CREATE TEMP TABLE g AS SELECT case_id,sum(label) n,count(*) row_count FROM c GROUP BY case_id')
    groups = db.execute('SELECT case_id,n,row_count FROM g').fetchall()
    if max(g[1] for g in groups) != 1 or not any(g[1] for g in groups):
        raise ValueError('Expected one target per hittable query')
    if negatives < 1:
        raise ValueError('Need at least one TRAIN negative')
    rows = sum(min(g[2],negatives+1) if training else g[2] for g in groups if g[1])
    pos = sum(g[1]>0 for g in groups)
    cats = np.lib.format.open_memmap(cache/'cats.npy',mode='w+',dtype=np.int32,shape=(rows,len(HASH_BUCKETS)))
    nums = np.lib.format.open_memmap(cache/'nums.npy',mode='w+',dtype=np.float32,shape=(rows,len(NUM_COLUMNS)))
    labels = np.lib.format.open_memmap(cache/'labels.npy',mode='w+',dtype=np.float32,shape=(rows,))
    columns = list(dict.fromkeys(['case_id','candidate_item_id','label','rrf_score',*HASH_BUCKETS,*NUM_COLUMNS]))
    sql = 'SELECT '+','.join('c."'+c+'"' for c in columns)+' FROM c SEMI JOIN g ON c.case_id=g.case_id AND g.n>0'
    if training:
        sql += f' QUALIFY row_number() OVER(PARTITION BY c.case_id ORDER BY label DESC,rrf_score DESC,candidate_item_id)<={negatives+1}'
    sql += ' ORDER BY c.case_id,c.candidate_item_id'
    writer = None
    count = offset = 0
    running_mean = np.zeros(len(NUM_COLUMNS),dtype=np.float64)
    m2 = running_mean.copy()
    try:
        for arrow in db.execute(sql).fetch_record_batch(65536):
            frame = pl.from_arrow(arrow)
            x = numeric_features(frame)
            batch_cats, _ = encode(frame,np.zeros(len(NUM_COLUMNS),np.float32),np.ones(len(NUM_COLUMNS),np.float32))
            n = len(frame)
            cats[offset:offset+n] = batch_cats.numpy()
            nums[offset:offset+n] = x
            labels[offset:offset+n] = frame['label'].to_numpy()
            if training:
                batch_mean = x.mean(0,dtype=np.float64)
                delta = batch_mean-running_mean
                m2 += ((x-batch_mean)**2).sum(0)+delta**2*count*n/(count+n)
                running_mean += delta*n/(count+n)
                count += n
            else:
                keys = frame.select(['case_id','candidate_item_id','label','rrf_score']).to_arrow()
                if writer is None:
                    writer = pq.ParquetWriter(cache/'keys.parquet',keys.schema,compression='zstd')
                writer.write_table(keys)
            offset += n
            if offset % (65536*8) == 0:
                print(f'Preparing {path.stem}: {offset}/{rows} rows',flush=True)
        if offset != rows:
            raise ValueError('Streamed row count differs from query count')
        if training:
            mean = running_mean.astype(np.float32)
            std = np.sqrt(np.maximum(m2/count,0)).astype(np.float32)
            std[std<1e-6]=1
        if mean is None or std is None or not np.isfinite(mean).all() or not np.isfinite(std).all():
            raise ValueError('Invalid TRAIN scaler')
        for start in range(0,rows,65536):
            nums[start:start+65536] = (nums[start:start+65536]-mean)/std
        cats.flush(); nums.flush(); labels.flush()
    finally:
        if writer is not None:
            writer.close()
        db.close()
    return {'cats':torch.from_numpy(cats),'nums':torch.from_numpy(nums),
            'labels':torch.from_numpy(labels),'mean':mean,'std':std,
            'rows':rows,'all_cases':len(groups),'positive_cases':pos,
            'case_ids':{g[0] for g in groups},
            'frame':None if training else pl.read_parquet(cache/'keys.parquet')}


def train(args):
    torch.set_num_threads(args.threads)
    torch.manual_seed(42)
    np.random.seed(42)
    audit = validate_candidate_audit(args.dataset)
    source_topk = audit.get("expansion", {}).get("source_topk")
    args.output.mkdir(parents=True, exist_ok=True)
    best_path = args.output / "model/dcn_best.pt"
    if best_path.exists():
        raise ValueError("Output already contains a checkpoint; use a new directory")
    best_path.parent.mkdir(parents=True, exist_ok=True)
    metric_dir = args.output / "metrics"
    metric_dir.mkdir(parents=True, exist_ok=True)
    paths = {s: args.dataset / f"dcn_{s}.parquet" for s in ("train", "val", "test")}
    fingerprints = {s: fingerprint(p) for s, p in paths.items()}
    streaming = getattr(args,'streaming',False)
    if streaming:
        tr = prepare_streamed_split(paths['train'],args.output/'encoded/train',training=True,negatives=args.train_negatives)
        train_all,train_pos,train_rows = tr['all_cases'],tr['positive_cases'],tr['rows']
        train_case_ids = tr['case_ids']
        mean,std,tc,tn,labels = tr['mean'],tr['std'],tr['cats'],tr['nums'],tr['labels']
        vp = prepare_streamed_split(paths['val'],args.output/'encoded/val',mean=mean,std=std)
        val,val_all,val_pos,vc,vn = vp['frame'],vp['all_cases'],vp['positive_cases'],vp['cats'],vp['nums']
        if train_case_ids.intersection(vp['case_ids']):
            raise ValueError('TRAIN and VAL case IDs overlap')
        weight = (train_rows-train_pos)/train_pos
    else:
        tr, train_all, train_pos = load_split(paths["train"], training=True,negatives=args.train_negatives)
        train_rows = len(tr)
        train_case_ids = set(tr["case_id"])
        val, val_all, val_pos = load_split(paths["val"])
        if train_case_ids.intersection(val["case_id"]):
            raise ValueError("TRAIN and VAL case IDs overlap")
        mean, std = fit_scaler(numeric_features(tr))
        tc, tn = encode(tr, mean, std)
        vc, vn = encode(val, mean, std)
        labels = torch.from_numpy(tr["label"].to_numpy().astype(np.float32))
        weight = positive_weight(labels.numpy())
    if train_rows < 10000:
        raise ValueError("Need at least 10,000 TRAIN candidate rows")
    profile = getattr(args, "profile", "legacy")
    model = DCN(MODEL_PROFILES[profile])
    learning_rate = getattr(args, "learning_rate", None)
    weight_decay = getattr(args, "weight_decay", None)
    learning_rate = learning_rate if learning_rate is not None else {'legacy':1e-3,'compact':3e-4,'numeric':1e-4}[profile]
    weight_decay = weight_decay if weight_decay is not None else {'legacy':1e-5,'compact':1e-3,'numeric':1e-2}[profile]
    parameter_count = sum(p.numel() for p in model.parameters())
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    print(f"DCN profile={profile}, parameters={parameter_count}, config={model.config}, "
          f"learning_rate={learning_rate}, weight_decay={weight_decay}", flush=True)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(weight, dtype=torch.float32))
    print(f"TRAIN {train_all} cases, {train_pos} hittable, {train_rows} sampled rows; "
          f"VAL {val_all} cases, {val_pos} hittable; pos_weight={weight:.3f}; "
          f"CPU threads={args.threads}", flush=True)
    val_baseline = evaluate(val, val["rrf_score"].to_numpy(), val_all)
    print("VAL RRF baseline", json.dumps(val_baseline), flush=True)
    monitor = getattr(args, 'monitor_overfit', False)
    if monitor:
        tp, tpc, tpn = training_probe(paths['train'], mean, std, args.train_negatives)
        mp, mpc, mpn = matched_val_probe(val, vc, vn, args.train_negatives)
    history = []
    best, bad = -1., 0
    for epoch in range(1, args.epochs + 1):
        started = time.perf_counter()
        model.train()
        order = torch.randperm(len(labels))
        loss_sum, batches = 0., 0
        for start in range(0, len(order), args.batch_size):
            ix = order[start:start+args.batch_size]
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(tc[ix].long(), tn[ix]), labels[ix])
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite training loss")
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True)
            optimizer.step()
            loss_sum += loss.item()
            batches += 1
            if batches % 200 == 0:
                print(f"epoch={epoch} rows={min(start+args.batch_size,len(order))}/{len(order)} "
                      f"loss={loss_sum/batches:.6f}", flush=True)
        metrics = evaluate(val, predict(model, vc, vn, args.batch_size), val_all)
        record = {"epoch": epoch, "train_loss": loss_sum / batches, "val": metrics,
                  "epoch_seconds": time.perf_counter() - started,
                  "val_ndcg20_minus_rrf": metrics["NDCG@20"] - val_baseline["NDCG@20"]}
        if monitor:
            tm = evaluate(tp, predict(model, tpc, tpn, args.batch_size), tp['case_id'].n_unique())
            vm = evaluate(mp, predict(model, mpc, mpn, args.batch_size), mp['case_id'].n_unique())
            record['overfit_monitor'] = {
                'protocol': 'hittable_cases_same_hard_negative_budget_diagnostic_only',
                'negatives': args.train_negatives,
                'train_probe': tm, 'val_probe': vm,
                'ndcg20_gap': tm['NDCG@20']-vm['NDCG@20'],
            }
        history.append(record)
        print(json.dumps(record), flush=True)
        if metrics["NDCG@20"] > best:
            best, bad = metrics["NDCG@20"], 0
            torch.save({"model": model.state_dict(), "epoch": epoch,
                        "best_ndcg20": best, "num_mean": mean, "num_std": std,
                        "cat_columns": list(HASH_BUCKETS), "num_columns": NUM_COLUMNS,
                        "hash_buckets": HASH_BUCKETS,
                        "model_config": model.config, "profile": profile,
                        "parameter_count": parameter_count,
                        "learning_rate": learning_rate, "weight_decay": weight_decay,
                        "source_topk": source_topk,
                        "numeric_nonfinite": "zero_before_transforms",
                        "train_query_policy": "positive_queries_only",
                        "train_negatives": args.train_negatives,
                        "pos_weight": weight,
                        "serving_policy": "allow_repeat",
                        "dataset_fingerprints": fingerprints}, best_path)
        else:
            bad += 1
        (metric_dir / "train_history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        if bad >= args.patience:
            break
    del tr, tc, tn, labels, order
    ckpt = torch.load(best_path, map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model"])
    if streaming:
        sp = prepare_streamed_split(paths['test'],args.output/'encoded/test',mean=mean,std=std)
        test,test_all,test_pos,sc,sn = sp['frame'],sp['all_cases'],sp['positive_cases'],sp['cats'],sp['nums']
    else:
        test, test_all, test_pos = load_split(paths["test"])
        sc, sn = encode(test, mean, std)
    if train_case_ids.intersection(test["case_id"]):
        raise ValueError("TRAIN and TEST case IDs overlap")
    if set(val["case_id"]).intersection(test["case_id"]):
        raise ValueError("VAL and TEST case IDs overlap")
    scores = predict(model, sc, sn, args.batch_size)
    metrics = evaluate(test, scores, test_all)
    test_baseline = evaluate(test, test["rrf_score"].to_numpy(), test_all)
    prediction = test.select(["case_id", "candidate_item_id", "label"]).with_columns(pl.Series("dcn_logit", scores))
    prediction.write_parquet(args.output / "test_predictions.parquet")
    report = {"model": "DCN", "protocol": "single_target_current_candidates_all_cases",
              "serving_policy": "allow_repeat", "retrained": True,
              "candidate_audit_history_policy_verified": False,
              "test_used_for_selection": False, "best_epoch": ckpt["epoch"],
              "best_val_ndcg20": best, "train_all_cases": train_all,
              "train_positive_cases": train_pos, "train_sampled_rows": train_rows,
              "train_query_policy": "positive_queries_only", "pos_weight": weight,
              "train_negatives": args.train_negatives,
              "streaming": streaming,
              "profile": profile, "model_config": model.config,
              "overfit_monitor_enabled": monitor,
              "parameter_count": parameter_count,
              "learning_rate": learning_rate, "weight_decay": weight_decay,
              "test_all_cases": test_all, "test_positive_cases": test_pos,
              "test": metrics, "candidate_audit": audit,
              "val_rrf_baseline": val_baseline, "test_rrf_baseline": test_baseline,
              "beats_rrf_on_val": best > val_baseline["NDCG@20"],
              "dataset_fingerprints": fingerprints,
              "torch_version": torch.__version__, "polars_version": pl.__version__,
              "numeric_nonfinite": "zero_before_transforms",
              "checkpoint": str(best_path), "serving_activated": False}
    if fingerprints != {s: fingerprint(p) for s, p in paths.items()}:
        raise ValueError("Dataset changed during training")
    (metric_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "training/dcn/dataset")
    parser.add_argument("--output", type=Path, default=ROOT / "training/dcn_rerun_20261009")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--patience", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--profile", choices=tuple(MODEL_PROFILES), default="numeric",
                        help="Numeric removes embeddings and clips scaled features; legacy reproduces the old architecture")
    parser.add_argument("--learning-rate", type=float, default=None)
    parser.add_argument("--weight-decay", type=float, default=None)
    parser.add_argument("--monitor-overfit", action="store_true",
                        help="Log fixed TRAIN and matched VAL probes; selection still uses full VAL")
    parser.add_argument("--streaming", action="store_true",help="Encode Arrow batches to disk-backed tensors for large datasets")
    parser.add_argument("--train-negatives", type=int, default=199,
                        help="Maximum retrieved negatives per positive TRAIN case")
    train(parser.parse_args())
