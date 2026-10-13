"""Inference adapters for fixed artifacts; no fit, tuning, or seen-item masking."""
from __future__ import annotations

import gc
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .nextitem import (connection, digest, fingerprint, mapped_values, metric_rows,
                       reverse_mapping, sqlpath, write_json)


def artifacts(model, root):
    root=Path(root)
    base=root/"artifacts/merrec_models"
    if model=="content":
        p=root/"training/checkpoints/content_based_full_catalog"
        manifest=json.loads((p/"manifest.json").read_text(encoding="utf-8"))
        paths=[p/n for n in ("manifest.json","meta.json","hashing_vectorizer.joblib","idf.npy")]
        paths += [p/"matrix_shards"/s[k] for s in manifest for k in ("matrix","item_ids")]
        paths.append(root/"data/processed/recommender/serving/item_catalog_full.parquet")
        return p,paths
    if model=="covis":
        p=root/"training/checkpoints/covisitation/polars_v2"
        paths=[p/"tuning/best_config.json",p/"models/train_val/_MODEL_COMPLETE.json"]
        paths+=sorted((p/"models/train_val/model").glob("bucket_*.parquet"))
        if len(paths)!=130:
            raise ValueError("Co-visitation cần đủ 128 bucket model TRAIN+VAL")
        return p,paths
    folder={"als":"ALS","gru":"GRU4Rec","twotower":"TwoTower"}[model]
    p=base/folder
    names={"als":["model/final_model.npz","serving/item_factors.npy","serving/item_gram.npy",
                  "serving/als_config.json","mappings/train_val_item_map.parquet"],
           "gru":["model/gru4rec_best_model.pt","index/items_ivfpq.faiss",
                  "serving/gru4rec_config.json","mappings/train_item_map.parquet"],
           "twotower":["model/two_tower_best_model.pt","index/items_ivfpq.faiss",
                  "serving/twotower_config.json","mappings/train_item_map.parquet","mappings/train_user_map.parquet"]}[model]
    paths=[p/n for n in names]
    if model=="twotower":
        cfg=json.loads((p/"serving/twotower_config.json").read_text(encoding="utf-8"))["cfg"]
        if cfg.get("architecture_version",1)>=2:
            paths += [p/"features"/(f+".npy") for f in [*cfg["hash_buckets"],"price_z"]]
    return p,paths


def aggregate_history(history, max_items=None, hash_ties=False):
    with connection(Path(history.attrs.get("output", "."))) as db:
        db.register("history",history)
        tie="hash(item_id)" if hash_ties else "item_id"
        return db.execute(f"""WITH a AS (SELECT user_id,item_id,sum(event_weight) strength,max(ts) last_ts
              FROM history GROUP BY user_id,item_id), r AS (SELECT *,row_number() OVER
              (PARTITION BY user_id ORDER BY last_ts DESC,strength DESC,{tie}) hist_rank FROM a)
              SELECT * FROM r {'WHERE hist_rank<='+str(int(max_items)) if max_items else ''}
              ORDER BY user_id,hist_rank""").df()


def top_local(scores, ids, k=20):
    """Exact top-K with deterministic ties by index; includes implicit zero scores."""
    k=min(k,len(scores))
    if not k:
        return np.empty(0,dtype=np.int64),np.empty(0,dtype=np.float32)
    if not np.isfinite(scores).all():
        raise ValueError("Model có score NaN/Inf")
    pos=np.argpartition(scores,len(scores)-k)[-k:]
    threshold=scores[pos].min()
    above=np.flatnonzero(scores>threshold)
    ties=np.flatnonzero(scores==threshold)
    # ids are sorted in dense catalog chunks; merge calls use at most 40 entries.
    ties=ties[np.argsort(ids[ties],kind="stable")[:k-len(above)]]
    pos=np.concatenate([above,ties])
    pos=pos[np.lexsort((ids[pos],-scores[pos]))][:k]
    return ids[pos],scores[pos]


