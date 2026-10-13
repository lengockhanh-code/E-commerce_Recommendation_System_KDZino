import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
import pandas as pd
import polars as pl

from scripts import build_ranker_datasets as builder
from training.evaluation.pipeline import candidate_discrimination, exclusive_hits, metrics, dcn_feature_frame, ranker_metrics


class PipelineTests(unittest.TestCase):
    def test_ranker_conditioning_keeps_order_and_separates_retrieval_misses(self):
        targets = pd.DataFrame({'user_id':['a','a','b','c','c'],
                                'item_id':['seen','absent','missing','new','absent']})
        pool = {'a':['wrong','seen'],'b':['wrong'],'c':['new','other']}
        predictions = {'a':['wrong','seen'],'b':['wrong'],'c':['new','other']}
        result = ranker_metrics(targets, pool, predictions, ks=(1,2))
        self.assertEqual(result['pool_target_pairs'], 2)
        self.assertEqual(result['users'], 2)
        self.assertEqual(result['all_users'], 3)
        self.assertEqual(result['users_without_retrieved_target'], 1)
        self.assertEqual(result['Recall@1'], .5)
        self.assertEqual(result['Recall@2'], 1.)
        self.assertEqual(result['NDCG@1'], .5)
        self.assertEqual(result['micro_Recall@1'], .5)
        self.assertAlmostEqual(metrics(targets,predictions,ks=(1,))['Recall@1'], 1/6)
        with self.assertRaises(ValueError):
            ranker_metrics(targets,pool,{'a':['absent']},ks=(1,))
        with self.assertRaises(ValueError):
            ranker_metrics(targets,pool,{'b':['wrong','wrong']},ks=(2,))

    def test_empty_reachable_pool_has_no_ranker_score(self):
        targets = pd.DataFrame({'user_id':['a'],'item_id':['target']})
        result = ranker_metrics(targets,{'a':['other']},{'a':['other']})
        self.assertEqual(result['pool_target_pairs'], 0)
        self.assertEqual(result['users_without_retrieved_target'], 1)
        self.assertIsNone(result['NDCG@20'])
        self.assertEqual(metrics(targets,{'a':['other']})['NDCG@20'], 0.)

    def test_gauc_excludes_single_class_users_and_weights_candidate_counts(self):
        frame = pd.DataFrame({"user_id": ["a", "a", "b", "b", "c"],
                              "candidate_item_id": ["x", "y", "x", "z", "x"],
                              "score": [.9, .1, .1, .9, .6]})
        targets = pd.DataFrame({"user_id": ["a", "b", "c"], "item_id": ["x", "x", "x"]})
        result = candidate_discrimination(frame, targets, "score")
        self.assertAlmostEqual(result["future_item_candidate_GAUC"], .5)
        self.assertEqual(result["GAUC_eligible_users"], 2)
        self.assertEqual(result["GAUC_excluded_single_class_users"], 1)

    def test_macro_micro_recall_include_missed_users(self):
        targets = pd.DataFrame({"user_id": ["a", "a", "b"], "item_id": ["seen", "future", "cold"]})
        row = metrics(targets, {"a": ["seen"]})
        self.assertEqual(row["hits@100"], 1)
        self.assertEqual(row["Recall@100"], .25)
        self.assertEqual(row["micro_Recall@100"], 1 / 3)
        self.assertEqual(row["users_with_hit@100"], 1)
        self.assertEqual(row["avg_hits@20"], .5)
        self.assertEqual(row["Precision@20"], 1 / 40)
        with self.assertRaises(ValueError):
            metrics(targets, {"a": ["seen", "seen"]})

    def test_dcn_normalization_uses_checkpoint_without_changing_shared_candidates(self):
        frame = pl.DataFrame({'twotower_rank':[1,100,9999],
                              'twotower_score_norm':[1.,.1,0.]})
        result = dcn_feature_frame(frame, {'source_topk':{'twotower':3000}})
        self.assertAlmostEqual(result['twotower_score_norm'][1], 1-99/2999, places=6)
        self.assertEqual(result['twotower_score_norm'][2], 0.)
        self.assertEqual(frame['twotower_score_norm'][1], .1)
        self.assertTrue(dcn_feature_frame(frame, {}).equals(frame))

    def test_exclusive_contribution_counts_user_item_pairs(self):
        targets = pd.DataFrame({"user_id": ["a", "a", "b"], "item_id": ["x", "y", "x"]})
        result = exclusive_hits(targets, {"one": {"a": ["x", "y"]}, "two": {"a": ["x"], "b": ["x"]}})
        self.assertEqual(result["one"]["exclusive_hits"], 1)
        self.assertEqual(result["two"]["exclusive_hits"], 1)

    def test_repeat_retained_and_val_target_does_not_select_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pl.DataFrame({"case_id": ["c"], "history_item_ids": [["seen"]]}).write_parquet(root / "cases_val.parquet")
            frame = pl.DataFrame({"case_id": ["c", "c"], "user_id": ["u", "u"],
                "candidate_item_id": ["seen", "new"], "target_item_id": ["seen", "seen"], "rank": [1, 2]})
            frame.write_parquet(root / "content_val.parquet")
            with patch.object(builder, "EXPORTS", root), patch.object(builder, "CASES", root), patch.object(builder, "SOURCE_TOPK", {"content": 2}), duckdb.connect() as db:
                def selected(exclude=False):
                    return db.execute(builder.build_keys_query("val", 2, exclude)).df().candidate_item_id.tolist()
                self.assertEqual(selected(), ["seen", "new"])
                self.assertEqual(selected(True), ["new"])
                frame.with_columns(pl.lit("other").alias("target_item_id")).write_parquet(root / "content_val.parquet")
                self.assertEqual(selected(), ["seen", "new"])


if __name__ == "__main__":
    unittest.main()
