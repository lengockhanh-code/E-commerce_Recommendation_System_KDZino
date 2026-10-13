"""User-facing protocol: all products a user will interact with in TEST."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from training.evaluation.future_items import build_future_cases,future_metric_rows,validate_future


class FutureItemsTests(unittest.TestCase):
    def fixture(self):
        users=pd.DataFrame({"user_id":["u1","u2"]})
        targets=pd.DataFrame({"user_id":["u1","u1","u2"],"item_id":["seen","future","cold"],
            "is_positive":[True,True,False],"is_strong_positive":[False,True,False],
            "is_purchase":[False,True,False],"is_train_item":[True,True,False]})
        return users,targets

    def test_multiple_future_products_macro_recall_ndcg_mrr(self):
        u,t=self.fixture()
        table=future_metric_rows(u,t,{"u1":["seen","irrelevant","future"]},"covis")
        row=table.query("cohort_scope=='ALL_CASES' and target_group=='ALL'").iloc[0]
        self.assertEqual(row.users,2)
        self.assertEqual(row.targets,3)
        self.assertAlmostEqual(row["Recall@20"],.5)
        self.assertAlmostEqual(row["NDCG@20"],(1+.5)/(1+1/np.log2(3))/2)
        self.assertEqual(row["MRR@20"],.5)
        warm=table.query("cohort_scope=='COMMON_WARM' and target_group=='ALL'").iloc[0]
        self.assertEqual(warm.users,1)
        self.assertEqual(warm.targets,2)
        self.assertEqual(warm["Recall@20"],1)
        purchase=table.query("cohort_scope=='ALL_CASES' and target_group=='PURCHASE'").iloc[0]
        self.assertEqual(purchase.users,1)
        self.assertEqual(purchase.targets,1)
        self.assertEqual(purchase["Recall@20"],1)
        self.assertEqual(purchase["NDCG@20"],.5)
        self.assertAlmostEqual(purchase["MRR@20"],1/3)

    def test_recall_averages_users_not_targets(self):
        u,t=self.fixture()
        table=future_metric_rows(u,t,{"u1":["seen"]},"als")
        row=table.iloc[0]
        self.assertEqual(row["Recall@20"],.25)  # mean(1/2, 0/1), not 1/3

    def test_no_seen_filter_duplicates_and_empty_group(self):
        u,t=self.fixture()
        with self.assertRaises(ValueError):
            future_metric_rows(u,t,{"u1":["seen","seen"]},"als")
        t.is_purchase=False
        empty=future_metric_rows(u,t,{},"gru").query("target_group=='PURCHASE'")
        self.assertTrue(empty["MRR@20"].isna().all())

    def test_builder_keeps_all_test_products_deduplicates_events_and_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"data/processed/recommender/model_data"
            def e(u,item,day,event="view",purchase=0):
                return {"user_id":u,"item_id":item,"ts":pd.Timestamp(day),"event_group":event,
                        "event_id":event,"session_id":"s","event_weight":1.,
                        "is_strong_positive":purchase,"is_purchase":purchase}
            data={"train":[e("u1","seen","2023-05-01"),e("u2","known","2023-05-01")],
                  "val":[e("u1","v","2023-05-27"),e("u2","v","2023-05-27")],
                  "test":[e("u1","seen","2023-05-29"),e("u1","future","2023-05-30"),
                          e("u1","future","2023-05-30 01:00","buy_comp",1),
                          e("u2","cold","2023-05-29"),e("u2","later","2023-05-30")]}
            for split,rows in data.items():
                folder=base/"interactions"/f"split={split}"
                folder.mkdir(parents=True)
                pd.DataFrame(rows).to_parquet(folder/"data_0.parquet",index=False)
            pd.DataFrame({"user_id":["u1","u2"],"user_idx":[0,1]}).to_parquet(base/"train_user_map.parquet")
            pd.DataFrame({"item_id":["seen","known"],"item_idx":[0,1]}).to_parquet(base/"train_item_map.parquet")
            u,t,h,m=build_future_cases(root,root/"future_results",users=2)
            self.assertEqual(len(t),4)  # later products are ground truth too
            self.assertEqual(m["avg_targets_per_user"],2)
            self.assertEqual(set(t.item_id),{"seen","future","cold","later"})
            future=t.query("item_id=='future'").iloc[0]
            self.assertEqual(future.interaction_count,2)
            self.assertTrue(future.is_purchase)
            self.assertTrue(future.is_positive)
            self.assertEqual(set(h.source_split),{"train","val"})
            validate_future(u,t,h)
            self.assertEqual(m["groups"]["PURCHASE"]["targets"],1)
            h.loc[h.index[0],"ts"]=u.history_cutoff_ts.min()
            with self.assertRaises(ValueError):
                validate_future(u,t,h)


if __name__=="__main__":
    unittest.main()
