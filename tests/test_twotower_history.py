import ast
import contextlib
import importlib
import io
import json
import math
import os
import random
import shutil
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import duckdb
import numpy as np
import polars as pl
import torch
import torch.nn.functional as F

from scripts.twotower_history import (HistoryTwoTower, history_tensors,
                                      load_history_model, user_queries)

ROOT = Path(__file__).resolve().parents[1]


def notebook_functions(cell_index, names, namespace):
    notebook = json.loads((ROOT/'training/models/05_two_tower.ipynb').read_text(encoding='utf-8'))
    tree = ast.parse(''.join(notebook['cells'][cell_index]['source']))
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<notebook>', 'exec'), namespace)
    return namespace


class TwoTowerHistoryTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        torch.manual_seed(17)
        self.cfg = dict(embed_dim=4,feature_dim=3,hidden_dim=12,dropout=0.,
                        hash_buckets={'brand':8},history_length=3,history_decay=.7,
                        history_dropout=0.,architecture_version=2)
        self.features = {'brand':np.array([0,1,2,3],dtype=np.uint32),
                         'price_z':np.array([-2.,-1.,1.,2.],dtype=np.float32)}
        self.model = HistoryTwoTower(self.cfg,2).eval()
        self.checkpoint = {'cfg':self.cfg,'model':self.model.state_dict(),'n_items':4}

    def test_history_changes_query_for_same_user_and_order_matters(self):
        x,mask=history_tensors([[0,1],[1,0],[2,3]],self.features,self.cfg)
        with torch.inference_mode(): q=self.model.encode_user(torch.tensor([0,0,0]),x,mask).numpy()
        self.assertFalse(np.allclose(q[0],q[1]))
        self.assertFalse(np.allclose(q[0],q[2]))
        np.testing.assert_allclose(np.linalg.norm(q,axis=1),1.,atol=1e-6)

    def test_gradient_and_export_reload_use_same_query(self):
        x,mask=history_tensors([[0,1],[2,3]],self.features,self.cfg)
        self.model.train()
        q=self.model.encode_user(torch.tensor([0,1]),x,mask)
        target={key:torch.as_tensor(values[[2,0]],dtype=torch.float32 if key=='price_z' else torch.long)
                for key,values in self.features.items()}
        loss=F.cross_entropy(q@self.model.encode_item(target).T/.1,torch.arange(2))
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertGreater(self.model.user_mlp[0].weight.grad.abs().sum().item(),0.)
        self.assertGreater(self.model.meta['brand'].weight.grad.coalesce().values().abs().sum().item(),0.)
        sparse=[self.model.user.weight,self.model.meta['brand'].weight]
        dense=list(self.model.mlp.parameters())+list(self.model.user_mlp.parameters())
        before=self.model.user_mlp[0].weight.detach().clone()
        torch.optim.SGD(sparse,lr=.1).step(); torch.optim.AdamW(dense,lr=.01).step()
        self.assertFalse(torch.equal(before,self.model.user_mlp[0].weight))
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            for key,values in self.features.items(): np.save(directory/(key+'.npy'),values)
            torch.save(self.checkpoint,directory/'model.pt')
            checkpoint=torch.load(directory/'model.pt',weights_only=False)
            query=user_queries(checkpoint,[0,1],[[0,1],[2,3]],directory)
            self.model.eval()
            with torch.inference_mode(): expected=self.model.encode_user(torch.tensor([0,1]),x,mask).numpy()
            np.testing.assert_allclose(query,expected,atol=1e-6)
            # Unknown ID works with known-item history, but empty unknown history fails.
            self.assertTrue(np.isfinite(user_queries(checkpoint,[-1],[[2]],directory)).all())
            with self.assertRaises(ValueError): user_queries(checkpoint,[-1],[[]],directory)

    def test_legacy_checkpoint_keeps_old_id_only_query(self):
        checkpoint={'model':{'user.weight':torch.tensor([[3.,4.],[0.,2.]])}}
        np.testing.assert_allclose(user_queries(checkpoint,[0,1],[[1],[0]]),[[.6,.8],[0.,1.]])
        with self.assertRaises(ValueError): user_queries(checkpoint,[-1])

    def test_padding_unknown_items_and_recent_limit(self):
        x,mask=history_tensors([[0,1,2,3,999,-1],[2]],self.features,self.cfg)
        np.testing.assert_array_equal(x['brand'].numpy(),[[1,2,3],[0,0,2]])
        np.testing.assert_array_equal(mask.numpy(),[[True,True,True],[False,False,True]])

    def test_training_history_is_strictly_past_and_repeat_is_allowed(self):
        functions=notebook_functions(5,{'sql_identifier','sql_literal','sequence_query'}, {})
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            # items 1 and 2 occur simultaneously: neither can be the other's history.
            pl.DataFrame({'user_id':['u']*5,'item_id':['a','b','c','a','d'],
                          'ts':[1,2,2,3,4]}).write_parquet(directory/'events.parquet')
            pl.DataFrame({'user_id':['u'],'user_idx':[0]}).write_parquet(directory/'users.parquet')
            pl.DataFrame({'item_id':['a','b','c','d'],'item_idx':[0,1,2,3]}).write_parquet(directory/'items.parquet')
            query=functions['sequence_query'](str(directory/'events.parquet'),str(directory/'users.parquet'),
                  str(directory/'items.parquet'),'user_id','item_id','ts','user_id','user_idx','item_id','item_idx',3)
            with duckdb.connect() as db: rows=db.execute(query+' ORDER BY ts,item_idx').fetchall()
            self.assertEqual(len(rows),4)
            self.assertEqual(rows[0][-1],[0]); self.assertEqual(rows[1][-1],[0])
            self.assertEqual(rows[2][1],0); self.assertIn(0,rows[2][-1])
            self.assertEqual(rows[3][-1],[1,2,0])

    def test_notebook_model_and_inference_model_agree(self):
        functions=notebook_functions(9,{'HistoryTwoTower'}, {'nn':torch.nn,'torch':torch,'F':F})
        model=functions['HistoryTwoTower'](self.cfg,2).eval()
        model.load_state_dict(self.model.state_dict())
        x,mask=history_tensors([[0,1],[2,3]],self.features,self.cfg)
        with torch.inference_mode():
            np.testing.assert_allclose(model.encode_user(torch.tensor([0,1]),x,mask),
                                       self.model.encode_user(torch.tensor([0,1]),x,mask))

    def test_future_metric_counts_distinct_items_including_cold(self):
        functions=notebook_functions(10,{'targets'}, {})
        df=pl.DataFrame({'user_idx':[0,0,0],'item_idx':[1,1,None],
                         'target_item_id':['a','a','cold'],'is_positive':[1,1,1],
                         'is_strong':[0,0,0],'is_purchase':[0,0,0]})
        targets,counts=functions['targets'](df)
        self.assertEqual(targets['ALL'][0],{1})
        self.assertEqual(counts['ALL'][0],2)

    def test_notebook_train_evaluate_package_and_online_inference(self):
        """Run real notebook stages on a small dataset, not the large Kaggle data."""
        import faiss
        import gc
        import pyarrow as pa
        import pyarrow.parquet as pq
        from datetime import datetime
        from scripts import online_models
        faiss.omp_set_num_threads(2)
        notebook=json.loads((ROOT/'training/models/05_two_tower.ipynb').read_text(encoding='utf-8'))
        cfg={**self.cfg,'epochs':1,'batch_size':8,'user_lr':.08,'dense_lr':.001,
             'weight_decay':1e-5,'grad_clip':1.,'checkpoint_minutes':35,'patience':2,
             'val_users':2,'test_users':2,'val_random_items':4,'eval_ks':[10,20,50,100],
             'retrieve_extra':2,'temperature':.1,'faiss_nlist':1,'faiss_m':2,
             'faiss_nbits':1,'faiss_nprobe':1,'faiss_train_sample':4,'faiss_batch':4}
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory); tower=directory/'working'/'TwoTower'
            for folder in ('processed','features','checkpoints','model','index','metrics','status','serving'):
                (tower/folder).mkdir(parents=True)
            inputs=directory/'input'; inputs.mkdir()
            users=inputs/'train_user_map.parquet'; items=inputs/'train_item_map.parquet'
            pl.DataFrame({'user_id':['u0','u1'],'user_idx':[0,1]}).write_parquet(users)
            # Physical row order deliberately differs from ANN IDs.
            pl.DataFrame({'item_id':['c','a','d','b'],'item_idx':[2,0,3,1]}).write_parquet(items)
            catalog=inputs/'item_features.parquet'
            pl.DataFrame({'item_id':['a','b','c','d'],'brand':['A','B','C','D'],
                          'price':[10.,20.,30.,40.]}).write_parquet(catalog)
            interactions=inputs/'interactions'
            for split,ids,timestamps in [('train',['a','b','c','d'],[1,2,3,4]),
                                         ('val',['b','cold','b'],[5,6,7]),
                                         ('test',['d','a','cold'],[8,9,10])]:
                folder=interactions/('split='+split); folder.mkdir(parents=True)
                pl.DataFrame({'user_id':[u for u in ('u0','u1') for _ in ids],
                              'item_id':ids*2,'ts':timestamps*2,
                              'event_group':['view']*(len(ids)*2)}).write_parquet(folder/'part.parquet')
            ns={'CFG':cfg,'SEED':17,'DEVICE':torch.device('cpu'),'ROOT':tower,'WORK':tower.parent,
                'USER_MAP':users,'ITEM_MAP':items,'CAT':catalog,'INTDIR':interactions,
                'UID':'user_id','UIX':'user_idx','IID':'item_id','IIX':'item_idx',
                'N_USERS':2,'N_ITEMS':4,'pl':pl,'np':np,'pa':pa,'pq':pq,'torch':torch,
                'nn':torch.nn,'F':F,'SGD':torch.optim.SGD,'AdamW':torch.optim.AdamW,
                'Path':Path,'json':json,'os':os,'shutil':shutil,'gc':gc,'math':math,
                'random':random,'time':time,'zipfile':zipfile,'datetime':datetime,
                'res':lambda:None,'ensure':lambda name:importlib.import_module(name),
                'schema':lambda path:pq.ParquetFile(path).schema_arrow.names,
                'atomic_json':lambda data,path:Path(path).write_text(json.dumps(data),encoding='utf-8'),
                'atomic_torch':lambda data,path:torch.save(data,path)}
            def col(names,choices,required=True):
                result=next((c for c in choices if c in names),None)
                if result is None and required: raise KeyError(choices)
                return result
            ns['col']=col; ns['faiss']=faiss
            with contextlib.redirect_stdout(io.StringIO()):
                for i in (5,6,7,9,10,11,12,13):
                    exec(compile(''.join(notebook['cells'][i]['source']),'<notebook-cell-'+str(i)+'>','exec'),ns)
                # Exercise the actual Kaggle branch without changing notebook paths.
                tree=ast.parse(''.join(notebook['cells'][14]['source']))
                exec(compile(ast.Module(body=tree.body[0].body+tree.body[1:],type_ignores=[]),'<kaggle-eval>','exec'),ns)
                exec(''.join(notebook['cells'][15]['source']),ns)
            self.assertEqual(ns['best']['epoch'],1)
            self.assertTrue(np.isfinite(ns['history'][0]['loss']))
            self.assertEqual(ns['test_full']['ALL']['targets_all'],6)
            self.assertEqual(ns['test_full']['ALL']['targets_warm'],4)
            self.assertEqual(ns['test_full']['ALL']['Recall@100'],2/3)
            result=ns['recommend_user']('u0',['a','b'],3)
            self.assertEqual(result.height,3)
            self.assertEqual(ns['recommend_user']('unknown',['a'],2).height,2)
            with self.assertRaises(ValueError): ns['recommend_user']('unknown',[],2)
            package=directory/'artifacts'/'TwoTower'; package.mkdir(parents=True)
            with zipfile.ZipFile(ns['ZIP']) as archive:
                self.assertIn('features/brand.npy',archive.namelist())
                self.assertIn('features/price_z.npy',archive.namelist())
                self.assertIn('twotower_history.py',archive.namelist())
                archive.extractall(package)
            with patch.object(online_models,'ARTIFACTS',package.parent):
                scores,status=online_models.twotower_scores([{'item_id':i} for i in ['a','b','c','d']],
                         {'user_id':'u0','history':[{'item_id':'a'},{'item_id':'b'}]})
            self.assertEqual(status,'ready')
            self.assertEqual(set(scores),{'a','b','c','d'})
            from scripts import export_all_candidate_datasets as exporter
            cases_dir=directory/'cases'; cases_dir.mkdir()
            export_dir=directory/'exports'; export_dir.mkdir()
            # Mirror the normal artifact layout, using the package just generated.
            model_root=directory/'artifacts'/'merrec_models'; model_root.mkdir()
            shutil.move(str(package),str(model_root/'TwoTower'))
            pl.DataFrame({'case_id':[0,1],'user_id':['u0','unknown'],
                          'target_item_id':['d','a'],'history_item_ids':[['a','b'],['c','d']]
                          }).write_parquet(cases_dir/'cases_test.parquet')
            with patch.object(exporter,'ROOT',directory), patch.object(exporter,'CASES_DIR',cases_dir), \
                 patch.object(exporter,'EXPORTS_DIR',export_dir), \
                 patch.object(exporter,'MODEL_SPECS',{'twotower':{'topk':3}}), \
                 contextlib.redirect_stdout(io.StringIO()):
                exporter.export_twotower('test')
                result=pl.read_parquet(export_dir/'twotower_test.parquet')
                self.assertEqual(result.height,6)
                self.assertEqual(set(result['case_id']),{0,1})
                self.assertTrue(set(result['candidate_item_id'])<={'a','b','c','d'})
                timestamp=(export_dir/'twotower_test.parquet').stat().st_mtime_ns
                exporter.export_twotower('test')
                self.assertEqual(timestamp,(export_dir/'twotower_test.parquet').stat().st_mtime_ns)
            # Release memory maps before Windows removes the temporary directory.
            for values in ns['ITEM_MM'].values(): values._mmap.close()
            if 'a' in ns and isinstance(ns['a'],np.memmap): ns['a']._mmap.close()
            ns.clear(); gc.collect()


if __name__=='__main__': unittest.main()
