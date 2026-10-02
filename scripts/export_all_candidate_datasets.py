"""Master High-Performance Candidate Export Pipeline for DCN Ranker (MerRec).

Reads unified prediction cases from data/processed/recommender/candidate_cases/
and exports Top-K candidate datasets for:
1. content   (Top 150)
2. covis     (Top 250)
3. als       (Top 200)
4. gru       (Top 200)
5. twotower  (Top 300)

Schema for each file:
case_id, user_id, candidate_item_id, target_item_id, score, rank

No retraining. Uses existing checkpoints/indexes/mappings.
Prints validation cell metrics after each export.
"""

import sys
import time
import json
import math
import gc
import argparse
import os
from pathlib import Path

import duckdb
import faiss
import numpy as np
import polars as pl
import torch
import torch.nn as nn
import torch.nn.functional as F
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "data" / "processed" / "recommender" / "candidate_cases"
EXPORTS_DIR = ROOT / "candidate_exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_SPECS = {
    "content": {"topk": 150},
    "covis": {"topk": 250},
    "als": {"topk": 200},
    "gru": {"topk": 200},
    "twotower": {"topk": 3000}
}
FORCE = False
CACHE_DIR = ROOT / "data" / "processed" / "recommender" / "candidate_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fallback_items(limit):
    """Training-only popularity plus serving-time trending, deduplicated."""
    frames = []
    for name, score in (("05_top_popularity_train.csv", "popularity_score"),
                        ("06_top_trending_serving.csv", "trending_score")):
        path = ROOT / "data" / "processed" / "recommender" / "tables" / name
        if path.is_file():
            frames.append(pl.read_csv(path).select(
                pl.col("item_id").cast(pl.String), pl.col(score).cast(pl.Float64).alias("raw_score")))
    if not frames:
        raise FileNotFoundError("popularity/trending fallback tables are missing")
    fallback = (pl.concat(frames).group_by("item_id").agg(pl.max("raw_score"))
                .sort(["raw_score", "item_id"], descending=[True, False]).head(limit))
    maximum = fallback["raw_score"].max() or 1.0
    return fallback.with_columns((pl.col("raw_score") / maximum).alias("score")).select("item_id", "score")


def atomic_write(frame, path):
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.write_parquet(temporary, compression="zstd")
    temporary.replace(path)

def print_validation_cell(split_name, cases_cnt, rows_cnt, recall, out_path):
    avg_cand = rows_cnt / max(1, cases_cnt)
    print("\n" + "="*80)
    print(f"VALIDATION SUMMARY FOR: {out_path.name}")
    print("="*80)
    print(f"  split                 : {split_name.upper()}")
    print(f"  cases                 : {cases_cnt:,}")
    print(f"  rows                  : {rows_cnt:,}")
    print(f"  avg candidates/case   : {avg_cand:.2f}")
    print(f"  Candidate Recall      : {recall * 100:.4f}%")
    print(f"  output path           : {out_path}")
    print("="*80 + "\n", flush=True)

