import unittest
import ast
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import polars as pl
import torch

from scripts.train_dcn_ranker import (DCN, HASH_BUCKETS, MODEL_PROFILES, NUM_COLUMNS, encode, predict, fit_scaler, numeric_features,
                                     select_training_candidates, positive_weight, matched_val_probe, training_probe)
from scripts.train_lightgbm_ranker import ranking_metrics


class DCNRankerTests(unittest.TestCase):
    def test_compact_generalizes_without_user_or_item_id_embeddings(self):
        model = DCN(MODEL_PROFILES['compact']).eval()
        cats = torch.ones((2, len(HASH_BUCKETS)), dtype=torch.long)
        cats[1, :3] = torch.tensor([42, 71, 88])
        nums = torch.zeros((2, len(NUM_COLUMNS)))
        with torch.inference_mode():
            scores = model(cats, nums)
        self.assertEqual(scores[0].item(), scores[1].item())
        compact_count = sum(p.numel() for p in model.parameters())
        legacy_count = sum(p.numel() for p in DCN().parameters())
        self.assertLess(compact_count, legacy_count / 10)

    def test_checkpoint_profiles_match_online_predictions_and_legacy_loads(self):
        from scripts.online_models import dcn_predict
        frame = pl.DataFrame({**{k: ['a', 'b'] for k in HASH_BUCKETS},
                              **{k: [0., 1.] for k in NUM_COLUMNS}})
        mean, std = fit_scaler(numeric_features(frame))
        cats, nums = encode(frame, mean, std)
        for profile in ('legacy', 'compact', 'numeric'):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as folder:
                model = DCN(MODEL_PROFILES[profile])
                checkpoint = {'model': model.state_dict(), 'cat_columns': list(HASH_BUCKETS),
                              'hash_buckets': HASH_BUCKETS, 'num_columns': NUM_COLUMNS,
                              'num_mean': mean, 'num_std': std}
                if profile != 'legacy':
                    checkpoint['model_config'] = model.config
                path = Path(folder) / 'model.pt'
                torch.save(checkpoint, path)
                restored = DCN(checkpoint.get('model_config'))
                restored.load_state_dict(torch.load(path, weights_only=False)['model'])
                expected = predict(model, cats, nums, 2)
                np.testing.assert_array_equal(predict(restored, cats, nums, 2), expected)
                with patch.dict('os.environ', {'MERREC_DCN_PATH': str(path)}):
                    np.testing.assert_allclose(dcn_predict(frame.to_dicts()), expected, rtol=1e-6, atol=1e-6)

    def test_numeric_profile_is_id_independent_and_clips_extreme_features(self):
        model = DCN(MODEL_PROFILES['numeric']).eval()
        cats = torch.zeros((2, len(HASH_BUCKETS)), dtype=torch.long)
        cats[1] = 9999999  # Numeric profile never looks up categorical IDs.
        nums = torch.full((2, len(NUM_COLUMNS)), 1e20)
        with torch.inference_mode():
            scores = model(cats, nums)
            clipped = model(cats, nums.clamp(-5, 5))
        self.assertTrue(torch.isfinite(scores).all())
        torch.testing.assert_close(scores, clipped, rtol=0, atol=0)
        self.assertEqual(scores[0].item(), scores[1].item())
        self.assertLess(sum(p.numel() for p in model.parameters()), 2000)

    def test_overfit_probe_keeps_tensor_alignment_and_official_val_unchanged(self):
        frame = pl.DataFrame({**{k: ['a']*4 for k in HASH_BUCKETS},
                              **{k: [0.]*4 for k in NUM_COLUMNS}}).with_columns(
            pl.Series('case_id', ['hit','hit','hit','miss']),
            pl.Series('candidate_item_id', ['target','strong','weak','other']),
            pl.Series('label', [1,0,0,0]),
            pl.Series('rrf_score', [.01,.8,.2,.9]))
        cats = torch.arange(4).reshape(-1,1)
        nums = cats.float()
        probe, pc, pn = matched_val_probe(frame, cats, nums, negatives=1)
        self.assertEqual(len(frame), 4)
        self.assertEqual(set(probe['candidate_item_id']), {'target','strong'})
        for item,row in zip(probe['candidate_item_id'],pc[:,0].tolist()):
            self.assertEqual(frame['candidate_item_id'][row], item)
        torch.testing.assert_close(pc.float(), pn)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'train.parquet'
            frame.write_parquet(path)
            tp,tc,tn = training_probe(path,np.zeros(len(NUM_COLUMNS),np.float32),
                                     np.ones(len(NUM_COLUMNS),np.float32),negatives=1)
            self.assertEqual(set(tp['candidate_item_id']), {'target','strong'})
            self.assertEqual(tc.shape[0], len(tp))
            self.assertTrue(torch.isfinite(tn).all())

    def test_notebook_profiles_match_script_checkpoint(self):
        notebook = json.loads(Path('training/models/06_dcn.ipynb').read_text(encoding='utf-8'))
        scope = {'torch': torch, 'nn': torch.nn}
        exec(compile(''.join(notebook['cells'][36]['source']), '<notebook-model>', 'exec'), scope)
        assignments = ast.parse(''.join(notebook['cells'][37]['source']))
        config_node = next(x.value for x in assignments.body if isinstance(x, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'MODEL_CONFIG' for t in x.targets))
        self.assertEqual(ast.literal_eval(config_node), MODEL_PROFILES['numeric'])
        cats = torch.ones((3, len(HASH_BUCKETS)), dtype=torch.long)
        nums = torch.randn((3, len(NUM_COLUMNS))) * 10
        for profile in ('compact', 'numeric'):
            config = MODEL_PROFILES[profile]
            model = DCN(config).eval()
            notebook_model = scope['DCN'](
                HASH_BUCKETS, len(NUM_COLUMNS), embed_dim=config['embedding_dim'],
                cross_layers=config['cross_layers'], deep_layers=config['hidden_dims'],
                dropout=config['dropout'], categorical_features=config['categorical_features'],
                numeric_clip=config.get('numeric_clip')).eval()
            notebook_model.load_state_dict(model.state_dict())
            with torch.inference_mode():
                torch.testing.assert_close(notebook_model(cats, nums), model(cats, nums), rtol=0, atol=0)

    def test_train_uses_positive_queries_and_keeps_hard_negatives(self):
        frame = pl.DataFrame({
            "case_id": ["hit", "hit", "hit", "hit", "miss", "miss"],
            "candidate_item_id": ["target", "a", "b", "c", "d", "e"],
            "label": [1, 0, 0, 0, 0, 0],
            "rrf_score": [.01, .5, .5, .1, .9, .8],
        })
        train = select_training_candidates(frame, negatives=2)
        self.assertEqual(set(train["case_id"]), {"hit"})
        self.assertEqual(set(train["candidate_item_id"]), {"target", "a", "b"})
        self.assertEqual(train["label"].sum(), 1)
        self.assertEqual(positive_weight(train["label"].to_numpy()), 2)
        with self.assertRaises(ValueError):
            select_training_candidates(frame.filter(pl.col("case_id") == "miss"))

    def test_positive_weight_uses_observed_ratio_without_cap(self):
        self.assertEqual(positive_weight(np.array([1] + [0] * 199)), 199)
        for labels in ([0, 0], [1, 1], [1, np.nan], [1, 2]):
            with self.assertRaises(ValueError):
                positive_weight(labels)

    def test_notebook_metrics_include_unretrieved_cases(self):
        notebook = json.loads((Path(__file__).resolve().parents[1] /
                               "training/models/06_dcn.ipynb").read_text(encoding="utf-8"))
        tree = ast.parse("".join(notebook["cells"][41]["source"]))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "ranking_metrics")
        namespace = {"np": np, "pd": pd}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "notebook", "exec"), namespace)
        result = namespace["ranking_metrics"](
            np.array([1., 1., 4., 3.]), np.array([0, 1, 0, 0]),
            np.array([10, 10, 20, 20]), ks=(1, 2, 20))
        self.assertEqual(result["all_cases"], 2)
        self.assertEqual(result["Recall@1"], 0)
        self.assertEqual(result["Recall@2"], .5)
        self.assertEqual(result["conditional_Recall@2"], 1)
        self.assertEqual(result["MRR@20"], .25)
        with self.assertRaises(ValueError):
            namespace["ranking_metrics"](np.array([np.nan]), np.array([1]), np.array([1]))

    def test_nonfinite_scores_do_not_corrupt_scaler(self):
        frame = pl.DataFrame({k: [0., 1., 2., 3.] for k in NUM_COLUMNS})
        frame = frame.with_columns(pl.Series("twotower_score", [None, -np.inf, np.inf, np.nan]))
        x = numeric_features(frame)
        mean, std = fit_scaler(x)
        self.assertTrue(np.isfinite((x - mean) / std).all())
        column = NUM_COLUMNS.index("twotower_score")
        self.assertEqual(mean[column], 0)
        self.assertEqual(std[column], 1)

    def test_price_and_rank_transform(self):
        frame = pl.DataFrame({k: [0., 0.] for k in NUM_COLUMNS}).with_columns(
            pl.Series("candidate_price", [-10., 99.]),
            pl.Series("content_rank", [1., 9999.]))
        x = numeric_features(frame)
        np.testing.assert_allclose(x[:, NUM_COLUMNS.index("candidate_price")], [0, np.log(100)], rtol=1e-6)
        np.testing.assert_allclose(x[:, NUM_COLUMNS.index("content_rank")], [.5, .0001])

    def test_missing_targets_count_as_zero_and_ties_are_deterministic(self):
        frame = pd.DataFrame({"case_id": ["a", "a"],
                              "candidate_item_id": ["z", "a"], "label": [1, 0]})
        result = ranking_metrics(frame, [1., 1.], all_cases=4, ks=(1, 2, 20))
        self.assertEqual(result["Recall@1"], 0)
        self.assertEqual(result["Recall@2"], .25)
        self.assertEqual(result["conditional_Recall@2"], 1)
        self.assertEqual(result["MRR@20"], .125)


if __name__ == "__main__":
    unittest.main()