def merge_top(best_ids,best_scores,row,ids,scores,k=20):
    merged_ids=np.concatenate([best_ids[row],ids])
    merged_scores=np.concatenate([best_scores[row],scores])
    best_ids[row],best_scores[row]=top_local(merged_scores,merged_ids,k=k)


def save_progress(output, number, best_ids, best_scores, signature):
    path=Path(output)/"scan_progress.npz"
    tmp=path.with_suffix(".tmp.npz")
    np.savez(tmp,number=number,ids=np.stack(best_ids),scores=np.stack(best_scores),signature=signature)
    tmp.replace(path)


def load_progress(output,n,signature):
    path=Path(output)/"scan_progress.npz"
    if path.exists():
        with np.load(path,allow_pickle=False) as old:
            if str(old['signature'])==signature:
                return int(old['number']),list(old['ids']),list(old['scores'])
            raise ValueError("Checkpoint scan evaluation không cùng model/cohort")
    return 0,[np.empty(0,dtype=np.int64) for _ in range(n)],[np.empty(0,dtype=np.float32) for _ in range(n)]


def content(p,root,output,cases,history,signature,top_k=20):
    import joblib
    import scipy.sparse as sp
    from sklearn.preprocessing import normalize
    meta=json.loads((p/"meta.json").read_text(encoding="utf-8"))
    entries=json.loads((p/"manifest.json").read_text(encoding="utf-8"))
    if sum(e["items"] for e in entries)!=meta["candidate_items"]:
        raise ValueError("Manifest Content-Based chưa đủ catalog")
    history.attrs["output"]=str(output)
    seeds=aggregate_history(history,100,hash_ties=True)
    with connection(output) as db:
        db.register("seeds",seeds)
        cat=Path(root)/"data/processed/recommender/serving/item_catalog_full.parquet"
        rows=db.execute(f"""SELECT s.*,c.name,c.price,c.category0,c.category1,c.category2,c.brand,c.condition
            FROM seeds s JOIN read_parquet({sqlpath(cat)}) c ON s.item_id=CAST(c.item_id AS VARCHAR)
            ORDER BY s.user_id,s.hist_rank""").df()
    hasher=joblib.load(p/"hashing_vectorizer.joblib")
    texts=rows.name.fillna("").astype(str).str.lower()
    for col,prefix in (("category0","c0"),("category1","c1"),("category2","c2"),("brand","brand"),("condition","condition")):
        tokens=rows[col].map(lambda v:prefix+"_"+"_".join(str("__UNK__" if pd.isna(v) else v).strip().lower().split()))
        texts=texts+" "+tokens
    x=hasher.transform(texts).tocsr()
    x.data=(1+np.log(x.data)).astype(np.float32)
    x=x.multiply(np.load(p/"idf.npy",mmap_mode="r")).tocsr()
    price=np.log1p(np.maximum(rows.price.fillna(0).to_numpy(dtype=np.float32),0))
    price=((price-meta["price_log_mean"])/meta["price_log_std"]*meta["price_weight"]).astype(np.float32)
    x=normalize(sp.hstack([x,sp.csr_matrix(price[:,None])],format="csr"),copy=False)
    user_idx={u:i for i,u in enumerate(cases.user_id)}
    weights=(np.log1p(np.maximum(rows.strength.to_numpy(dtype=np.float32),0))*
             np.power(.97,rows.hist_rank.to_numpy()-1)).astype(np.float32)
    w=sp.csr_matrix((weights,(rows.user_id.map(user_idx).to_numpy(),np.arange(len(rows)))),
                    shape=(len(cases),len(rows)))
    profiles=normalize((w@x).tocsr(),copy=False).astype(np.float32)
    sp.save_npz(output/"test_nextitem_profiles.npz",profiles)
    del rows,x,w,seeds,texts
    gc.collect()
    done,best_ids,best_scores=load_progress(output,len(cases),signature)
    # Algebraically identical sparse/dense decomposition, chosen from history profiles.
    # Frequent features (including price) cause a nearly dense sparse product; BLAS
    # computes those terms efficiently. Query-major contiguous rows speed exact Top-K.
    common_columns=np.argsort(profiles.getnnz(axis=0))[-128:]
    dense_queries=profiles[:,common_columns].toarray()
    feature_mask=np.ones(profiles.shape[1],dtype=np.float32)
    feature_mask[common_columns]=0
    offset=sum(e["items"] for e in entries[:done])
    for shard_no,e in enumerate(entries[done:],start=done+1):
        matrix=sp.load_npz(p/"matrix_shards"/e["matrix"]).tocsr()
        ids=np.arange(offset,offset+matrix.shape[0],dtype=np.int64)
        if matrix.shape!=(e["items"],meta["matrix_features"]):
            raise ValueError("Sai shape Content-Based shard")
        dense_items=matrix[:,common_columns].toarray()
        residual=matrix.multiply(feature_mask).tocsr()
        residual.eliminate_zeros()
        for start in range(0,len(cases),256):
            end=min(start+256,len(cases))
            scores=(profiles[start:end]@residual.T).toarray()
            scores+=dense_queries[start:end]@dense_items.T
            for j,row in enumerate(scores):
                local_ids,local_scores=top_local(row,ids,k=top_k)
                merge_top(best_ids,best_scores,start+j,local_ids,local_scores,k=top_k)
            del scores
        offset+=e["items"]
        save_progress(output,shard_no,best_ids,best_scores,signature)
        print(f"Content-Based full catalog: {shard_no}/{len(entries)} shards",flush=True)
        del matrix,residual,dense_items
        gc.collect()
    wanted=set(int(i) for row in best_ids for i in row)
    mapping={}
    offset=0
    for e in entries:
        local=[i for i in wanted if offset<=i<offset+e["items"]]
        if local:
            ids=np.load(p/"matrix_shards"/e["item_ids"],mmap_mode="r",allow_pickle=False)
            mapping.update({i:str(ids[i-offset]) for i in local})
        offset+=e["items"]
    pred={u:[mapping[int(i)] for i in row] for u,row in zip(cases.user_id,best_ids)}
    return pred,{"retrieval_type":"EXACT_FULL_CATALOG","model_catalog_items":meta["candidate_items"],
                 "artifact_note":"Existing transductive catalog/IDF: metadata_scope=train+val+test; no TEST behavior used",
                 "history_limit":100,"filter_seen_items":False}


