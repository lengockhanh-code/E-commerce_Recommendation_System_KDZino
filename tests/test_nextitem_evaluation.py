"""Behavioral checks for the shared TEST protocol and fixed-weight inference."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from training.evaluation.nextitem import build_cases, metric_rows, validate_cases
from training.evaluation.retrievers import fold_in, gru_queries, top_local


class NextItemTests(unittest.TestCase):
    def cases(self):
        return pd.DataFrame({"user_id":["u1","u2","u3"],"target_item_id":["repeat","cold","third"],
            "target_ts":pd.to_datetime(["2023-05-29"]*3),"is_positive":[True,False,True],
            "is_strong_positive":[True,False,False],"is_purchase":[False]*3,
            "is_train_item":[True,False,True]})

    def test_single_target_metrics_and_cold_miss(self):
        c=self.cases()
        table,ranks=metric_rows(c,{"u1":["repeat"],"u3":["a","b","third"]},"als")
        allrow=table.query("cohort_scope=='ALL_CASES' and target_group=='ALL'").iloc[0]
        self.assertEqual(list(ranks),[1,0,3])
        self.assertEqual(allrow.targets,3)
        self.assertAlmostEqual(allrow["Recall@20"],2/3)
        self.assertAlmostEqual(allrow["NDCG@20"],.5)
        self.assertAlmostEqual(allrow["MRR@20"],(1+1/3)/3)
        warm=table.query("cohort_scope=='COMMON_WARM' and target_group=='ALL'").iloc[0]
        self.assertEqual(warm.targets,2)
        self.assertEqual(warm["Recall@20"],1)
        empty=table.query("target_group=='PURCHASE'")
        self.assertTrue(empty["Recall@20"].isna().all())
        self.assertEqual(set(empty.status),{"EMPTY_GROUP"})

    def test_cutoffs_and_duplicate_predictions(self):
        c=self.cases().iloc[:1]
        top=[str(n) for n in range(10)]+["repeat"]
        row=metric_rows(c,{"u1":top},"als")[0].iloc[0]
        self.assertEqual(row["Recall@10"],0)
        self.assertEqual(row["Recall@20"],1)
        self.assertAlmostEqual(row["MRR@20"],1/11)
        with self.assertRaises(ValueError):
            metric_rows(c,{"u1":["repeat","repeat"]},"als")

    def test_strict_history_and_no_test_history(self):
        c=self.cases().iloc[:1]
        h=pd.DataFrame({"user_id":["u1"],"ts":pd.to_datetime(["2023-05-29"]),"source_split":["val"]})
        with self.assertRaises(ValueError):
            validate_cases(c,h)
        h.ts=pd.to_datetime(["2023-05-28"])
        validate_cases(c,h)
        h.source_split="test"
        with self.assertRaises(ValueError):
            validate_cases(c,h)

    def test_recall_20_50_100_boundaries_and_mrr_cutoff(self):
        for rank in (20,21,50,51,100,101):
            top=[f"other-{i}" for i in range(rank-1)]+["repeat"]
            table,ranks=metric_rows(self.cases().iloc[:1],{"u1":top},"als",ks=(20,50,100))
            row=table.iloc[0]
            for k in (20,50,100):
                self.assertEqual(row[f"Recall@{k}"],float(rank<=k))
            self.assertAlmostEqual(row["MRR@20"],1/rank if rank<=20 else 0)
            self.assertEqual(ranks[0],rank if rank<=100 else 0)
        empty=metric_rows(self.cases(),{},"als",ks=(20,50,100))[0]
        self.assertTrue(empty.query("target_group=='PURCHASE'")["Recall@100"].isna().all())

    def test_top100_merge_keeps_candidates_beyond_20(self):
        from training.evaluation.retrievers import merge_top
        ids=np.arange(200)
        scores=ids.astype(float)
        best_ids=[np.empty(0,dtype=np.int64)]
        best_scores=[np.empty(0)]
        for start in (0,100):
            chosen,values=top_local(scores[start:start+100],ids[start:start+100],k=100)
            merge_top(best_ids,best_scores,0,chosen,values,k=100)
        self.assertEqual(best_ids[0].tolist(),list(range(199,99,-1)))

    def test_first_test_target_repeat_cold_and_val_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"data/processed/recommender/model_data"
            def event(user,item,day,event="view",strong=0):
                return {"user_id":user,"item_id":item,"ts":pd.Timestamp(day),"event_group":event,
                        "event_id":event,"session_id":"s","event_weight":1.,
                        "is_strong_positive":strong,"is_purchase":0}
            data={"train":[event("u1","repeat","2023-05-01"),event("u2","old","2023-05-01")],
                  "val":[event("u1","v","2023-05-27"),event("u2","v","2023-05-27")],
                  "test":[event("u1","future","2023-05-30","cart",1),
                          event("u1","repeat","2023-05-29","cart",1),
                          event("u2","cold","2023-05-29"),event("u2","later","2023-05-30")]}
            for s,rows in data.items():
                folder=base/"interactions"/f"split={s}"
                folder.mkdir(parents=True)
                pd.DataFrame(rows).to_parquet(folder/"data_0.parquet",index=False)
            pd.DataFrame({"user_id":["u1","u2"],"user_idx":[0,1]}).to_parquet(base/"train_user_map.parquet")
            pd.DataFrame({"item_id":["repeat","old"],"item_idx":[0,1]}).to_parquet(base/"train_item_map.parquet")
            out=root/"results"
            c,h,m=build_cases(root,out,users=2)
            self.assertEqual(dict(zip(c.user_id,c.target_item_id)),{"u1":"repeat","u2":"cold"})
            self.assertEqual(len(c),2)
            self.assertEqual(set(h.source_split),{"train","val"})
            self.assertNotIn("future",set(h.item_id))
            self.assertEqual(m["warm_targets"],1)
            same=build_cases(root,out,users=2)[0]
            pd.testing.assert_frame_equal(c,same)
            with self.assertRaises(ValueError):
                build_cases(root,out,users=2,seed=1)
            # Seen target is legal and contributes a hit.
            row=metric_rows(c,{"u1":["repeat"]},"als")[0].iloc[0]
            self.assertEqual(row["Recall@20"],.5)

    def test_topk_includes_zero_scores_and_stable_ties(self):
        ids=np.array([1,2,3,4])
        chosen,scores=top_local(np.array([-1.,0.,2.,0.]),ids,k=3)
        self.assertEqual(chosen.tolist(),[3,2,4])
        self.assertEqual(scores.tolist(),[2.,0.,0.])

    def test_als_foldin_matches_implicit_inference(self):
        import scipy.sparse as sp
        from implicit.cpu.als import AlternatingLeastSquares
        y=np.array([[.2,.4],[.7,.1],[.3,.8]],dtype=np.float32)
        strengths=np.array([1.2,.5],dtype=np.float32)
        model=AlternatingLeastSquares(factors=2,regularization=.15,alpha=40,num_threads=1)
        model.item_factors=y
        matrix=sp.csr_matrix((strengths,([0,0],[0,2])),shape=(1,3))
        expected=model.recalculate_user(0,matrix)
        actual=fold_in(y[[0,2]],40*strengths,y.T@y,.15)
        np.testing.assert_allclose(actual,expected,rtol=1e-5,atol=1e-5)

    def test_gru_encoder_and_full_catalog_score_identity(self):
        import torch
        import torch.nn.functional as f
        torch.manual_seed(10)
        hidden=4
        gru=torch.nn.GRU(hidden,hidden,num_layers=2,batch_first=True)
        state={"gru."+k:v for k,v in gru.state_dict().items()}
        state.update({"item_emb.weight":torch.randn(6,2),"event_emb.weight":torch.randn(7,1),
            "input_proj.weight":torch.randn(hidden,3),"input_proj.bias":torch.randn(hidden),
            "input_ln.weight":torch.ones(hidden),"input_ln.bias":torch.zeros(hidden),
            "out_ln.weight":torch.ones(hidden),"out_ln.bias":torch.zeros(hidden),
            "item_out.weight":torch.randn(hidden,2)})
        history=pd.DataFrame({"user_id":["u1","u1"],"item_id":["a","oov"],"event_group":["view","cart"]})
        cases=pd.DataFrame({"user_id":["u1"]})
        actual=gru_queries(state,history,cases,{"a":2},max_len=3)
        with torch.inference_mode():
            x=torch.cat((f.embedding(torch.tensor([[2,1]]),state["item_emb.weight"]),
                         f.embedding(torch.tensor([[1,3]]),state["event_emb.weight"])),dim=-1)
            x=f.layer_norm(f.linear(x,state["input_proj.weight"],state["input_proj.bias"]),(hidden,))
            x,_=gru(x)
            expected=f.normalize(f.layer_norm(x,(hidden,))[:,-1],dim=-1).numpy()
            item=f.normalize(f.linear(state["item_emb.weight"][2:],state["item_out.weight"]),dim=-1).numpy()
        np.testing.assert_allclose(actual,expected,rtol=1e-5,atol=1e-6)
        e=state["item_emb.weight"][2:].numpy()
        w=state["item_out.weight"].numpy()
        fast=(actual@w)@e.T/np.linalg.norm(e@w.T,axis=1)
        np.testing.assert_allclose(fast,actual@item.T,rtol=1e-5,atol=1e-6)


if __name__=="__main__":
    unittest.main()