# -------------------------------------------------------------------------
# 1. Content-Based Candidate Exporter (Batch Vectorized)
# -------------------------------------------------------------------------
def export_content(split_name):
    topk = MODEL_SPECS["content"]["topk"]
    out_path = EXPORTS_DIR / f"content_{split_name}.parquet"
    cases_df = pl.read_parquet(CASES_DIR / f"cases_{split_name}.parquet")
    if out_path.exists() and not FORCE:
        print(f"Skipping existing: {out_path.name}")
        return
    # Mirror serving policy: use recent history as profile seeds, but never return
    # an item already present in history. Product identity and brand+leaf category
    # are stable catalog metadata and require no target/future information.
    con = duckdb.connect()
    con.execute("SET threads=1")
    con.execute("SET memory_limit='2500MB'")
    con.execute("SET preserve_insertion_order=false")
    scratch = ROOT / "scratch/duckdb_content"
    scratch.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory='{str(scratch).replace("'", "''")}'")
    con.register("cases_tbl", cases_df.to_arrow())
    con.register("fallback_tbl", fallback_items(topk).to_arrow())
    catalog_path = ROOT / "data/processed/recommender/serving/item_catalog_full.parquet"
    con.from_parquet(str(catalog_path)).create_view("catalog")
    con.execute("""CREATE TEMP TABLE seed_meta AS
      WITH seeds AS (
        SELECT c.case_id, c.user_id, c.target_item_id, c.history_item_ids,
               u.item AS seed_item, len(c.history_item_ids)-u.pos AS age
        FROM cases_tbl c,
             UNNEST(c.history_item_ids) WITH ORDINALITY AS u(item,pos)
        WHERE u.pos > greatest(len(c.history_item_ids)-20,0)
      ) SELECT s.case_id,s.user_id,s.target_item_id,s.age,
               m.product_id,m.brand,m.category2
        FROM seeds s JOIN catalog m ON m.item_id=s.seed_item
    """)
    con.execute(f"""CREATE TEMP TABLE product_candidates AS
      SELECT c.product_id,c.item_id
      FROM catalog c JOIN (SELECT DISTINCT product_id FROM seed_meta
                           WHERE product_id IS NOT NULL AND product_id<>'__UNK__') k
        USING(product_id)
      QUALIFY row_number() OVER(PARTITION BY c.product_id
                                ORDER BY c.item_id)<={topk}
    """)
    con.execute(f"""CREATE TEMP TABLE category_brand_candidates AS
      SELECT c.category2,c.brand,c.item_id
      FROM catalog c JOIN (SELECT DISTINCT category2,brand FROM seed_meta
                           WHERE category2 IS NOT NULL AND category2<>'__UNK__'
                             AND brand IS NOT NULL AND brand<>'__UNK__') k
        USING(category2,brand)
      QUALIFY row_number() OVER(PARTITION BY c.category2,c.brand
                                ORDER BY c.item_id)<={topk}
    """)
    con.execute(f"""CREATE TEMP TABLE category_candidates AS
      SELECT c.category2,c.item_id
      FROM catalog c JOIN (SELECT DISTINCT category2 FROM seed_meta
                           WHERE category2 IS NOT NULL AND category2<>'__UNK__') k
        USING(category2)
      QUALIFY row_number() OVER(PARTITION BY c.category2 ORDER BY c.item_id)<={topk}
    """)
    df_out = con.execute(f"""
      WITH product_matches AS (
        SELECT s.case_id,s.user_id,c.item_id candidate_item_id,s.target_item_id,
               max(3.0 + 1.0/(1+s.age)) score
        FROM seed_meta s JOIN product_candidates c ON c.product_id=s.product_id
        GROUP BY s.case_id,s.user_id,c.item_id,s.target_item_id
      ), category_brand_matches AS (
        SELECT s.case_id,s.user_id,c.item_id candidate_item_id,s.target_item_id,
               max(1.0 + 0.25/(1+s.age)) score
        FROM seed_meta s JOIN category_brand_candidates c
          ON c.category2=s.category2 AND c.brand=s.brand
        GROUP BY s.case_id,s.user_id,c.item_id,s.target_item_id
      ), category_matches AS (
        SELECT s.case_id,s.user_id,c.item_id candidate_item_id,s.target_item_id,
               max(0.5 + 0.1/(1+s.age)) score
        FROM seed_meta s JOIN category_candidates c ON c.category2=s.category2
        GROUP BY s.case_id,s.user_id,c.item_id,s.target_item_id
      ), fallback AS (
        SELECT c.case_id,c.user_id,f.item_id candidate_item_id,c.target_item_id,
               f.score*0.01 score
        FROM cases_tbl c CROSS JOIN fallback_tbl f
        WHERE NOT list_contains(c.history_item_ids,f.item_id)
      ), merged AS (
        SELECT x.case_id,x.user_id,x.candidate_item_id,x.target_item_id,max(x.score) score
        FROM (SELECT * FROM product_matches UNION ALL SELECT * FROM category_brand_matches
              UNION ALL SELECT * FROM category_matches UNION ALL SELECT * FROM fallback) x
        JOIN cases_tbl h USING(case_id)
        WHERE NOT list_contains(h.history_item_ids,x.candidate_item_id)
        GROUP BY x.case_id,x.user_id,x.candidate_item_id,x.target_item_id
      ), ranked AS (
        SELECT *,row_number() OVER(PARTITION BY case_id ORDER BY score DESC,candidate_item_id) rank
        FROM merged
      )
      SELECT * FROM ranked WHERE rank<={topk}
    """).pl()
    con.close()
    atomic_write(df_out, out_path)
    recalled = df_out.filter(pl.col("candidate_item_id") == pl.col("target_item_id"))["case_id"].n_unique()
    
    recall = recalled / max(1, cases_df.height)
    print_validation_cell(split_name, cases_df.height, df_out.height, recall, out_path)