def covis(p,root,output,cases,history,signature,top_k=20):
    cfg=json.loads((p/"tuning/best_config.json").read_text(encoding="utf-8"))
    history.attrs["output"]=str(output)
    seeds=aggregate_history(history,cfg["history_items"])
    with connection(output) as db:
        db.register("seeds",seeds)
        buckets=sorted((p/"models/train_val/model").glob("bucket_*.parquet"))
        # Read the entire persisted model index; new eval caches have no old seen anti-join.
        parts=[]
        for n,bucket in enumerate(buckets,1):
            path=output/f"test_nextitem_candidates_{n:03d}.parquet"
            query=f"""SELECT s.user_id,m.dst_item_id,
                 sum(ln(1+greatest(s.strength,0))*pow({cfg['decay']},s.hist_rank-1)*
                     ln(1+greatest(m.forward_score+{cfg['reverse_weight']}*m.reverse_score,0)) /
                     pow(1+greatest(m.dst_strength,0),{cfg['popularity_penalty']})) score
                 FROM seeds s JOIN read_parquet({sqlpath(bucket)}) m ON s.item_id=m.src_item_id
                 GROUP BY s.user_id,m.dst_item_id"""
            db.execute(f"COPY ({query}) TO {sqlpath(path)} (FORMAT PARQUET,COMPRESSION ZSTD)")
            parts.append(path)
            if n%8==0:
                print(f"Co-visitation full index: {n}/128 buckets",flush=True)
        source="read_parquet(["+",".join(sqlpath(p) for p in parts)+"])"
        ranked=db.execute(f"""WITH a AS (SELECT user_id,dst_item_id,sum(score) score FROM {source}
            GROUP BY user_id,dst_item_id),r AS (SELECT *,row_number() OVER
            (PARTITION BY user_id ORDER BY score DESC,dst_item_id) rank FROM a)
            SELECT * FROM r WHERE rank<={int(top_k)} ORDER BY user_id,rank""").df()
    pred=ranked.groupby("user_id").dst_item_id.agg(list).to_dict()
    return pred,{"retrieval_type":"FULL_PERSISTED_PAIR_INDEX","model_catalog_items":None,
        "history_limit":cfg["history_items"],"filter_seen_items":False,
        "artifact_note":"TRAIN+VAL pair tables; fixed pre-TEST selected parameters"}


