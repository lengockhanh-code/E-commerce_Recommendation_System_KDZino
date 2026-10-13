"""Audit frozen predictions and report retrieval/ranking roles separately."""
import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

from training.evaluation.nextitem import MODELS, NAMES, fingerprint, write_json
from training.evaluation.pipeline import exclusive_hits, metrics, ranker_metrics

ROOT = Path(__file__).resolve().parents[1]


def verify_retrieval_sql(source, retrieval):
    """Cross-check hit counts and leave-one-source-out loss in SQL."""
    with duckdb.connect() as db:
        db.execute("SET memory_limit='1GB'")
        db.execute('SET threads=2')
        db.from_parquet(str(Path(source)/'test_future_item_targets.parquet')).create_view('labels')
        queries = []
        for model in MODELS:
            db.from_parquet(str(Path(source)/f'{model}_sources.parquet')).create_view(model)
            queries.append(f"SELECT DISTINCT '{model}' model,user_id,candidate_item_id FROM {model} WHERE rank<=100")
        db.execute('CREATE TEMP TABLE contributions AS '+ ' UNION ALL '.join(queries))
        rows = db.execute('''WITH multiplicity AS (
            SELECT user_id,candidate_item_id,count(DISTINCT model) n
            FROM contributions GROUP BY user_id,candidate_item_id)
            SELECT c.model,count(*) hits,
                count(*) FILTER (WHERE m.n=1) exclusive_hits,
                count(*) FILTER (WHERE NOT t.is_train_item) outside_train_hits
            FROM contributions c JOIN labels t
                ON c.user_id=t.user_id AND c.candidate_item_id=t.item_id
            JOIN multiplicity m ON c.user_id=m.user_id
                AND c.candidate_item_id=m.candidate_item_id
            GROUP BY c.model''').fetchall()
        actual = {model:(hits,exclusive,cold) for model,hits,exclusive,cold in rows}
        expected = {model:(row['future_hits@100'],row['exclusive_hits@100'],
                           row['outside_train_hits@100'])
                    for model,row in zip(MODELS,retrieval)}
        if actual != expected:
            raise ValueError('SQL disagrees with retrieval contributions')
        return actual