# -------------------------------------------------------------------------
# 2. Co-Visitation Candidate Exporter (Batch Vectorized)
# -------------------------------------------------------------------------
def export_covis(split_name):
    topk = MODEL_SPECS["covis"]["topk"]
    out_path = EXPORTS_DIR / f"covis_{split_name}.parquet"
    cases_df = pl.read_parquet(CASES_DIR / f"cases_{split_name}.parquet")
    if out_path.exists() and not FORCE:
        print(f"Skipping existing: {out_path.name}")
        return
    neighbor_path = CACHE_DIR / "covis_neighbors_train.parquet"
    if not neighbor_path.is_file():
        build_covis_neighbors(neighbor_path, max_neighbors=max(500, topk))
    con = duckdb.connect()
    con.execute("SET threads=2")
    con.register("cases_tbl", cases_df.to_arrow())
    con.register("fallback_tbl", fallback_items(topk).to_arrow())
    con.from_parquet(str(neighbor_path)).create_view("neighbors")
    df_out = con.execute(f"""
        WITH seeds AS (
          SELECT c.case_id, c.user_id, c.target_item_id, u.item AS seed_item,
                 len(c.history_item_ids) - u.pos AS age
          FROM cases_tbl c,
               UNNEST(c.history_item_ids) WITH ORDINALITY AS u(item, pos)
          WHERE u.pos > greatest(len(c.history_item_ids) - 20, 0)
        ), personalized AS (
          SELECT s.case_id, s.user_id, n.candidate_item_id, s.target_item_id,
                 sum(n.score / (1.0 + s.age)) AS score
          FROM seeds s JOIN neighbors n ON n.seed_item_id = s.seed_item
          GROUP BY s.case_id, s.user_id, n.candidate_item_id, s.target_item_id
        ), fallback AS (
          SELECT c.case_id, c.user_id, f.item_id AS candidate_item_id, c.target_item_id,
                 f.score * 0.01 AS score
          FROM cases_tbl c CROSS JOIN fallback_tbl f
        ), merged AS (
          SELECT case_id, user_id, candidate_item_id, target_item_id, max(score) AS score
          FROM (SELECT * FROM personalized UNION ALL SELECT * FROM fallback)
          GROUP BY case_id, user_id, candidate_item_id, target_item_id
        ), ranked AS (
          SELECT *, row_number() OVER (
            PARTITION BY case_id ORDER BY score DESC, candidate_item_id) AS rank
          FROM merged
        )
        SELECT * FROM ranked WHERE rank <= {topk}
        ORDER BY case_id, rank
    """).pl()
    atomic_write(df_out, out_path)
    recalled = df_out.filter(pl.col("candidate_item_id") == pl.col("target_item_id"))["case_id"].n_unique()
    
    recall = recalled / max(1, cases_df.height)
    print_validation_cell(split_name, cases_df.height, df_out.height, recall, out_path)