def fold_in(vectors,confidence,gram,regularization):
    """Same fixed-item least-squares inference as implicit.recalculate_user (no model fit)."""
    y=np.asarray(vectors,dtype=np.float64)
    c=np.asarray(confidence,dtype=np.float64)
    a=np.asarray(gram,dtype=np.float64)+(y.T*(c-1))@y+regularization*np.eye(y.shape[1])
    return np.linalg.solve(a,y.T@c).astype(np.float32)


def als(p,root,output,cases,history,signature,top_k=20):
    cfg=json.loads((p/"serving/als_config.json").read_text(encoding="utf-8"))
    factors=np.load(p/"serving/item_factors.npy",mmap_mode="r",allow_pickle=False)
    gram=np.load(p/"serving/item_gram.npy",allow_pickle=False)
    history.attrs["output"]=str(output)
    seeds=aggregate_history(history)
    mapping=mapped_values(p/"mappings/train_val_item_map.parquet",seeds.item_id,output)
    seeds["item_idx"]=seeds.item_id.map(mapping)
    seeds=seeds.dropna(subset=["item_idx"])
    vectors={}
    for u,h in seeds.groupby("user_id",sort=False):
        ids=h.item_idx.to_numpy(dtype=np.int64)
        confidence=float(cfg["alpha"])*np.log1p(h.strength.to_numpy(dtype=np.float64))
        if (confidence<=0).any():
            raise ValueError("ALS confidence phải dương")
        vectors[u]=fold_in(factors[ids],confidence,gram,float(cfg["regularization"]))
    query=np.stack([vectors.get(u,np.zeros(factors.shape[1],dtype=np.float32)) for u in cases.user_id])
    # Inference-only user fold-in; fixed trained item factors/weights remain unchanged.
    np.save(output/"test_nextitem_user_queries.npy",query)
    del seeds,mapping,vectors
    gc.collect()
    done,best_ids,best_scores=load_progress(output,len(cases),signature)
    chunk=100000
    chunks=(len(factors)+chunk-1)//chunk
    for n in range(done,chunks):
        start=n*chunk
        y=np.asarray(factors[start:start+chunk])
        ids=np.arange(start,start+len(y),dtype=np.int64)
        for st in range(0,len(cases),128):
            scores=query[st:st+128]@y.T
            for j,row in enumerate(scores):
                local_ids,local_scores=top_local(row,ids,k=top_k)
                merge_top(best_ids,best_scores,st+j,local_ids,local_scores,k=top_k)
        save_progress(output,n+1,best_ids,best_scores,signature)
        if (n+1)%5==0 or n+1==chunks:
            print(f"ALS exact full catalog: {n+1}/{chunks} chunks",flush=True)
    mapping=reverse_mapping(p/"mappings/train_val_item_map.parquet",np.stack(best_ids),output)
    pred={u:[mapping[int(i)] for i in row] for u,row in zip(cases.user_id,best_ids)}
    return pred,{"retrieval_type":"EXACT_FULL_CATALOG","model_catalog_items":len(factors),
                 "history_limit":None,"filter_seen_items":False,
                 "artifact_note":"TRAIN+VAL checkpoint; inference-only weighted user fold-in with fixed item factors"}