def run(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError('Use a new report directory')
    summary = json.loads((source/'summary.json').read_text(encoding='utf-8'))
    files = [source/'summary.json', source/'test_future_item_targets.parquet',
             source/'shared_candidates.parquet', source/'ranker_scores.parquet']
    files += [source/f'{m}_sources.parquet' for m in MODELS]
    files += [source/f'{m}_top100.parquet' for m in ('rrf','dcn','lightgbm')]
    upstream = summary['ranker_checkpoints'][:]
    for entry in summary['cache_provenance'].values():
        upstream += entry['artifacts'] + entry['cache']
    expected = {x['path']:x for x in upstream}
    current = {x['path']:x for x in fingerprint(expected)}
    if current != expected:
        raise ValueError('Artifact or retrieval cache changed since inference')
    before = fingerprint(files)
    targets = pd.read_parquet(source/'test_future_item_targets.parquet')
    if targets.duplicated(['user_id','item_id']).any():
        raise ValueError('Future target pairs must be unique')
    routes = {}
    for model in MODELS:
        frame = pd.read_parquet(source/f'{model}_sources.parquet',
                                 columns=['user_id','candidate_item_id','rank'])
        frame = frame.sort_values(['user_id','rank','candidate_item_id'])
        routes[model] = frame.groupby('user_id').candidate_item_id.agg(list).to_dict()
    for model in ('RRF','DCN','LightGBM'):
        frame = pd.read_parquet(source/f'{model.lower()}_top100.parquet')
        routes[model] = dict(zip(frame.user_id,frame.candidate_item_id.map(list)))
    with duckdb.connect() as db:
        db.execute("SET memory_limit='1GB'")
        db.execute('SET threads=2')
        pool = dict(db.execute('SELECT user_id,list(candidate_item_id) FROM read_parquet(?) GROUP BY user_id',
                               [str(source/'shared_candidates.parquet')]).fetchall())
        db.from_parquet(str(source/'ranker_scores.parquet')).create_view('scores')
        db.register('targets',targets)
        db.execute('''CREATE TEMP TABLE reached AS SELECT t.user_id,t.item_id
            FROM targets t SEMI JOIN scores s ON t.user_id=s.user_id AND t.item_id=s.candidate_item_id''')
        pool_hits = db.execute('SELECT count(*) FROM reached').fetchone()[0]
        eligible_users = db.execute('SELECT count(DISTINCT user_id) FROM reached').fetchone()[0]
        rankers = []
        for model,column in (('RRF','rrf_score'),('DCN','dcn_score'),('LightGBM','lightgbm_score')):
            row = {'model':model, **ranker_metrics(targets,pool,routes[model])}
            # Independent SQL verifies recall and ideal-DCG denominators.
            for k in (20,50,100):
                hit,recall,ndcg = db.execute('''WITH ranked AS (
                    SELECT user_id,candidate_item_id,row_number() OVER(PARTITION BY user_id
                    ORDER BY '''+column+''' DESC,candidate_item_id) rank FROM scores),
                    denominators AS (SELECT user_id,count(*) n FROM reached GROUP BY user_id),
                    got AS (SELECT t.user_id,count(*) hits,sum(1.0/log2(r.rank+1)) dcg
                        FROM reached t JOIN ranked r ON t.user_id=r.user_id AND t.item_id=r.candidate_item_id
                        WHERE r.rank<=? GROUP BY t.user_id),
                    ideals AS (SELECT d.user_id,sum(1.0/log2(v+1)) idcg FROM denominators d,
                        LATERAL range(1,least(?,d.n)+1) z(v) GROUP BY d.user_id)
                    SELECT sum(coalesce(g.hits,0)),avg(coalesce(g.hits,0)::DOUBLE/d.n),
                        avg(coalesce(g.dcg,0)/i.idcg) FROM denominators d
                    JOIN ideals i USING(user_id) LEFT JOIN got g USING(user_id)''',[k,k]).fetchone()
                if (hit != row[f'hits@{k}'] or abs(recall-row[f'Recall@{k}'])>1e-10
                        or abs(ndcg-row[f'NDCG@{k}'])>1e-10):
                    raise ValueError('SQL disagrees with ranker metrics')
            rankers.append(row)
    if pool_hits != summary['candidate_target_hits']:
        raise ValueError('Candidate coverage differs from source report')
    unique = exclusive_hits(targets,{m:routes[m] for m in MODELS})
    first = {x['model']:x for x in summary['single_next_item_same_anchor']}
    retrieval = []
    for model in MODELS:
        full = metrics(targets,routes[model])
        cold = metrics(targets[~targets.is_train_item],routes[model])
        retrieval.append({'model':NAMES[model],'future_hits@100':full['hits@100'],
            'candidate_micro_recall@100':full['micro_Recall@100'],
            'exclusive_hits@100':unique[model]['exclusive_hits'],
            'outside_train_hits@100':cold['hits@100'],
            'first_next_item_HR@20':first[model]['Recall@20'],
            'unique_recommended_items@100':len({i for items in routes[model].values() for i in items[:100]}),
            'inference':summary['cache_provenance'][model]['metadata']})
    verify_retrieval_sql(source, retrieval)
    if fingerprint(files)!=before or {x['path']:x for x in fingerprint(expected)}!=expected:
        raise ValueError('Inputs changed during role evaluation')
    output.mkdir(parents=True)
    report = {'protocol':'fixed_pre_TEST_role_specific_evaluation_v1',
        'source_report':str(source.resolve()),'users':summary['users'],
        'future_targets':len(targets),'pool_target_pairs':pool_hits,
        'ranker_eligible_users':eligible_users,'ranker_excluded_users':summary['users']-eligible_users,
        'retrieval':retrieval,'ranker':rankers,'end_to_end':summary['results'],
        'candidate_discrimination_proxy':summary['ranking_candidate_proxy'],
        'ranker_recall_and_ndcg_independent_SQL_verified':True,
        'retrieval_hit_contributions_independent_SQL_verified':True,
        'input_fingerprints':before,'artifact_fingerprints':list(expected.values()),
        'artifact_and_prediction_files_unchanged':True,
        'test_used_to_select_models_or_hyperparameters':False,
        'label_policy':'all distinct observed TEST interactions; unobserved is not explicit negative',
        'history_policy':'TRAIN+VAL strictly before first TEST event; repeats allowed',
        'serving_activated':False,'limitations':summary['limitations']}
    write_json(output/'summary.json',report)
    pd.DataFrame([{k:v for k,v in row.items() if k!='inference'} for row in retrieval]).to_csv(output/'retrieval_roles.csv',index=False)
    pd.DataFrame(rankers).to_csv(output/'ranker_metrics.csv',index=False)
    print(pd.DataFrame(rankers)[['model','users','pool_target_pairs','NDCG@20','NDCG@100','micro_Recall@20','micro_Recall@100']].to_string(index=False))
    print(pd.DataFrame([{k:v for k,v in row.items() if k!='inference'} for row in retrieval]).to_string(index=False))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'training/evaluation/results/pipeline_multifuture_numeric_20261010')
    parser.add_argument('--output',type=Path,default=ROOT/'training/evaluation/results/model_roles_canva_20261010')
    args=parser.parse_args()
    run(args.input,args.output)
