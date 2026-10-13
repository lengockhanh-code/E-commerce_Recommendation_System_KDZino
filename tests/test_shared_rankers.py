import unittest

import numpy as np
import pandas as pd

from scripts.evaluate_shared_rankers import KS, combine_metrics, validate_query_frame
from scripts.train_lightgbm_ranker import ranking_metrics


class SharedRankerEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({"case_id": [1, 1, 2, 2],
                                   "candidate_item_id": [10, 11, 20, 21],
                                   "label": [1, 0, 1, 0]})

    def test_batching_preserves_misses_and_global_denominator(self):
        scores = np.array([1., 0., 0., 1.])
        parts = [ranking_metrics(self.frame.iloc[i:i+2], scores[i:i+2], 1, ks=KS)
                 for i in (0, 2)]
        merged = combine_metrics(parts, all_cases=4, positive_cases=2)
        expected = ranking_metrics(self.frame, scores, 4, ks=KS)
        for key, value in expected.items():
            self.assertAlmostEqual(merged[key], value)
        self.assertEqual(merged["candidate_recall"], .5)
        self.assertEqual(merged["Recall@20"], .5)
        self.assertEqual(merged["conditional_Recall@20"], 1.)

    def test_missing_scored_cases_fail_instead_of_inflating_metrics(self):
        part = ranking_metrics(self.frame.iloc[:2], [1., 0.], 1, ks=KS)
        with self.assertRaisesRegex(ValueError, "Scored queries"):
            combine_metrics([part], 4, 2)

    def test_duplicate_and_multiple_targets_are_rejected(self):
        validate_query_frame(self.frame)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_query_frame(pd.concat([self.frame, self.frame.iloc[:1]]))
        bad = self.frame.copy()
        bad.loc[1, "label"] = 1
        with self.assertRaisesRegex(ValueError, "one target"):
            validate_query_frame(bad)

    def test_missing_label_is_not_silently_a_negative(self):
        bad = self.frame.copy()
        bad.loc[0, "label"] = np.nan
        with self.assertRaisesRegex(ValueError, "non-null"):
            validate_query_frame(bad)


if __name__ == "__main__":
    unittest.main()
