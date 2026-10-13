"""Shared TEST evaluation: recommend products the user will interact with.

Latest user instruction: ground truth is ALL distinct future TEST products/user,
not one first item. History/inference is strictly before TEST interactions.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .nextitem import (MODELS,NAMES,POSITIVE,build_cases,connection,digest,fingerprint,
                       inputs,parquet_source,sqlpath,write_json)

PROTOCOL="test_future_items_v1"


def build_future_cases(root,output,users=5000,seed=20260916):
    root,output=Path(root),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    # Existing common cache defines users and strict history cutoff only.
    # Its first-event item/flags are NEVER used as future ground truth.
    anchor_output=root/"training/evaluation/results/test_nextitem"
    anchors,history,anchor_manifest=build_cases(root,anchor_output,users,seed)
    cohort=anchors[["user_id","target_ts"]].rename(columns={"target_ts":"history_cutoff_ts"})
    paths,base=inputs(root)
    spec={"protocol":PROTOCOL,"history_spec":anchor_manifest["spec"],
          "users_hash":digest(cohort.astype(str).to_dict("records")),
          "inputs":fingerprint(paths["test"]+[base/"train_item_map.parquet"])}
    manifest_path=output/"evaluation_cases_manifest.json"
    target_path=output/"test_future_item_targets.parquet"
    if manifest_path.exists():
        m=json.loads(manifest_path.read_text(encoding="utf-8"))
        if m["spec"]!=spec:
            raise ValueError("Future-target cache khác nguồn/cohort; dùng output mới")
        if target_path.exists():
            targets=pd.read_parquet(target_path)
            validate_future(cohort,targets,history)
            return cohort,targets,history,m
    print("Đọc toàn bộ sản phẩm từng user sẽ tương tác trong TEST...",flush=True)
    with connection(output) as db:
        db.register("cohort",cohort)
        pos=",".join("'"+p+"'" for p in POSITIVE)
        targets=db.execute(f"""WITH t AS (SELECT CAST(e.user_id AS VARCHAR) user_id,
            CAST(e.item_id AS VARCHAR) item_id,min(e.ts) first_interaction_ts,max(e.ts) last_interaction_ts,
            bool_or(coalesce(lower(e.event_group) IN ({pos}),false)) is_positive,
            bool_or(coalesce(e.is_strong_positive=1,false)) is_strong_positive,
            bool_or(coalesce(e.is_purchase=1,false)) is_purchase,
            count(*) interaction_count
            FROM {parquet_source(paths['test'])} e JOIN cohort c
              ON CAST(e.user_id AS VARCHAR)=c.user_id
            WHERE e.item_id IS NOT NULL AND CAST(e.item_id AS VARCHAR)<>''
              AND e.ts>=c.history_cutoff_ts
            GROUP BY e.user_id,e.item_id)
            SELECT t.*,(i.item_id IS NOT NULL) is_train_item FROM t
            LEFT JOIN read_parquet({sqlpath(base/'train_item_map.parquet')}) i
              ON t.item_id=CAST(i.item_id AS VARCHAR) ORDER BY t.user_id,t.item_id""").df()
    validate_future(cohort,targets,history)
    groups={}
    for group in ("ALL","POSITIVE","STRONG","PURCHASE"):
        t=target_subset(targets,group)
        groups[group]={"users":int(t.user_id.nunique()),"targets":len(t),"warm_targets":int(t.is_train_item.sum())}
    m={"spec":spec,"protocol":PROTOCOL,"users":len(cohort),"targets":len(targets),
       "avg_targets_per_user":len(targets)/len(cohort),"warm_targets":int(targets.is_train_item.sum()),
       "groups":groups,"inference_cohort_hash":anchor_manifest["cohort_hash"],
       "targets_hash":digest(targets.astype(str).to_dict("records")),
       "history_rows":len(history),"history_sources":["TRAIN","VAL"],
       "filter_seen_items":False,"test_used_for_tuning":False,"target_definition":"All distinct interacted products per user in TEST"}
    targets.to_parquet(target_path,index=False)
    cohort.to_parquet(output/"test_future_item_users.parquet",index=False)
    write_json(manifest_path,m)
    print(json.dumps({k:m[k] for k in ("users","targets","avg_targets_per_user","warm_targets","groups")}),flush=True)
    return cohort,targets,history,m


def validate_future(users,targets,history):
    if users.user_id.duplicated().any() or targets.duplicated(["user_id","item_id"]).any():
        raise ValueError("User cohort hoặc target (user,item) bị trùng")
    if set(targets.user_id)!=set(users.user_id):
        raise ValueError("Target cohort không đúng user cohort chung")
    t=targets.merge(users,on="user_id",validate="many_to_one")
    h=history.merge(users,on="user_id",validate="many_to_one")
    if not (t.first_interaction_ts>=t.history_cutoff_ts).all():
        raise ValueError("Có target trước history cutoff")
    if not (h.ts<h.history_cutoff_ts).all() or set(h.user_id)!=set(users.user_id):
        raise ValueError("History rò rỉ tương lai hoặc thiếu user")
    if not set(history.source_split).issubset({"train","val"}):
        raise ValueError("Không được tạo history bằng TEST")


def target_subset(targets,group):
    column={"POSITIVE":"is_positive","STRONG":"is_strong_positive","PURCHASE":"is_purchase"}.get(group)
    return targets.loc[targets[column].astype(bool)] if column else targets


def future_metric_rows(users,targets,predictions,model,metadata=None):
    """Macro user Recall, binary-relevance NDCG and first-relevant reciprocal rank."""
    rows=[]
    discount=1/np.log2(np.arange(1,21)+1)
    for scope in ("ALL_CASES","COMMON_WARM"):
        for group in ("ALL","POSITIVE","STRONG","PURCHASE"):
            gt=target_subset(targets,group)
            if scope=="COMMON_WARM":
                gt=gt.loc[gt.is_train_item.astype(bool)]
            sets=gt.groupby("user_id").item_id.agg(set).to_dict()
            recalls={10:[],20:[]}
            ndcgs={10:[],20:[]}
            mrr=[]
            for u,items in sets.items():
                top=list(predictions.get(u,[]))[:20]
                if len(top)!=len(set(top)):
                    raise ValueError("Prediction có item trùng")
                flags=np.array([p in items for p in top],dtype=np.float64)
                hits=np.flatnonzero(flags)
                mrr.append(1/(hits[0]+1) if len(hits) else 0.)
                for k in (10,20):
                    recalls[k].append(float(flags[:k].sum()/len(items)))
                    dcg=float((flags[:k]*discount[:min(k,len(flags))]).sum())
                    idcg=float(discount[:min(k,len(items))].sum())
                    ndcgs[k].append(dcg/idcg)
            n=len(sets)
            row={"split":"TEST","model":NAMES.get(model,model),"target_group":group,"cohort_scope":scope,
                 "users":n,"cohort_users":len(users),"targets":len(gt),"targets_all":len(gt),
                 "warm_targets":int(gt.is_train_item.sum()),
                 "warm_target_coverage":float(gt.is_train_item.mean()) if len(gt) else np.nan,
                 "avg_targets_per_user":len(gt)/n if n else np.nan,
                 "Recall@10":float(np.mean(recalls[10])) if n else np.nan,
                 "Recall@20":float(np.mean(recalls[20])) if n else np.nan,
                 "NDCG@10":float(np.mean(ndcgs[10])) if n else np.nan,
                 "NDCG@20":float(np.mean(ndcgs[20])) if n else np.nan,
                 "MRR@20":float(np.mean(mrr)) if n else np.nan,
                 "status":"COMPLETE" if n else "EMPTY_GROUP","protocol":PROTOCOL}
            row.update(metadata or {})
            rows.append(row)
    return pd.DataFrame(rows)


def evaluate_future_model(model,root,output,users,targets,history,manifest):
    from . import retrievers as r
    root,output=Path(root),Path(output)
    dest=output/model
    dest.mkdir(parents=True,exist_ok=True)
    base_cache=root/"training/evaluation/results/test_nextitem"/model
    cache_pred=base_cache/"test_nextitem_predictions.parquet"
    cache_manifest=base_cache/"evaluation_manifest.json"
    p,paths=r.artifacts(model,root)
    before=fingerprint(paths)
    final_pred=dest/"test_future_item_predictions.parquet"
    final_manifest=dest/"evaluation_manifest.json"
    if final_pred.exists() and final_manifest.exists():
        previous=json.loads(final_manifest.read_text(encoding="utf-8"))
        if previous["artifacts"]!=before or previous["cohort_hash"]!=manifest["spec"]["users_hash"]:
            raise ValueError("Future prediction cache không cùng artifact/history/cohort")
        frame=pd.read_parquet(final_pred)
        if set(frame.user_id)!=set(users.user_id):
            raise ValueError("Future inference cache thiếu hoặc khác users")
        pred={u:list(items) for u,items in zip(frame.user_id,frame.predicted_item_ids)}
        metadata=previous["metadata"].copy()
        source="Existing full-catalog/full-index future prediction cache; no repeated inference"
    elif cache_pred.exists() and cache_manifest.exists():
        previous=json.loads(cache_manifest.read_text(encoding="utf-8"))
        if previous["spec"]["artifacts"]!=before or previous["spec"]["cohort_hash"]!=manifest["inference_cohort_hash"]:
            raise ValueError("Prediction cache không cùng artifact/history/cohort")
        frame=pd.read_parquet(cache_pred)
        if set(frame.user_id)!=set(users.user_id):
            raise ValueError("Inference cache thiếu hoặc khác users")
        pred={u:list(items) for u,items in zip(frame.user_id,frame.predicted_item_ids)}
        metadata=previous["metadata"].copy()
        metadata.pop("cohort_hash",None)
        source="Reused full-catalog predictions: identical user/history/artifacts; no repeated inference"
    else:
        # Resume the in-progress Content scan only after matching its prior signed
        # artifact/cohort/code specification. Only matrix multiplication layout changed.
        legacy_progress=base_cache/"scan_progress.npz"
        signature=digest({"artifacts":before,"history":manifest["inference_cohort_hash"]})
        scan_output=dest
        if model=="content" and legacy_progress.exists():
            prior=json.loads((base_cache.parent/"als/evaluation_manifest.json").read_text(encoding="utf-8"))
            old_spec={"artifacts":before,"cohort_hash":manifest["inference_cohort_hash"],
                      "code":prior["spec"]["code"],"protocol":"test_nextitem_v1"}
            with np.load(legacy_progress,allow_pickle=False) as old:
                if str(old["signature"])!=digest(old_spec):
                    raise ValueError("Không xác thực được partial Content evaluation cache")
                signature=str(old["signature"])
            scan_output=base_cache
        adapters={"content":r.content,"covis":r.covis,"als":r.als,"gru":r.gru_full}
        if model in adapters:
            pred,metadata=adapters[model](p,root,scan_output,users,history,signature)
        else:
            pred,metadata=r.ann(model,p,root,scan_output,users,history,signature)
        source="Fixed artifacts; full-catalog/full-index inference; no training"
    if before!=fingerprint(paths):
        raise RuntimeError("Model artifact thay đổi trong evaluation")
    metadata["cohort_hash"]=manifest["spec"]["users_hash"]
    metadata["targets_hash"]=manifest["targets_hash"]
    results=future_metric_rows(users,targets,pred,model,metadata)
    results.to_csv(dest/"evaluation_nextitem_test.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame({"user_id":list(users.user_id),"predicted_item_ids":[pred.get(u,[]) for u in users.user_id]}).to_parquet(
        dest/"test_future_item_predictions.parquet",index=False)
    write_json(dest/"evaluation_manifest.json",{"protocol":PROTOCOL,"cohort_hash":manifest["spec"]["users_hash"],
        "targets_hash":manifest["targets_hash"],"artifacts":before,"checkpoint_unchanged":True,
        "retrained":False,"test_used_for_tuning":False,"filter_seen_items":False,
        "metadata":metadata,"inference_source":source})
    return results


def summarize_future(output):
    output=Path(output)
    files=[output/m/"evaluation_nextitem_test.csv" for m in MODELS]
    existing=[p for p in files if p.exists()]
    if not existing:
        return None
    df=pd.concat([pd.read_csv(p) for p in existing],ignore_index=True)
    if df.cohort_hash.nunique()!=1 or df.targets_hash.nunique()!=1 or set(df.protocol)!={PROTOCOL}:
        raise ValueError("Không được ghép kết quả khác cohort/ground truth/protocol")
    df.to_csv(output/"next_item_evaluation_summary.csv",index=False,encoding="utf-8-sig")
    return df