EVENT_IDS={"unknown":0,"view":1,"view_item":1,"click":1,"like":2,"cart":3,"add_to_cart":3,
           "offer":4,"make_offer":4,"buy_start":5,"purchase_start":5,
           "buy_comp":6,"purchase":6,"purchase_complete":6,"buy_complete":6}


def gru_queries(state,history,cases,mapping,max_len=100):
    import torch
    import torch.nn.functional as f
    torch.set_num_threads(2)
    hidden=state["input_proj.bias"].numel()
    layers=sum(k.startswith("gru.weight_ih_l") for k in state)
    gru=torch.nn.GRU(hidden,hidden,num_layers=layers,batch_first=True)
    gru.load_state_dict({k[4:]:v for k,v in state.items() if k.startswith("gru.")})
    gru.eval()
    rows=history.groupby("user_id",sort=False).tail(max_len)
    grouped={u:h for u,h in rows.groupby("user_id",sort=False)}
    result=[]
    with torch.inference_mode():
        for start in range(0,len(cases),64):
            users=list(cases.user_id.iloc[start:start+64])
            xi=torch.zeros((len(users),max_len),dtype=torch.long)
            xe=torch.zeros_like(xi)
            lengths=[]
            for j,u in enumerate(users):
                h=grouped[u]
                ids=[mapping.get(v,1) for v in h.item_id]
                events=[EVENT_IDS.get(str(v).lower(),0) for v in h.event_group]
                xi[j,:len(ids)]=torch.tensor(ids)
                xe[j,:len(ids)]=torch.tensor(events)
                lengths.append(len(ids))
            x=torch.cat((f.embedding(xi,state["item_emb.weight"],padding_idx=0),
                         f.embedding(xe,state["event_emb.weight"])),dim=-1)
            x=f.linear(x,state["input_proj.weight"],state["input_proj.bias"])
            x=f.layer_norm(x,(hidden,),state["input_ln.weight"],state["input_ln.bias"])
            x,_=gru(x)
            x=f.layer_norm(x,(hidden,),state["out_ln.weight"],state["out_ln.bias"])
            q=f.normalize(x[torch.arange(len(users)),torch.tensor(lengths)-1],dim=-1)
            result.append(q.numpy().astype(np.float32))
    return np.concatenate(result)


def gru_full(p,root,output,cases,history,signature,top_k=20):
    """Exact full-catalog GRU scoring; saved 32-D index cannot accept 128-D queries.

    q dot normalize(W e) = ((q W) dot e) / ||W e||.
    This computes the original model's scores without changing either tower.
    """
    import torch
    torch.set_num_threads(2)
    cfg=json.loads((p/"serving/gru4rec_config.json").read_text(encoding="utf-8"))
    ckpt=torch.load(p/"model/gru4rec_best_model.pt",map_location="cpu",weights_only=False,mmap=True)
    state=ckpt["model"]
    short=history.groupby("user_id",sort=False).tail(cfg["max_seq_len"])
    mapping=mapped_values(p/"mappings/train_item_map.parquet",short.item_id,output)
    q=gru_queries(state,history,cases,mapping,cfg["max_seq_len"])
    projection=state["item_out.weight"].numpy()
    query=q@projection
    embeddings=state["item_emb.weight"].numpy()
    if len(embeddings)!=ckpt["vocab_size"]:
        raise ValueError("GRU vocab_size không đúng checkpoint")
    np.save(output/"test_nextitem_user_queries.npy",q)
    del short,mapping,q
    gc.collect()
    done,best_ids,best_scores=load_progress(output,len(cases),signature)
    chunk=100000
    total=len(embeddings)-2
    chunks=(total+chunk-1)//chunk
    for n in range(done,chunks):
        start=2+n*chunk
        y=embeddings[start:min(start+chunk,len(embeddings))]
        norms=np.maximum(np.linalg.norm(y@projection.T,axis=1),1e-12)
        ids=np.arange(start,start+len(y),dtype=np.int64)
        for st in range(0,len(cases),128):
            scores=(query[st:st+128]@y.T)/norms[None,:]
            for j,row in enumerate(scores):
                local_ids,local_scores=top_local(row,ids,k=top_k)
                merge_top(best_ids,best_scores,st+j,local_ids,local_scores,k=top_k)
        save_progress(output,n+1,best_ids,best_scores,signature)
        if (n+1)%5==0 or n+1==chunks:
            print(f"GRU4Rec exact full catalog: {n+1}/{chunks} chunks",flush=True)
    mapping=reverse_mapping(p/"mappings/train_item_map.parquet",np.stack(best_ids),output)
    pred={u:[mapping[int(i)] for i in row] for u,row in zip(cases.user_id,best_ids)}
    return pred,{"retrieval_type":"EXACT_FULL_CATALOG","model_catalog_items":total,
                 "history_limit":cfg["max_seq_len"],"filter_seen_items":False,
                 "artifact_note":f"Existing checkpoint epoch={ckpt.get('epoch')}; reported best epoch={ckpt.get('best_epoch')}. Exact scoring bypasses incompatible 32-D index; original 128-D encoder/item projection retained"}


