import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
import polars as pl

from scripts.expand_ranker_training import expanded_train_sql, include_history_candidates


class ExpansionTests(unittest.TestCase):
    def test_streamed_training_matches_sampler_and_scaler(self):
        import numpy as np
        from scripts.train_dcn_ranker import (HASH_BUCKETS,NUM_COLUMNS,prepare_streamed_split,
            select_training_candidates,numeric_features,fit_scaler,encode)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            values = {'case_id':['hit','hit','hit','miss'], 'candidate_item_id':['target','a','b','x'],
                      'label':[1,0,0,0], 'rrf_score':[.2,.3,.1,.4]}
            for column in HASH_BUCKETS:
                if column not in values:
                    values[column]=['category']*4
            for column in NUM_COLUMNS:
                if column not in values:
                    values[column]=[1.,2.,3.,4.]
            frame = pl.DataFrame(values)
            path = root/'train.parquet'
            frame.write_parquet(path)
            sampled = select_training_candidates(frame,negatives=1)
            mean,std = fit_scaler(numeric_features(sampled))
            cats,nums = encode(sampled,mean,std)
            result = prepare_streamed_split(path,root/'encoded',training=True,negatives=1)
            self.assertEqual((result['all_cases'],result['positive_cases'],result['rows']),(2,1,2))
            np.testing.assert_allclose(result['mean'],mean,rtol=1e-6)
            np.testing.assert_allclose(result['std'],std,rtol=1e-6)
            np.testing.assert_array_equal(result['cats'].numpy(),cats.numpy())
            np.testing.assert_allclose(result['nums'].numpy(),nums.numpy(),atol=1e-6)
            np.testing.assert_array_equal(result['labels'].numpy(),sampled['label'].to_numpy())
            del result,cats,nums

    def test_fusion_filters_cases_and_catalog_without_inserting_target(self):
        from scripts import build_ranker_datasets as builder
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pl.DataFrame({'case_id':['repeat','missing'], 'user_id':['u','v'],
                'target_item_id':['seen','catalog_only'], 'history_item_ids':[['seen'],[]]},
                schema_overrides={'history_item_ids':pl.List(pl.String)}).write_parquet(root/'cases_train.parquet')
            pl.DataFrame({'case_id':['repeat','missing','unrelated'], 'user_id':['u','v','z'],
                'target_item_id':['seen','catalog_only','seen'], 'candidate_item_id':['seen']*3,
                'score':[1.,1.,1.], 'rank':[1,1,1]}).write_parquet(root/'content_train.parquet')
            catalog = {'item_id':['seen','catalog_only'], 'price':[10.,20.]}
            for column in ('product_id','brand','category0','category1','category2','condition','shipper'):
                catalog[column]=['known','other']
            pl.DataFrame(catalog).write_parquet(root/'catalog.parquet')
            pl.DataFrame({'item_id':['seen'], 'interactions':[5]}).write_csv(root/'pop.csv')
            with patch.multiple(builder,CASES=root,EXPORTS=root,OUTPUT=root/'out',
                CATALOG=root/'catalog.parquet',POPULARITY=root/'pop.csv',SOURCE_TOPK={'content':2}):
                report = builder.build('train',2,256,scratch_dir=root/'scratch')
            result = pl.read_parquet(root/'out/dcn_train.parquet')
            self.assertEqual(report['cases'],2)
            self.assertEqual(report['candidate_recall'],0.5)
            self.assertEqual(set(result['candidate_item_id']),{'seen'})
            self.assertEqual(result.filter(pl.col('case_id')=='repeat')['label'].item(),1)
            self.assertEqual(set(result['candidate_brand']),{'known'})

    def test_repeat_candidates_do_not_depend_on_target_and_are_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rankings = []
            for target in ('seen', 'never_seen'):
                cases = root / f'{target}_cases.parquet'
                content = root / f'{target}_content.parquet'
                pl.DataFrame({'case_id':['c'], 'user_id':['u'], 'target_item_id':[target],
                    'history_item_ids':[['older','seen','older']]}).write_parquet(cases)
                pl.DataFrame({'case_id':['c'], 'user_id':['u'], 'candidate_item_id':['metadata'],
                    'target_item_id':[target], 'score':[3.0], 'rank':[1]}).write_parquet(content)
                include_history_candidates(cases,content,root/'scratch',3)
                first = pl.read_parquet(content).sort('rank')
                include_history_candidates(cases,content,root/'scratch',3)
                self.assertTrue(first.equals(pl.read_parquet(content).sort('rank')))
                rankings.append(first.select('candidate_item_id','score','rank').to_dicts())
            self.assertEqual(rankings[0],rankings[1])
            self.assertEqual([r['candidate_item_id'] for r in rankings[0]],['older','seen','metadata'])

    def test_preserve_original_cases_and_strict_past_for_added_users(self):
        import datetime
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            t = datetime.datetime(2026, 1, 1)
            later = datetime.datetime(2026, 1, 2)
            old = pl.DataFrame({'case_id':['kept'], 'split':['train'], 'user_id':['old'],
                'target_item_id':['original'], 'target_ts':[later], 'history_item_ids':[['past']]})
            old.write_parquet(root / 'old.parquet')
            pl.DataFrame({'user_id':['old','old','new','new','new','tied','tied'],
                'item_id':['past','original','past','target_a','target_b','x','y'],
                'ts':[t,later,t,later,later,later,later]}).write_parquet(root / 'train.parquet')
            with duckdb.connect() as db:
                result = db.execute(expanded_train_sql(root/'train.parquet',root/'old.parquet',1)).pl()
            self.assertEqual(result.height, 2)
            self.assertEqual(result.filter(pl.col('user_id')=='old').to_dicts(),old.to_dicts())
            added = result.filter(pl.col('user_id')=='new').row(0,named=True)
            self.assertEqual(added['history_item_ids'],['past'])
            self.assertEqual(added['target_item_id'],'target_a')


if __name__ == '__main__':
    unittest.main()
