"""Behavior checks for ranker evaluation and serving fallback."""

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.online_models import rank_candidates
from scripts.train_lightgbm_ranker import (
    FEATURES, encode_features, ranking_metrics, validate_candidate_audit,
)


class LightGBMRankerTests(unittest.TestCase):
    def test_metrics_include_unretrieved_requests(self):
        frame = pd.DataFrame({
            "case_id": ["a", "a", "b", "b"],
            "candidate_item_id": ["1", "2", "3", "4"],
            "label": [0, 1, 0, 1],
        })
        metrics = ranking_metrics(frame, np.array([0.1, 0.9, 0.9, 0.1]), all_cases=4)
        self.assertEqual(metrics["candidate_recall"], 0.5)
        self.assertEqual(metrics["Recall@10"], 0.5)
        self.assertEqual(metrics["conditional_Recall@10"], 1.0)
        self.assertAlmostEqual(metrics["NDCG@10"], (1 + 1 / np.log2(3)) / 4)

    def test_features_exclude_user_item_and_target_ids(self):
        self.assertFalse({"user_id", "candidate_item_id", "target_item_id", "case_id", "label"} & set(FEATURES))

    def test_unseen_category_maps_to_missing(self):
        frame = pd.DataFrame({name: [0.0] for name in FEATURES})
        for name in ("candidate_brand", "candidate_category0", "candidate_category1",
                     "candidate_category2", "candidate_condition", "candidate_shipper"):
            frame[name] = "known"
        _, vocabulary = encode_features(frame)
        frame["candidate_brand"] = "new"
        encoded, _ = encode_features(frame, vocabulary)
        self.assertTrue(pd.isna(encoded.loc[0, "candidate_brand"]))

    def test_rejected_model_keeps_hybrid_ranking(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.txt"
            model.with_name("feature_schema.json").write_text(
                json.dumps({"accepted_for_serving": False}), encoding="utf-8")
            with patch.dict("os.environ", {"MERREC_RANKER": "lightgbm",
                                             "MERREC_LIGHTGBM_PATH": str(model)}):
                scores, name, status = rank_candidates([{"candidate_item_id": "x"}], [0.7])
        self.assertEqual(scores, [0.7])
        self.assertEqual(name, "hybrid_feature_ranker_v2")
        self.assertEqual(status["lightgbm"], "rejected_by_offline_gate")

    def test_training_rejects_policy_mismatch(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "candidate_audit.json").write_text(json.dumps({
                split: {"candidate_recall": 0.5, "serving_policy": "include_history"}
                for split in ("train", "val", "test")
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exclude-history"):
                validate_candidate_audit(path)


if __name__ == "__main__":
    unittest.main()