def ann(model,p,root,output,cases,history,signature,top_k=20):
    import faiss
    import torch
    import torch.nn.functional as f
    torch.set_num_threads(2)
    faiss.omp_set_num_threads(2)
    if model=="gru":
        cfg=json.loads((p/"serving/gru4rec_config.json").read_text(encoding="utf-8"))
        ckpt=torch.load(p/"model/gru4rec_best_model.pt",map_location="cpu",weights_only=False,mmap=True)
        short=history.groupby("user_id",sort=False).tail(cfg["max_seq_len"])
        mapping=mapped_values(p/"mappings/train_item_map.parquet",short.item_id,output)
        q=gru_queries(ckpt["model"],history,cases,mapping,cfg["max_seq_len"])
        nprobe=int(cfg["faiss"]["nprobe"])
        expected=ckpt["vocab_size"]-2
        notes=f"Full GRU encoder; existing checkpoint epoch={ckpt.get('epoch')}; reported best epoch={ckpt.get('best_epoch')}; existing index provenance must be interpreted as provided"
    else:
        cfg=json.loads((p/"serving/twotower_config.json").read_text(encoding="utf-8"))["cfg"]
        ckpt=torch.load(p/"model/two_tower_best_model.pt",map_location="cpu",weights_only=False,mmap=True)
        mapping=mapped_values(p/"mappings/train_user_map.parquet",cases.user_id,output,"user_id","user_idx")
        from scripts.twotower_history import user_queries, uses_history
        if uses_history(ckpt):
            ordered=history.sort_values(["user_id","ts","item_id"],kind="stable")
            item_mapping=mapped_values(p/"mappings/train_item_map.parquet",ordered.item_id,output)
            sequences={u:[item_mapping[i] for i in rows.item_id if i in item_mapping]
                       for u,rows in ordered.groupby("user_id",sort=False)}
            q=user_queries(ckpt,[mapping.get(u,-1) for u in cases.user_id],
                           [sequences.get(u,[]) for u in cases.user_id],p/"features")
            notes="History-aware user tower; chronological history before the evaluation anchor; repeats allowed"
        else:
            q=user_queries(ckpt,[mapping.get(u,-1) for u in cases.user_id])
            notes="Legacy ID-only user tower; TRAIN+VAL history does not update this checkpoint"
        nprobe=int(cfg["faiss_nprobe"])
        expected=int(ckpt["n_items"])
    np.save(output/"test_nextitem_user_queries.npy",q)
    del ckpt,mapping
    gc.collect()
    print(f"Đọc {model} full FAISS index...",flush=True)
    index=faiss.read_index(str(p/"index/items_ivfpq.faiss"))
    if index.ntotal!=expected or index.d!=q.shape[1]:
        raise ValueError(f"Index/model không tương thích: ntotal={index.ntotal},expected={expected},d={index.d},query={q.shape[1]}")
    faiss.ParameterSpace().set_index_parameter(index,"nprobe",nprobe)
    print(f"FAISS full index: {index.ntotal:,} items; d={index.d}; nprobe={nprobe}",flush=True)
    scores,ids=index.search(q,top_k)
    total=index.ntotal
    del index
    gc.collect()
    np.savez(output/"test_nextitem_index_predictions.npz",ids=ids,scores=scores)
    mapping=reverse_mapping(p/"mappings/train_item_map.parquet",ids,output)
    missing=set(int(i) for i in ids.ravel() if i>=0)-set(mapping)
    if missing:
        raise ValueError("Index IDs không thuộc mapping; không được đổi index ID sang row offset")
    pred={u:[mapping[int(i)] for i in row if i>=0] for u,row in zip(cases.user_id,ids)}
    return pred,{"retrieval_type":"ANN_FULL_MODEL_INDEX","model_catalog_items":total,
                 "nprobe":nprobe,"filter_seen_items":False,"artifact_note":notes,
                 "history_limit":100 if model=="gru" else cfg.get("history_length")}


