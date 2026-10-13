"""Shared, deterministic history anchors and legacy single-target audit utilities.

Only evaluation outputs are written. Training/checkpoint/index paths are read-only.
The current public evaluation uses future_items.py: all TEST products are targets.
Anchor item/flags below are not the ground truth for that public evaluation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PROTOCOL = "test_nextitem_v1"
SEED = 20260916
MODELS = ("content", "covis", "als", "gru", "twotower")
NAMES = dict(zip(MODELS, ("Content-Based", "Co-visitation", "ALS", "GRU4Rec", "Two-Tower")))
POSITIVE = ("like", "cart", "offer", "buy_start", "buy_comp", "add_to_cart", "purchase",
            "add_cart", "make_offer", "purchase_start", "purchase_complete", "buy_complete")


def sqlpath(path):
    return "'" + Path(path).as_posix().replace("'", "''") + "'"


def fingerprint(paths):
    return [{"path": str(Path(p).resolve()), "bytes": Path(p).stat().st_size,
             "mtime_ns": Path(p).stat().st_mtime_ns} for p in sorted(map(Path, paths))]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def connection(output):
    spill = Path(output) / "spill"
    spill.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect()
    db.execute("SET threads=2")
    db.execute("SET memory_limit='384MB'")
    db.execute("SET preserve_insertion_order=false")
    db.execute(f"SET temp_directory={sqlpath(spill)}")
    return db


def inputs(root):
    base = Path(root) / "data/processed/recommender/model_data"
    return {s: sorted((base / "interactions" / f"split={s}").glob("*.parquet"))
            for s in ("train", "val", "test")}, base


def parquet_source(paths):
    return "read_parquet([" + ",".join(sqlpath(p) for p in paths) + "])"


def time_bounds(paths):
    lows, highs = [], []
    for p in paths:
        f = pq.ParquetFile(p)
        idx = f.schema_arrow.names.index("ts")
        for i in range(f.num_row_groups):
            st = f.metadata.row_group(i).column(idx).statistics
            if st is None or not st.has_min_max:
                return None
            lows.append(st.min)
            highs.append(st.max)
    return (min(lows), max(highs)) if lows else None


def validate_cases(cases, history):
    if cases.empty or cases.user_id.duplicated().any():
        raise ValueError("Cases phải không rỗng và mỗi user có đúng một target")
    if cases[["user_id", "target_item_id", "target_ts"]].isna().any().any():
        raise ValueError("Target không hợp lệ")
    if cases.target_item_id.astype(str).eq("").any():
        raise ValueError("Target item_id rỗng")
    check = history.merge(cases[["user_id", "target_ts"]], on="user_id", validate="many_to_one")
    if len(check) != len(history) or not (check.ts < check.target_ts).all():
        raise ValueError("History có sự kiện ngoài cohort hoặc không trước target")
    if set(check.user_id) != set(cases.user_id):
        raise ValueError("Có user không có history trước target")
    if "source_split" in history and not set(history.source_split).issubset({"train", "val"}):
        raise ValueError("History TEST chỉ được đọc TRAIN + VAL")


def build_cases(root, output, users=5000, seed=SEED):
    """First TEST event, ties by item/event/session; no target warmth filtering."""
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    paths, base = inputs(root)
    if any(not p for p in paths.values()):
        raise FileNotFoundError("Thiếu split TRAIN/VAL/TEST")
    sources = [p for ps in paths.values() for p in ps]
    sources += [base / "train_user_map.parquet", base / "train_item_map.parquet"]
    spec = {"protocol": PROTOCOL, "users": int(users), "seed": int(seed), "inputs": fingerprint(sources)}
    manifest_path = output / "cases_manifest.json"
    case_path, history_path = output / "test_next_item_cases.parquet", output / "test_next_item_history.parquet"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["spec"] != spec:
            raise ValueError("Cache khác nguồn/cohort. Chọn --output mới để giữ kết quả hiện có")
        if case_path.exists() and history_path.exists():
            c, h = pd.read_parquet(case_path), pd.read_parquet(history_path)
            validate_cases(c, h)
            return c, h, manifest
    print("Tạo cohort TEST cố định và mốc cắt history...", flush=True)
    with connection(output) as db:
        # Bound first-event aggregation to the deterministic candidate cohort.
        # Overselect without looking at item warmth/behavior; then check first-target validity.
        db.execute(f"""CREATE TEMP TABLE candidate_users AS SELECT * FROM (SELECT DISTINCT CAST(e.user_id AS VARCHAR) user_id
            FROM {parquet_source(paths['test'])} e
            JOIN read_parquet({sqlpath(base / 'train_user_map.parquet')}) u
              ON CAST(e.user_id AS VARCHAR)=CAST(u.user_id AS VARCHAR)
            WHERE e.user_id IS NOT NULL AND e.ts IS NOT NULL)
            ORDER BY md5(user_id || ':{int(seed)}'), user_id LIMIT {int(users)*4}""")
        # Select the first event BEFORE checking target validity.
        db.execute(f"""CREATE TEMP TABLE first_test AS
            SELECT CAST(e.user_id AS VARCHAR) user_id,
              arg_min(struct_pack(item_id:=CAST(item_id AS VARCHAR), event:=event_group,
                ts:=ts, strong:=is_strong_positive, purchase:=is_purchase),
                struct_pack(ts:=ts, item:=coalesce(CAST(item_id AS VARCHAR), ''),
                  event:=coalesce(event_group,''), event_id:=coalesce(event_id,''),
                  session:=coalesce(session_id,''))) t
            FROM {parquet_source(paths['test'])} e JOIN candidate_users u
                ON CAST(e.user_id AS VARCHAR)=u.user_id
            WHERE e.ts IS NOT NULL GROUP BY e.user_id""")
        bounds = {s: time_bounds(ps) for s, ps in paths.items()}
        ordered = all(bounds.values()) and max(bounds['train'][1], bounds['val'][1]) < bounds['test'][0]
        eligible = f"""SELECT f.* FROM first_test f
            INNER JOIN read_parquet({sqlpath(base / 'train_user_map.parquet')}) u
            ON f.user_id=CAST(u.user_id AS VARCHAR)
            WHERE f.t.item_id IS NOT NULL AND f.t.item_id<>''"""
        if not ordered:
            # General fallback: require a genuine prior TRAIN/VAL event before sampling.
            db.execute(f"""CREATE TEMP TABLE min_history AS SELECT CAST(user_id AS VARCHAR) user_id,
                min(ts) ts FROM {parquet_source(paths['train'] + paths['val'])}
                WHERE item_id IS NOT NULL AND ts IS NOT NULL GROUP BY user_id""")
            eligible = f"SELECT e.* FROM ({eligible}) e JOIN min_history h ON e.user_id=h.user_id WHERE h.ts<e.t.ts"
        positive = ",".join("'" + e + "'" for e in POSITIVE)
        db.execute(f"""CREATE TEMP TABLE cohort AS SELECT user_id, t.item_id target_item_id,
            t.event target_event, t.ts target_ts,
            coalesce(lower(t.event) IN ({positive}), false) is_positive,
            coalesce(t.strong=1,false) is_strong_positive,
            coalesce(t.purchase=1,false) is_purchase
            FROM ({eligible}) ORDER BY md5(user_id || ':{int(seed)}'), user_id LIMIT {int(users)}""")
        c = db.execute(f"""SELECT c.*, (i.item_id IS NOT NULL) is_train_item FROM cohort c
            LEFT JOIN read_parquet({sqlpath(base / 'train_item_map.parquet')}) i
            ON c.target_item_id=CAST(i.item_id AS VARCHAR) ORDER BY c.user_id""").df()
        if len(c) != users:
            raise ValueError(f"Chỉ có {len(c)} users hợp lệ; yêu cầu {users}")
        db.register("cases", c)
        chunks = []
        for split in ("train", "val"):
            print(f"Đọc {split.upper()} history cho {len(c):,} users...", flush=True)
            chunks.append(db.execute(f"""SELECT CAST(h.user_id AS VARCHAR) user_id,
                CAST(h.item_id AS VARCHAR) item_id, h.ts, h.event_group,
                CAST(h.event_weight AS DOUBLE) event_weight, h.event_id, h.session_id,
                '{split}' source_split
                FROM {parquet_source(paths[split])} h JOIN cases c
                ON CAST(h.user_id AS VARCHAR)=c.user_id
                WHERE h.item_id IS NOT NULL AND h.ts<c.target_ts""").df())
    h = pd.concat(chunks, ignore_index=True).sort_values(
        ["user_id", "ts", "item_id", "event_group", "event_id", "session_id"], kind="stable")
    validate_cases(c, h)
    manifest = {"spec": spec, "cohort_hash": digest(c.astype(str).to_dict("records")),
                "users": len(c), "targets": len(c), "targets_per_user": 1.0,
                "history_rows": len(h), "warm_targets": int(c.is_train_item.sum()),
                "groups": {g: int(group_mask(c,g).sum()) for g in ("ALL","POSITIVE","STRONG","PURCHASE")},
                "time_bounds": {s: list(map(str,b)) if b else None for s,b in bounds.items()},
                "history_sources": ["TRAIN", "VAL"], "strict_history_before_target": True,
                "test_used_for_tuning": False, "filter_seen_items": False}
    c.to_parquet(case_path, index=False)
    h.to_parquet(history_path, index=False)
    write_json(manifest_path, manifest)
    print(json.dumps({"users":len(c),"history_cutoffs":len(c),"history_rows":len(h)}), flush=True)
    return c,h,manifest


def group_mask(cases, group):
    column = {"POSITIVE":"is_positive", "STRONG":"is_strong_positive", "PURCHASE":"is_purchase"}.get(group)
    return cases[column].astype(bool).to_numpy() if column else np.ones(len(cases), dtype=bool)


def metric_rows(cases, predictions, model, metadata=None, ks=(10,20)):
    """Missing/cold predictions count as MISS; never remove unscorable targets."""
    ks = tuple(sorted(set(ks)))
    if not ks or any(type(k) is not int or k <= 0 for k in ks):
        raise ValueError("K phải là số nguyên dương")
    ranks = np.zeros(len(cases), dtype=np.int32)
    for n, c in enumerate(cases.itertuples(index=False)):
        top = list(predictions.get(c.user_id, []))[:max(20,max(ks))]
        if len(top) != len(set(top)):
            raise ValueError("Top-K chứa item trùng lặp")
        if c.target_item_id in top:
            ranks[n] = top.index(c.target_item_id) + 1
    warm = cases.is_train_item.astype(bool).to_numpy()
    rows = []
    for scope in ("ALL_CASES", "COMMON_WARM"):
        for group in ("ALL", "POSITIVE", "STRONG", "PURCHASE"):
            mask = group_mask(cases, group) & (warm if scope=="COMMON_WARM" else True)
            r = ranks[mask]
            row = {"split":"TEST", "model":NAMES.get(model,model), "target_group":group,
                "cohort_scope":scope, "users":len(r), "targets":len(r), "warm_targets":int(warm[mask].sum()),
                "warm_target_coverage":float(warm[mask].mean()) if len(r) else np.nan,
                "protocol":PROTOCOL, "status":"COMPLETE" if len(r) else "EMPTY_GROUP"}
            for k in ks:
                hit = (r>0) & (r<=k)
                row[f"Recall@{k}"] = float(hit.mean()) if len(r) else np.nan
                row[f"NDCG@{k}"] = float(np.where(hit,1/np.log2(np.maximum(r,1)+1),0).mean()) if len(r) else np.nan
            row["MRR@20"] = float(np.where((r>0)&(r<=20),1/np.maximum(r,1),0).mean()) if len(r) else np.nan
            row.update(metadata or {})
            rows.append(row)
    return pd.DataFrame(rows), ranks


def mapped_values(path, values, output, key="item_id", value="item_idx"):
    with connection(output) as db:
        db.register("wanted", pd.DataFrame({key:list(set(values))}))
        rows=db.execute(f'SELECT CAST(m."{key}" AS VARCHAR),m."{value}" FROM read_parquet(?) m '
                        f'JOIN wanted w ON CAST(m."{key}" AS VARCHAR)=w."{key}"', [str(path)]).fetchall()
    return {str(k):int(v) for k,v in rows}


def reverse_mapping(path, indices, output):
    with connection(output) as db:
        db.register("wanted", pd.DataFrame({"item_idx":np.unique(indices[indices>=0]).astype(np.int64)}))
        rows=db.execute('SELECT m.item_idx,CAST(m.item_id AS VARCHAR) FROM read_parquet(?) m '
                        'JOIN wanted w ON m.item_idx=w.item_idx', [str(path)]).fetchall()
    return {int(k):str(v) for k,v in rows}


def summarize(output):
    output=Path(output)
    files=[output/m/"evaluation_nextitem_test.csv" for m in MODELS]
    existing=[p for p in files if p.exists()]
    if not existing:
        return None
    table=pd.concat([pd.read_csv(p) for p in existing],ignore_index=True)
    table.to_csv(output/"next_item_evaluation_summary.csv",index=False,encoding="utf-8-sig")
    return table
