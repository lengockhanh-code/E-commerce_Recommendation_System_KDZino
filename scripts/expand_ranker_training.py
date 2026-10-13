"""Expand TRAIN requests and retrieval in an isolated, resumable experiment.

Keep old VAL/TEST requests and legacy ALS/GRU exports. New TRAIN requests use
content metadata, TRAIN-history co-visitation and the installed Two-Tower.
ALS/GRU features are missing for new requests, explicitly recorded in the audit.
This does not replace models, notebook paths, or the original ranking dataset.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import duckdb
import polars as pl


def input_dependencies():
    """Freeze upstream artifacts so resumed fusion never uses stale features."""
    paths = [ROOT/'data/processed/recommender/serving/item_catalog_full.parquet',
             ROOT/'data/processed/recommender/tables/05_top_popularity_train.csv']
    paths += list((ROOT/'data/processed/recommender/model_data/interactions/split=train').glob('*.parquet'))
    paths += [ROOT/'candidate_exports'/f'{source}_{split}.parquet'
              for source in ('als','gru') for split in ('train','val','test')]
    paths += [p for p in (ROOT/'artifacts/merrec_models/TwoTower').rglob('*')
              if p.is_file() and p.suffix in ('.pt','.faiss','.parquet','.npy','.json')]
    return [[str(p.relative_to(ROOT)),p.stat().st_size,p.stat().st_mtime_ns]
            for p in sorted(paths)]


def expanded_train_sql(train_path, old_path, additional, seed=42):
    """Add users with a strictly earlier history; targets never drive retrieval."""
    from scripts.build_ranker_datasets import sql_path
    return f"""WITH old AS (SELECT * FROM read_parquet('{sql_path(old_path)}')),
      eligible AS (
        SELECT user_id FROM read_parquet('{sql_path(train_path)}')
        WHERE user_id NOT IN (SELECT user_id FROM old)
        GROUP BY user_id HAVING min(ts)<max(ts)
        ORDER BY hash(user_id,{int(seed)}),user_id LIMIT {int(additional)}
      ), targets AS (
        SELECT i.user_id,i.item_id target_item_id,i.ts target_ts
        FROM read_parquet('{sql_path(train_path)}') i SEMI JOIN eligible USING(user_id)
        QUALIFY row_number() OVER(PARTITION BY user_id ORDER BY ts DESC,item_id)=1
      ), added AS (
        SELECT 'train_'||t.user_id||'_'||epoch_ms(t.target_ts)::VARCHAR||'_'||t.target_item_id case_id,
          'train' split,t.user_id,t.target_item_id,t.target_ts,
          list(i.item_id ORDER BY i.ts,i.item_id) history_item_ids
        FROM targets t JOIN read_parquet('{sql_path(train_path)}') i
          ON i.user_id=t.user_id AND i.ts<t.target_ts
        GROUP BY t.user_id,t.target_item_id,t.target_ts
      ) SELECT * FROM old UNION ALL SELECT * FROM added"""


def connection(scratch):
    from scripts.build_ranker_datasets import sql_path
    scratch.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect()
    db.execute("SET threads=2")
    db.execute("SET memory_limit='2500MB'")
    db.execute("SET preserve_insertion_order=false")
    db.execute(f"SET temp_directory='{sql_path(scratch)}'")
    return db


def include_history_candidates(cases_path, content_path, scratch, topk=300):
    """Retain repeatable historical items, ranked solely by historical recency."""
    from scripts.build_ranker_datasets import sql_path
    temporary = content_path.with_suffix('.parquet.tmp')
    with connection(scratch) as db:
        query = f"""WITH history AS (
          SELECT c.case_id,c.user_id,u.item candidate_item_id,c.target_item_id,
            (5.0+1.0/(1+len(c.history_item_ids)-u.pos))::FLOAT score
          FROM read_parquet('{sql_path(cases_path)}') c,
            UNNEST(c.history_item_ids) WITH ORDINALITY u(item,pos)
        ), merged AS (
          SELECT case_id,user_id,candidate_item_id,target_item_id,max(score)::FLOAT score
          FROM (SELECT case_id,user_id,candidate_item_id,target_item_id,score FROM history
                UNION ALL SELECT case_id,user_id,candidate_item_id,target_item_id,score
                FROM read_parquet('{sql_path(content_path)}'))
          GROUP BY case_id,user_id,candidate_item_id,target_item_id
        ), ranked AS (
          SELECT *,row_number() OVER(PARTITION BY case_id ORDER BY score DESC,candidate_item_id) rank
          FROM merged
        ) SELECT * FROM ranked WHERE rank<={int(topk)}"""
        db.execute(f"COPY ({query}) TO '{sql_path(temporary)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    temporary.replace(content_path)


def run(args):
    from scripts import build_ranker_datasets as builder
    from scripts import export_all_candidate_datasets as exporter
    from scripts.train_dcn_ranker import fingerprint
    import faiss
    import torch

    if args.train_cases < 10000 or args.batch_cases < 1:
        raise ValueError('train-cases must be >=10000; batch-cases must be positive')
    destination = args.output.resolve()
    if not destination.is_relative_to(ROOT / 'training/dcn/runs'):
        raise ValueError('Output must stay under training/dcn/runs to preserve original data')
    destination.mkdir(parents=True, exist_ok=True)
    cases = destination / 'cases'
    exports = destination / 'exports'
    cache = destination / 'cache'
    for directory in (cases, exports, cache):
        directory.mkdir(exist_ok=True)
    old_cases = ROOT / 'data/processed/recommender/candidate_cases'
    config = {'train_cases': args.train_cases, 'seed': args.seed,
              'input_dependencies': input_dependencies(),
              'source_topk': {'content': 300, 'covis': 1000, 'als': 200, 'gru': 200, 'twotower': 3000},
              'train_candidates': 1000, 'eval_candidates': 2000,
              'twotower_nprobe': 24,
              'legacy_cases': {s: fingerprint(old_cases / f'cases_{s}.parquet') for s in ('train','val','test')},
              'legacy_sources': 'ALS/GRU reused only for original case IDs; missing for new TRAIN cases',
              'content_model': 'catalog metadata heuristic',
              'content_repeat_candidates': 'historical items by recency; target independent',
              'twotower_model': 'installed checkpoint; history used only when checkpoint supports it',
              'evaluation_protocol': 'legacy last target; causal history including earlier split interactions; allow_repeat'}
    config_path = destination / 'expansion_config.json'
    if config_path.exists() and json.loads(config_path.read_text(encoding='utf-8')) != config:
        raise ValueError('Existing experiment configuration differs; choose a new output directory')
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    for split in ('val', 'test'):
        if not (cases / f'cases_{split}.parquet').exists():
            shutil.copy2(old_cases / f'cases_{split}.parquet', cases / f'cases_{split}.parquet')
    train_cases = cases / 'cases_train.parquet'
    if not train_cases.exists():
        original_count = pl.read_parquet(old_cases / 'cases_train.parquet').height
        train_path = ROOT / 'data/processed/recommender/model_data/interactions/split=train/*.parquet'
        query = expanded_train_sql(train_path, old_cases / 'cases_train.parquet', args.train_cases-original_count, args.seed)
        temporary = train_cases.with_suffix('.parquet.tmp')
        print('Building expanded TRAIN cases...', flush=True)
        with connection(destination / 'scratch/cases') as db:
            db.execute(f"COPY ({query}) TO '{builder.sql_path(temporary)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        temporary.replace(train_cases)
    frame = pl.read_parquet(train_cases)
    if frame.height != args.train_cases or frame['case_id'].n_unique() != frame.height:
        raise ValueError(f'Expected {args.train_cases} unique TRAIN cases, got {frame.height}')
    print(f'TRAIN cases={frame.height}; old VAL/TEST requests preserved', flush=True)
    exporter.CASES_DIR, exporter.EXPORTS_DIR, exporter.CACHE_DIR = cases, exports, cache
    for source, topk in config['source_topk'].items():
        exporter.MODEL_SPECS[source]['topk'] = topk
    # Use the installed index's native search setting (24), rather than the
    # legacy exporter's expensive hard-coded 128 probes.
    exporter.MODEL_SPECS['twotower']['nprobe'] = 24
    torch.set_num_threads(4)
    faiss.omp_set_num_threads(4)
    neighbor_path = cache / 'covis_neighbors_train.parquet'
    if not neighbor_path.exists():
        exporter.build_covis_neighbors(neighbor_path, max_neighbors=1000)
    for split in ('train', 'val', 'test'):
        for source in ('als', 'gru'):
            path = exports / f'{source}_{split}.parquet'
            if not path.exists():
                shutil.copy2(ROOT / 'candidate_exports' / path.name, path)
        split_frame = pl.read_parquet(cases / f'cases_{split}.parquet')
        for source in ('content', 'covis'):
            out = exports / f'{source}_{split}.parquet'
            if out.exists():
                continue
            parts = []
            for start in range(0, split_frame.height, args.batch_cases):
                part_root = destination / 'batches' / split / str(start)
                part_root.mkdir(parents=True, exist_ok=True)
                case_file = part_root / f'cases_{split}.parquet'
                batch = split_frame.slice(start, args.batch_cases)
                if not case_file.exists():
                    batch.write_parquet(case_file)
                elif not pl.read_parquet(case_file).equals(batch):
                    raise ValueError('Batch configuration changed; resume with the original batch-cases value')
                exporter.CASES_DIR = exporter.EXPORTS_DIR = part_root
                getattr(exporter, f'export_{source}')(split)
                parts.append(str(part_root / out.name))
                print(f'{source}/{split}: {min(start+args.batch_cases,split_frame.height)}/{split_frame.height}', flush=True)
            exporter.CASES_DIR, exporter.EXPORTS_DIR = cases, exports
            temporary = out.with_suffix('.parquet.tmp')
            with connection(destination / 'scratch/merge') as db:
                db.execute(f"COPY (SELECT * FROM read_parquet(?)) TO '{builder.sql_path(temporary)}' (FORMAT PARQUET, COMPRESSION ZSTD)", [parts])
            temporary.replace(out)
        exporter.CASES_DIR, exporter.EXPORTS_DIR = cases, exports
        exporter.export_twotower(split)
    for split in ('train', 'val', 'test'):
        include_history_candidates(cases / f'cases_{split}.parquet',
                                   exports / f'content_{split}.parquet',
                                   destination / 'scratch/history', topk=300)
    builder.CASES, builder.EXPORTS, builder.OUTPUT = cases, exports, destination / 'dataset'
    builder.SOURCE_TOPK = config['source_topk']
    report = {'expansion': config}
    for split in ('train', 'val', 'test'):
        split_frame = pl.read_parquet(cases / f'cases_{split}.parquet')
        parts = []
        for start in range(0, split_frame.height, args.batch_cases):
            part_root = destination / 'fusion' / split / str(start)
            part_root.mkdir(parents=True, exist_ok=True)
            case_file = part_root / f'cases_{split}.parquet'
            batch = split_frame.slice(start,args.batch_cases)
            if case_file.exists() and not pl.read_parquet(case_file).equals(batch):
                raise ValueError('Fusion batch changed; use original batch-cases')
            batch.write_parquet(case_file)
            builder.CASES, builder.OUTPUT = part_root, part_root / 'dataset'
            path = builder.OUTPUT / f'dcn_{split}.parquet'
            if not path.exists():
                builder.build(split,1000,3500,min_recall=0,
                              scratch_dir=destination/'scratch/fusion')
            parts.append(str(path))
            print(f'Fusion/{split}: {min(start+args.batch_cases,split_frame.height)}/{split_frame.height}',flush=True)
        builder.CASES, builder.OUTPUT = cases, destination / 'dataset'
        builder.OUTPUT.mkdir(exist_ok=True)
        final = builder.OUTPUT / f'dcn_{split}.parquet'
        temporary = final.with_suffix('.parquet.tmp')
        with connection(destination/'scratch/merge_dataset') as db:
            db.execute(f"COPY (SELECT * FROM read_parquet(?)) TO '{builder.sql_path(temporary)}' (FORMAT PARQUET, COMPRESSION ZSTD)",[parts])
            report[split] = builder.metrics(db,temporary,split,1000)
        temporary.replace(final)
        print(json.dumps({split: report[split]}), flush=True)
    (builder.OUTPUT / 'candidate_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Dataset ready: {builder.OUTPUT}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-cases', type=int, default=30000)
    parser.add_argument('--batch-cases', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=ROOT / 'training/dcn/runs/retrieval_expanded_20261010')
    run(parser.parse_args())