def evaluate(model,root,output,cases,history,manifest,ks=(10,20)):
    ks=tuple(sorted(set(ks)))
    if not ks or any(type(k) is not int or k<=0 for k in ks):
        raise ValueError("K ph?i l? s? nguy?n d??ng")
    top_k=max(20,max(ks))
    p,paths=artifacts(model,root)
    before=fingerprint(paths)
    dest=Path(output)/model
    dest.mkdir(parents=True,exist_ok=True)
    code_paths=[Path(__file__),Path(__file__).with_name("nextitem.py")]
    if model=="twotower": code_paths.append(Path(root)/"scripts/twotower_history.py")
    code=fingerprint(code_paths)
    spec={"artifacts":before,"cohort_hash":manifest["cohort_hash"],"code":code,
          "protocol":manifest["spec"]["protocol"],"top_k":top_k,"ks":ks}
    signature=digest(spec)
    provenance=dest/"evaluation_manifest.json"
    csv=dest/"evaluation_nextitem_test.csv"
    if provenance.exists():
        old=json.loads(provenance.read_text(encoding="utf-8"))
        if old["signature"]!=signature:
            raise ValueError("Kết quả hiện có khác model/cohort/code; dùng output mới")
        if csv.exists():
            return pd.read_csv(csv)
    adapters={"content":content,"covis":covis,"als":als,"gru":gru_full}
    if model in adapters:
        predictions,metadata=adapters[model](p,root,dest,cases,history,signature,top_k=top_k)
    else:
        predictions,metadata=ann(model,p,root,dest,cases,history,signature,top_k=top_k)
    after=fingerprint(paths)
    if before!=after:
        raise RuntimeError("Artifact thay đổi trong lúc evaluation; từ chối xuất metric")
    metadata["cohort_hash"]=manifest["cohort_hash"]
    metadata["prediction_top_k"]=top_k
    table,ranks=metric_rows(cases,predictions,model,metadata,ks=ks)
    audit=cases.copy()
    audit["predicted_item_ids"]=[predictions.get(u,[]) for u in cases.user_id]
    audit["target_rank_at20"]=np.where(ranks<=20,ranks,0)
    audit[f"target_rank_at{top_k}"]=ranks
    audit.to_parquet(dest/"test_nextitem_predictions.parquet",index=False)
    table.to_csv(csv,index=False,encoding="utf-8-sig")
    write_json(provenance,{"signature":signature,"spec":spec,"metadata":metadata,
                           "checkpoint_unchanged":True,"retrained":False,"test_used_for_tuning":False})
    return table