def build_covis_neighbors(out_path, max_neighbors=500):
    """Build directed 1-3 step item transitions from train histories only."""
    train_cases = CASES_DIR / "cases_train.parquet"
    temporary = out_path.with_suffix(out_path.suffix + ".tmp")
    con = duckdb.connect()
    con.execute("SET threads=2")
    con.execute("SET preserve_insertion_order=false")
    con.from_parquet(str(train_cases)).create_view("train_cases")
    escaped = str(temporary).replace("'", "''")
    con.execute(f"""COPY (
      WITH events AS (
        SELECT case_id, u.item AS item_id, u.pos
        FROM train_cases c,
             UNNEST(c.history_item_ids) WITH ORDINALITY AS u(item, pos)
      ), transitions AS (
        SELECT a.item_id AS seed_item_id, b.item_id AS candidate_item_id,
               1.0 / (b.pos - a.pos) AS weight
        FROM events a JOIN events b ON a.case_id = b.case_id
          AND b.pos > a.pos AND b.pos <= a.pos + 3
        WHERE a.item_id <> b.item_id
      ), scored AS (
        SELECT seed_item_id, candidate_item_id, sum(weight) AS score,
               row_number() OVER (PARTITION BY seed_item_id
                                  ORDER BY sum(weight) DESC, candidate_item_id) AS neighbor_rank
        FROM transitions GROUP BY seed_item_id, candidate_item_id
      )
      SELECT seed_item_id, candidate_item_id, score, neighbor_rank
      FROM scored WHERE neighbor_rank <= {int(max_neighbors)}
    ) TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    con.close()
    temporary.replace(out_path)

# -------------------------------------------------------------------------
# 3. ALS Candidate Exporter (PyTorch Chunked Dot-Product Matrix Mult)
# -------------------------------------------------------------------------
def export_als(split_name):
    topk = MODEL_SPECS["als"]["topk"]
    out_path = EXPORTS_DIR / f"als_{split_name}.parquet"
    cases_df = pl.read_parquet(CASES_DIR / f"cases_{split_name}.parquet")
    if out_path.exists() and not FORCE:
        print(f"Skipping existing: {out_path.name}")
        return
    
    ckpt_path = ROOT / "artifacts" / "merrec_models" / "ALS" / "model" / "final_model.npz"
    map_u_path = ROOT / "artifacts" / "merrec_models" / "ALS" / "mappings" / "train_val_user_map.parquet"
    map_i_path = ROOT / "artifacts" / "merrec_models" / "ALS" / "mappings" / "train_val_item_map.parquet"
    
    data = np.load(ckpt_path)
    user_factors = torch.from_numpy(data["user_factors"]).float()  # (N_users, 32)
    item_factors = torch.from_numpy(data["item_factors"]).float()  # (N_items, 32)
    
    user_map_df = pl.read_parquet(map_u_path)
    item_map_df = pl.read_parquet(map_i_path)
    
    u_str_to_idx = dict(zip(user_map_df["user_id"], user_map_df["user_idx"]))
    i_idx_to_str = dict(zip(item_map_df["item_idx"], item_map_df["item_id"]))
    
    u_idxs = [u_str_to_idx.get(str(u), 0) for u in cases_df["user_id"]]
    u_vecs = torch.zeros((len(u_idxs), user_factors.shape[1]), dtype=torch.float32)
    for b, idx in enumerate(u_idxs):
        if idx < len(user_factors):
            u_vecs[b] = user_factors[idx]

    N_items = item_factors.shape[0]
    chunk_size = 100000
    user_batch_size = 2000
    num_users = u_vecs.shape[0]
    
    all_scores = []
    all_indices = []
    
    for u_st in range(0, num_users, user_batch_size):
        u_ed = min(u_st + user_batch_size, num_users)
        u_sub = u_vecs[u_st:u_ed]  # (B, 32)
        
        top_scores = None
        top_indices = None
        
        for i_st in range(0, N_items, chunk_size):
            i_ed = min(i_st + chunk_size, N_items)
            item_chunk = item_factors[i_st:i_ed]  # (C, 32)
            
            scores_chunk = torch.matmul(u_sub, item_chunk.T) # (B, C)
            c_scores, c_indices = torch.topk(scores_chunk, k=min(topk, item_chunk.shape[0]), dim=1)
            c_indices = c_indices + i_st
            
            if top_scores is None:
                top_scores, top_indices = c_scores, c_indices
            else:
                comb_scores = torch.cat([top_scores, c_scores], dim=1)
                comb_indices = torch.cat([top_indices, c_indices], dim=1)
                top_scores, sorted_k = torch.topk(comb_scores, k=topk, dim=1)
                top_indices = torch.gather(comb_indices, 1, sorted_k)
                
        all_scores.append(top_scores.numpy())
        all_indices.append(top_indices.numpy())
        
    scores = np.vstack(all_scores)
    retrieved_idxs = np.vstack(all_indices)
    
    rows = []
    recalled_cases = 0
    
    for b, row in enumerate(cases_df.iter_rows(named=True)):
        case_id = row["case_id"]
        user_id = str(row["user_id"])
        target_id = str(row["target_item_id"])
        
        cand_ids = [i_idx_to_str.get(idx, str(idx)) for idx in retrieved_idxs[b]]
        if target_id in cand_ids:
            recalled_cases += 1
            
        for rank, (cand_id, score) in enumerate(zip(cand_ids, scores[b]), start=1):
            rows.append({
                "case_id": case_id,
                "user_id": user_id,
                "candidate_item_id": str(cand_id),
                "target_item_id": target_id,
                "score": float(score),
                "rank": int(rank)
            })

    df_out = pl.DataFrame(rows)
    df_out.write_parquet(out_path, compression="zstd")
    
    recall = recalled_cases / max(1, cases_df.height)
    print_validation_cell(split_name, cases_df.height, df_out.height, recall, out_path)

# -------------------------------------------------------------------------
# 4. GRU4Rec Candidate Exporter (PyTorch Model + Prebuilt FAISS Index)
# -------------------------------------------------------------------------
class GRU4RecSequenceEncoder(nn.Module):
    def __init__(self, event_vocab_size=7, item_embed_dim=32, event_embed_dim=16, hidden_dim=128, gru_layers=2, dropout=0.2):
        super().__init__()
        self.event_emb = nn.Embedding(event_vocab_size, event_embed_dim, padding_idx=0)
        self.input_proj = nn.Linear(item_embed_dim + event_embed_dim, hidden_dim)
        self.input_ln = nn.LayerNorm(hidden_dim)
        self.gru = nn.GRU(
            hidden_dim, hidden_dim, num_layers=gru_layers, batch_first=True, dropout=dropout if gru_layers > 1 else 0.0
        )
        self.out_ln = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.item_out = nn.Linear(item_embed_dim, hidden_dim, bias=False)

    def forward(self, item_emb_w, item_ids_cpu, event_ids_cpu):
        item_x = F.embedding(item_ids_cpu, item_emb_w, padding_idx=0)
        event_x = self.event_emb(event_ids_cpu)
        x = torch.cat([item_x, event_x], dim=-1)
        x = self.input_proj(x)
        x = self.input_ln(x)
        x = self.dropout(x)
        out, _ = self.gru(x)
        out = self.out_ln(out)
        lengths = item_ids_cpu.ne(0).sum(dim=1).clamp_min(1)
        return out[torch.arange(out.size(0)), lengths - 1]

def export_gru(split_name):
    topk = MODEL_SPECS["gru"]["topk"]
    out_path = EXPORTS_DIR / f"gru_{split_name}.parquet"
    cases_df = pl.read_parquet(CASES_DIR / f"cases_{split_name}.parquet")
    if out_path.exists() and not FORCE:
        print(f"Skipping existing: {out_path.name}")
        return
    
    ckpt_path = ROOT / "artifacts" / "merrec_models" / "GRU4Rec" / "model" / "gru4rec_best_model.pt"
    faiss_path = ROOT / "artifacts" / "merrec_models" / "GRU4Rec" / "index" / "items_ivfpq.faiss"
    map_path = ROOT / "artifacts" / "merrec_models" / "GRU4Rec" / "mappings" / "train_item_map.parquet"
    
    index = faiss.read_index(str(faiss_path))
    faiss.ParameterSpace().set_index_parameter(index, "nprobe", 64)
    
    map_df = pl.read_parquet(map_path)
    item_ids_arr = map_df["item_id"].to_list()
    
    unique_hist_items = set()
    for h in cases_df["history_item_ids"]:
        unique_hist_items.update(str(x) for x in h)
        
    hist_map_df = map_df.filter(pl.col("item_id").is_in(list(unique_hist_items)))
    item_id_to_idx = dict(zip(hist_map_df["item_id"], hist_map_df["item_idx"].cast(pl.Int64)))
    
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model_state = ckpt.get("model", ckpt)
    item_emb_w = model_state["item_emb.weight"]
    
    batch_size = 512
    all_rows = []
    recalled_cases = 0
    
    for st in range(0, cases_df.height, batch_size):
        sub_df = cases_df.slice(st, batch_size)
        max_len = 100
        b_size = sub_df.height
        items_cpu = torch.full((b_size, max_len), 0, dtype=torch.long)
        
        for b, row in enumerate(sub_df.iter_rows(named=True)):
            h_items = [item_id_to_idx.get(str(x), 1) for x in row["history_item_ids"]][-max_len:]
            n = len(h_items)
            if n > 0:
                items_cpu[b, :n] = torch.tensor(h_items, dtype=torch.long)
                
        with torch.no_grad():
            item_x = F.embedding(items_cpu, item_emb_w, padding_idx=0)
            lengths = items_cpu.ne(0).sum(dim=1).clamp_min(1)
            last_items = item_x[torch.arange(item_x.size(0)), lengths - 1]
            q = F.normalize(last_items, dim=-1).numpy().astype("float32")
            
        scores, retrieved_ids = index.search(q, topk)
        
        for b, row in enumerate(sub_df.iter_rows(named=True)):
            case_id = row["case_id"]
            user_id = str(row["user_id"])
            target_id = str(row["target_item_id"])
            
            cand_ids = [item_ids_arr[idx - 2] if 2 <= idx < len(item_ids_arr) + 2 else str(idx) for idx in retrieved_ids[b]]
            if target_id in cand_ids:
                recalled_cases += 1
                
            for rank, (cand_id, score) in enumerate(zip(cand_ids, scores[b]), start=1):
                all_rows.append({
                    "case_id": case_id,
                    "user_id": user_id,
                    "candidate_item_id": str(cand_id),
                    "target_item_id": target_id,
                    "score": float(score),
                    "rank": int(rank)
                })

    df_out = pl.DataFrame(all_rows)
    df_out.write_parquet(out_path, compression="zstd")
    
    recall = recalled_cases / max(1, cases_df.height)
    print_validation_cell(split_name, cases_df.height, df_out.height, recall, out_path)

# -------------------------------------------------------------------------
# 5. Two-Tower Candidate Exporter (Prebuilt FAISS + User Vector Lookup)
# -------------------------------------------------------------------------
def export_twotower(split_name):
    topk = MODEL_SPECS["twotower"]["topk"]
    out_path = EXPORTS_DIR / f"twotower_{split_name}.parquet"
    cases_df = pl.read_parquet(CASES_DIR / f"cases_{split_name}.parquet")
    if out_path.exists() and not FORCE:
        print(f"Skipping existing: {out_path.name}")
        return
    
    ckpt_path = ROOT / "artifacts" / "merrec_models" / "TwoTower" / "model" / "two_tower_best_model.pt"
    faiss_path = ROOT / "artifacts" / "merrec_models" / "TwoTower" / "index" / "items_ivfpq.faiss"
    map_i_path = ROOT / "artifacts" / "merrec_models" / "TwoTower" / "mappings" / "train_item_map.parquet"
    map_u_path = ROOT / "artifacts" / "merrec_models" / "TwoTower" / "mappings" / "train_user_map.parquet"
    
    index = faiss.read_index(str(faiss_path))
    faiss.ParameterSpace().set_index_parameter(index, "nprobe", 128)
    unique_users = [str(u) for u in cases_df["user_id"].unique()]
    target_ids = [str(i) for i in cases_df["target_item_id"].unique()]
    with duckdb.connect() as mapping_db:
        user_rows = mapping_db.execute("""SELECT user_id,user_idx FROM read_parquet(?)
            WHERE user_id IN (SELECT unnest(?))""", [str(map_u_path), unique_users]).fetchall()
        target_rows = mapping_db.execute("""SELECT item_id,item_idx FROM read_parquet(?)
            WHERE item_id IN (SELECT unnest(?))""", [str(map_i_path), target_ids]).fetchall()
    u_str_to_idx = {str(key): int(value) for key, value in user_rows}
    target_to_idx = {str(key): int(value) for key, value in target_rows}
    item_ids_arr = pq.read_table(map_i_path, columns=["item_id"], memory_map=True)["item_id"].combine_chunks()
    
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    user_emb_w = ckpt["model"]["user.weight"].float()
    
    temporary = out_path.with_suffix(out_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    writer = None
    recalled_cases = 0
    rows_written = 0
    batch_size = 256
    for start in range(0, cases_df.height, batch_size):
        batch = cases_df.slice(start, batch_size)
        records = batch.to_dicts()
        valid = [(row, u_str_to_idx.get(str(row["user_id"]))) for row in records]
        valid = [(row, idx) for row, idx in valid if idx is not None and idx < len(user_emb_w)]
        if not valid:
            continue
        user_indices = torch.tensor([idx for _, idx in valid], dtype=torch.long)
        q_vecs = F.normalize(user_emb_w[user_indices], dim=-1).numpy().astype("float32")
        scores, retrieved_ids = index.search(q_vecs, topk)
        for offset, (row, _) in enumerate(valid):
            target_idx = target_to_idx.get(str(row["target_item_id"]))
            if target_idx is not None and target_idx in retrieved_ids[offset]:
                recalled_cases += 1
        flat = retrieved_ids.reshape(-1)
        valid_slots = flat >= 0
        flat_indices = pa.array(flat[valid_slots], type=pa.int64())
        candidate_ids = pc.take(item_ids_arr, flat_indices)
        count = len(valid)
        repeated_cases = np.repeat([row["case_id"] for row, _ in valid], topk)[valid_slots]
        repeated_users = np.repeat([str(row["user_id"]) for row, _ in valid], topk)[valid_slots]
        repeated_targets = np.repeat([str(row["target_item_id"]) for row, _ in valid], topk)[valid_slots]
        table = pa.table({
            "case_id": pa.array(repeated_cases),
            "user_id": pa.array(repeated_users),
            "candidate_item_id": candidate_ids,
            "target_item_id": pa.array(repeated_targets),
            "score": pa.array(scores.reshape(-1)[valid_slots].astype(np.float32)),
            "rank": pa.array(np.tile(np.arange(1, topk + 1, dtype=np.int32), count)[valid_slots]),
        })
        if writer is None:
            writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
        writer.write_table(table)
        rows_written += len(table)
    if writer is None:
        raise ValueError(f"No mapped Two-Tower users for {split_name}")
    writer.close()
    temporary.replace(out_path)
    
    recall = recalled_cases / max(1, cases_df.height)
    print_validation_cell(split_name, cases_df.height, rows_written, recall, out_path)

# -------------------------------------------------------------------------
# Master Execution Pipeline
# -------------------------------------------------------------------------
def run_all_exports(sources=None, splits=None):
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== MASTER DCN RANKER CANDIDATE EXPORTER ===")
    t_start = time.time()

    splits = splits or ["train", "val", "test"]
    exporters = {
        "content": export_content,
        "covis": export_covis,
        "als": export_als,
        "gru": export_gru,
        "twotower": export_twotower
    }

    selected = sources or list(exporters)
    unknown = set(selected) - set(exporters)
    if unknown:
        raise ValueError(f"Unknown candidate sources: {sorted(unknown)}")
    for model_name in selected:
        func = exporters[model_name]
        print(f"\n=======================================================")
        print(f"EXPORTING CANDIDATES FOR MODEL: {model_name.upper()}")
        print(f"=======================================================")
        for split in splits:
            func(split)

    print(f"\nExported {len(selected) * len(splits)} candidate dataset(s) "
          f"in {time.time() - t_start:.2f}s.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", choices=list(MODEL_SPECS), default=None)
    parser.add_argument("--splits", nargs="+", choices=["train", "val", "test"], default=None)
    parser.add_argument("--force", action="store_true", help="replace existing exports atomically")
    args = parser.parse_args()
    FORCE = args.force or os.environ.get("MERREC_FORCE_CANDIDATES") == "1"
    run_all_exports(args.sources, args.splits)
