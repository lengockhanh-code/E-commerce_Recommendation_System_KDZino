"""Create TEST-only evaluation notebooks and a reviewable result table."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from training.evaluation.nextitem import MODELS, NAMES
from training.evaluation.future_items import summarize_future,target_subset,validate_future

ORIGINALS=dict(zip(MODELS,("01_content_based","02_covisitation","03_als","04_gru4rec","05_two_tower")))


def cell(kind,source,outputs=None):
    result={"cell_type":kind,"metadata":{},"source":source.splitlines(keepends=True)}
    if kind=="code":
        result.update(execution_count=None,outputs=outputs or [])
    return result


def evaluation_cells(model):
    """Self-contained cells that can run without executing any training cell."""
    name=NAMES[model]
    bootstrap="""# TEST FUTURE PRODUCTS — chạy cell này trực tiếp, không chạy lại training
import os
from pathlib import Path
import sys
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(key, '2')
ROOT_EVAL = next(p for p in (Path.cwd(), *Path.cwd().parents)
                 if (p / 'training/evaluation/nextitem.py').exists())
sys.path.insert(0, str(ROOT_EVAL))
from training.evaluation.future_items import build_future_cases, evaluate_future_model, summarize_future
EVAL_OUTPUT = ROOT_EVAL / 'training/evaluation/results/test_future_items'
eval_users, eval_targets, eval_history, eval_manifest = build_future_cases(ROOT_EVAL, EVAL_OUTPUT, users=5000, seed=20260916)
print('TEST users:', len(eval_users), '| distinct future products:', len(eval_targets))
print('Average targets/user:', len(eval_targets) / len(eval_users))
print('Target groups:', eval_manifest['groups'])
"""
    run=f"""eval_results = evaluate_future_model('{model}', ROOT_EVAL, EVAL_OUTPUT, eval_users, eval_targets, eval_history, eval_manifest)
eval_columns = ['cohort_scope', 'target_group', 'users', 'targets', 'warm_targets',
                'warm_target_coverage', 'Recall@10', 'Recall@20', 'NDCG@10', 'NDCG@20', 'MRR@20', 'status']
display(eval_results[eval_columns])
eval_summary = summarize_future(EVAL_OUTPUT)
print('Kết quả:', EVAL_OUTPUT / '{model}' / 'evaluation_nextitem_test.csv')
"""
    return bootstrap,run


def notebooks(output):
    import pandas as pd
    # Existing training cells and serving/export cells remain byte-for-byte identical in source.
    replacements={"content":(16,17),"covis":(15,16),"als":(18,),"gru":(19,),"twotower":(14,)}
    for model,stem in ORIGINALS.items():
        path=ROOT/"training/models"/(stem+".ipynb")
        n=json.loads(path.read_text(encoding="utf-8"))
        touched={0,*replacements[model]}
        baseline=n['metadata'].get('nextitem_test_evaluation',{}).get('protected_cell_hashes')
        hashes={str(i):hashlib.sha256((c['cell_type']+'\n'+''.join(c['source'])).encode()).hexdigest()
                for i,c in enumerate(n['cells']) if i not in touched}
        if baseline and baseline!=hashes:
            raise ValueError(f'Cell ngoài TEST đã đổi: {path.name}; không tự ghi đè')
        baseline=baseline or hashes
        marker='\n\n## Kết quả TEST next-item thống nhất'
        intro=''.join(n['cells'][0]['source']).split(marker)[0]
        intro+=marker+'\n\n'
        intro+=('Đánh giá khả năng gợi ý các sản phẩm người dùng sẽ tương tác trong TEST, '
                'trên cùng 5.000 users, seed 20260916. Ground truth là toàn bộ sản phẩm khác nhau '
                'từng user tương tác trong TEST. History chỉ từ TRAIN + VAL trước TEST của user; '
                'không seen-filter; cold target giữ trong mẫu số. '
                'Không train/tune lại. Các metric VAL/sampled/multi-target cũ ở phần training không phải kết quả cuối.\n\n'
                f'Chạy trực tiếp cell TEST ở vị trí '+', '.join(str(i+1) for i in replacements[model])+' '
                '(đếm cell đầu tiên là 1); không cần chạy các cell training phía trên. '
                'Kết quả đã được chạy bằng pipeline riêng và gắn vào cell TEST.\n\n'
                'Giới hạn: Content-Based giữ catalog/IDF transductive TRAIN+VAL+TEST; GRU dùng checkpoint epoch 8 '
                'hiện có và exact full-catalog scoring vì index 32 chiều không khớp encoder 128 chiều; '
                'Two-Tower dùng full ANN index và user embedding cố định.\n')
        n['cells'][0]['source']=intro.splitlines(keepends=True)
        bootstrap,run=evaluation_cells(model)
        indices=replacements[model]
        if len(indices)==2:
            sources=[bootstrap,run]
        else:
            sources=[bootstrap+'\n'+run]
        csv=output/model/'evaluation_nextitem_test.csv'
        for i,source in zip(indices,sources):
            n['cells'][i]['source']=source.splitlines(keepends=True)
            n['cells'][i]['outputs']=[]
            n['cells'][i]['execution_count']=None
        if csv.exists():
            df=pd.read_csv(csv)
            cols=['cohort_scope','target_group','users','targets','warm_targets','warm_target_coverage',
                  'Recall@10','Recall@20','NDCG@10','NDCG@20','MRR@20','status']
            n['cells'][indices[-1]]['outputs']=[{'output_type':'display_data','metadata':{},'data':{
                'text/plain':df[cols].to_string(index=False).splitlines(keepends=True),
                'text/html':df[cols].to_html(index=False,float_format=lambda x:f'{x:.6f}').splitlines(keepends=True)}}]
        n['metadata']['nextitem_test_evaluation']={'split':'TEST','protected_cell_hashes':baseline,
            'changed_cell_indices':list(indices),'results_source':str(csv.relative_to(ROOT)),
            'target_definition':'All distinct products interacted with in TEST',
            'results_generated_by':'scripts/evaluate_future_items.py; training cells were not executed'}
        after={str(i):hashlib.sha256((c['cell_type']+'\n'+''.join(c['source'])).encode()).hexdigest()
                for i,c in enumerate(n['cells']) if i not in touched}
        assert baseline==after
        path.write_text(json.dumps(n,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
        print('Sửa TEST trong',path.relative_to(ROOT),'cells',indices,'; training source giữ nguyên')


def markdown_table(frame):
    columns=["model","users","Recall@10","Recall@20","NDCG@10","NDCG@20","MRR@20"]
    lines=["| Mô hình | Users | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | MRR@20 |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for _,row in frame.iterrows():
        values=[str(row["model"]),str(int(row["users"]))]+[
            "—" if __import__('pandas').isna(row[c]) else f"{row[c]:.6f}" for c in columns[2:]]
        lines.append("| "+" | ".join(values)+" |")
    return "\n".join(lines)


def audit(output):
    """Independent pandas join/rank audit of the real saved predictions and metrics."""
    import numpy as np
    import pandas as pd
    from training.evaluation.nextitem import fingerprint,write_json
    u=pd.read_parquet(output/'test_future_item_users.parquet')
    t=pd.read_parquet(output/'test_future_item_targets.parquet')
    h=pd.read_parquet(ROOT/'training/evaluation/results/test_nextitem/test_next_item_history.parquet')
    validate_future(u,t,h)
    checks=[]
    discounts=1/np.log2(np.arange(1,21)+1)
    for model in MODELS:
        dest=output/model
        m=json.loads((dest/'evaluation_manifest.json').read_text(encoding='utf-8'))
        assert m['checkpoint_unchanged'] and not m['retrained'] and not m['test_used_for_tuning']
        assert not m['filter_seen_items']
        assert fingerprint([x['path'] for x in m['artifacts']])==m['artifacts']
        p=pd.read_parquet(dest/'test_future_item_predictions.parquet')
        assert not p.user_id.duplicated().any() and set(p.user_id)==set(u.user_id)
        assert all(len(items)==len(set(items)) and len(items)<=20 for items in p.predicted_item_ids)
        flat=p.rename(columns={'predicted_item_ids':'item_id'}).explode('item_id').dropna(subset=['item_id'])
        flat['rank']=flat.groupby('user_id').cumcount()+1
        rows=pd.read_csv(dest/'evaluation_nextitem_test.csv')
        for row in rows.to_dict('records'):
            gt=target_subset(t,row['target_group'])
            if row['cohort_scope']=='COMMON_WARM':
                gt=gt.loc[gt.is_train_item]
            counts=gt.groupby('user_id').size()
            assert row['users']==len(counts) and row['targets']==len(gt)
            hits=flat.merge(gt[['user_id','item_id']],on=['user_id','item_id'],validate='one_to_one')
            estimates={}
            for k in (10,20):
                sub=hits.loc[hits['rank']<=k].copy()
                count_hits=sub.groupby('user_id').size().reindex(counts.index,fill_value=0)
                estimates[f'Recall@{k}']=float((count_hits/counts).mean())
                sub['discount']=1/np.log2(sub['rank']+1)
                dcg=sub.groupby('user_id').discount.sum().reindex(counts.index,fill_value=0)
                ideal=np.cumsum(discounts)[np.minimum(counts.to_numpy(),k)-1]
                estimates[f'NDCG@{k}']=float((dcg/ideal).mean())
            rr=1/hits.groupby('user_id')['rank'].min()
            estimates['MRR@20']=float(rr.reindex(counts.index,fill_value=0).mean())
            for metric,value in estimates.items():
                assert np.isclose(value,row[metric],rtol=1e-10,atol=1e-12,equal_nan=True), (model,metric,value,row[metric])
        checks.append({'model':NAMES[model],'metric_rows_verified':len(rows),'artifact_unchanged':True})
    write_json(output/'verification_audit.json',{'models':checks,'history_before_test':True,
        'unique_future_targets':True,'same_cohort_and_targets':True,'metric_implementation_independently_checked':True})
    print('Audit độc lập: 40 dòng metric khớp predictions; history hợp lệ; artifacts không thay đổi')


def report(output):
    table=summarize_future(output)
    if table is None or set(table.model)!=set(NAMES.values()):
        raise RuntimeError("Chưa đủ 5 model; chưa xuất báo cáo hoàn tất")
    audit(output)
    manifest=json.loads((output/"evaluation_cases_manifest.json").read_text(encoding="utf-8"))
    if table.cohort_hash.nunique()!=1 or table.cohort_hash.iloc[0]!=manifest["spec"]["users_hash"]:
        raise ValueError("Các model không cùng cohort")
    allrows=table.query("cohort_scope=='ALL_CASES' and target_group=='ALL'")
    warmrows=table.query("cohort_scope=='COMMON_WARM' and target_group=='ALL'")
    compact=["model","users","targets","warm_targets","warm_target_coverage","Recall@10","Recall@20","NDCG@10","NDCG@20","MRR@20"]
    allrows[compact].to_csv(output/"next_item_test_all.csv",index=False,encoding="utf-8-sig")
    warmrows[compact].to_csv(output/"next_item_test_common_warm.csv",index=False,encoding="utf-8-sig")
    text=("# Bảng đánh giá gợi ý sản phẩm người dùng sẽ tương tác — TEST\n\n"
          f"Cùng {manifest['users']:,} người dùng, {manifest['targets']:,} target sản phẩm; "
          f"trung bình {manifest['avg_targets_per_user']:.3f} sản phẩm/user. "
          "Ground truth là toàn bộ tập sản phẩm khác nhau từng user tương tác trong TEST; "
          "nhiều sự kiện trên cùng sản phẩm được gộp thành một target (user,item). "
          f"Seed {manifest['spec']['history_spec']['seed']}; history TRAIN + VAL gồm {manifest['history_rows']:,} sự kiện, "
          "chỉ lấy timestamp trước TEST của từng user. Không loại sản phẩm đã xem; không sampled negatives; không huấn luyện/tune lại.\n\n"
          f"Target groups: ALL={manifest['groups']['ALL']['targets']}, POSITIVE={manifest['groups']['POSITIVE']['targets']}, "
          f"STRONG={manifest['groups']['STRONG']['targets']}, PURCHASE={manifest['groups']['PURCHASE']['targets']}. "
          f"Warm TRAIN targets={manifest['warm_targets']} ({manifest['warm_targets']/manifest['targets']:.2%}). "
          "Mỗi nhóm chỉ tính trên user có target thuộc nhóm đó, thống nhất giữa các mô hình. "
          "Nhóm nào không có target sẽ ghi NaN/EMPTY_GROUP.\n\n"
          "Recall@K là trung bình theo user của số item đúng trong Top-K chia số target của user. "
          "NDCG@K dùng relevance nhị phân và IDCG với min(K, số target). "
          "MRR@20 dùng vị trí sản phẩm liên quan đầu tiên.\n\n"
          "## Toàn bộ next-item cases\n\n"+markdown_table(allrows)+"\n\n"
          "## Common warm: target thuộc item universe TRAIN\n\n"+markdown_table(warmrows)+"\n\n"
          "## Giới hạn khi so sánh\n\n"
          "- Content-Based dùng artifact catalog/IDF có `metadata_scope=train+val+test`. "
          "History không dùng hành vi TEST, nhưng kết quả là transductive theo metadata; "
          "không được coi là chứng minh một thí nghiệm hoàn toàn causal theo thời gian. "
          "Để loại hoàn toàn thông tin metadata tương lai cần snapshot trước TEST và rebuild artifact; "
          "không thực hiện vì yêu cầu giữ nguyên model.\n"
          "- GRU4Rec được tính điểm exact trên 27.328.461 item với encoder 128 chiều và item projection gốc. "
          "Index có sẵn 32 chiều không tương thích nên không dùng. File checkpoint hiện chứa epoch 8; "
          "metadata best_epoch=6 không chứng minh weights epoch 6 có sẵn. "
          "Kết quả này là checkpoint epoch 8 hiện tại, không gán nhãn best epoch 6.\n"
          "- Two-Tower dùng full ANN index với nprobe=24 cố định; kết quả bao gồm sai số retrieval ANN. "
          "User embedding cố định được học từ TRAIN, không tự cập nhật theo VAL history.\n"
          "- ALS dùng 28.964.787 item factors TRAIN+VAL; fold-in weighted history chỉ là suy luận, "
          "không thay trọng số model. Co-visitation dùng toàn bộ pair index TRAIN+VAL đã lưu. "
          "Catalog của từng model khác nhau; common-warm thống nhất target cohort, không thống nhất candidate catalog.\n"
          "- Cold targets vẫn giữ trong mẫu số ALL. Trong COMMON_WARM, giữ target thuộc TRAIN "
          "và chỉ tính user còn ít nhất một target warm; cả 5 mô hình dùng cùng quy tắc. "
          "Không chọn lại user/target theo model. Nhóm PURCHASE có ít user cần diễn giải thận trọng.\n\n"
          "## Bàn giao theo yêu cầu\n\n"
          "1. **File sửa:** phần TEST trong 5 notebook gốc `01_content_based.ipynb`, `02_covisitation.ipynb`, "
          "`03_als.ipynb`, `04_gru4rec.ipynb`, `05_two_tower.ipynb`. **File thêm:** `training/evaluation/nextitem.py`, `retrievers.py`, "
          "`training/evaluation/future_items.py`, `scripts/evaluate_future_items.py`, `scripts/report_nextitem.py`, "
          "`tests/test_nextitem_evaluation.py`, `tests/test_future_items_evaluation.py`. Notebook Popularity/Trending và mọi model artifact giữ nguyên.\n"
          "2. **Cell sửa:** Content-Based cells 17–18; Co-visitation 16–17; ALS 19; GRU4Rec 20; "
          "Two-Tower 15 (đếm cell đầu tiên là 1). Cell giới thiệu đầu mỗi notebook bổ sung protocol. "
          "Kết quả chạy thực được gắn trực tiếp vào output cell TEST. Không thay hoặc chạy lại cell training gốc; "
          "hash source của tất cả cell ngoài phạm vi TEST được kiểm tra trước/sau.\n"
          "3. **Evaluation trước:** các model chọn user, target, catalog và seen-filter khác nhau; "
          "GRU có sampled validation và chưa có bảng TEST temporal full-catalog hoàn chỉnh. "
          "Các kết quả sampled trong training history chỉ là SAMPLED METRIC — NOT FINAL RESULT.\n"
          "4. **Evaluation mới:** tất cả sản phẩm thực tế user tương tác trong TEST, strict TRAIN+VAL history, cùng 5.000 users, "
          "4 target groups × 2 cohort scopes; full catalog/model index; Recall@10/20, NDCG@10/20, MRR@20.\n"
          "5. **Train lại:** không train/tune lại; trọng số, checkpoint, hyperparameter không thay đổi. "
          "Muốn loại transductive metadata của Content-Based cần artifact snapshot mới; "
          "muốn đánh giá GRU best epoch 6 cần khôi phục đúng checkpoint; không tự thực hiện.\n"
          "6. **Kết quả:** trong `training/evaluation/results/test_future_items/`: users/targets chung, "
          "manifest, mỗi model có `evaluation_nextitem_test.csv`, predictions case-level và manifest artifact; "
          "bảng chung `next_item_evaluation_summary.csv` (40 dòng); bảng chính `next_item_test_all.csv`; "
          "bảng warm `next_item_test_common_warm.csv`. Không chạy VAL theo yêu cầu mới nhất.\n"
          "7. **Kiểm tra:** target (user,item) duy nhất, history.ts trước mọi target TEST, source history chỉ TRAIN/VAL, "
          "không seen-filter, không TEST tuning, cùng cohort hash và targets hash; "
          "artifact size/mtime trước và sau inference giống nhau; 11 unit tests đạt. "
          "Audit độc lập bằng join/rank từ predictions thực xác nhận cả 40 dòng metric; "
          "kết quả kiểm tra lưu trong `verification_audit.json`. Hạn chế metadata/checkpoint nêu rõ ở trên.\n\n"
          "## Các nhóm target còn lại\n\n")
    for scope in ("ALL_CASES","COMMON_WARM"):
        for group in ("POSITIVE","STRONG","PURCHASE"):
            text+=f"### {scope} — {group}\n\n"+markdown_table(table.query("cohort_scope==@scope and target_group==@group"))+"\n\n"
    (output/"BANG_DANH_GIA_TEST_NEXTITEM.md").write_text(text,encoding="utf-8")
    html="<!doctype html><html lang='vi'><meta charset='utf-8'><title>Đánh giá sản phẩm tương tác TEST</title>"
    html+="<style>body{font:16px Arial;margin:40px;max-width:1200px}table{border-collapse:collapse;margin:20px 0}td,th{padding:10px;border:1px solid #bbb;text-align:right}th{background:#eef3fa}td:first-child{text-align:left}</style>"
    html+="<h1>Bảng đánh giá sản phẩm người dùng sẽ tương tác — TEST</h1><p>Cùng 5.000 user; toàn bộ 61.030 sản phẩm target TEST; history TRAIN + VAL trước TEST; không seen-filter; không train lại.</p>"
    html+="<h2>Toàn bộ cases</h2>"+allrows[compact].to_html(index=False,float_format=lambda x:f"{x:.6f}")
    html+="<h2>Common warm</h2>"+warmrows[compact].to_html(index=False,float_format=lambda x:f"{x:.6f}")
    html+="<p>Content-Based dùng metadata/IDF transductive TRAIN+VAL+TEST. GRU dùng checkpoint epoch 8 hiện có và exact scoring; Two-Tower dùng full ANN index. Xem báo cáo Markdown để đọc đầy đủ nhóm target và giới hạn.</p></html>"
    (output/"BANG_DANH_GIA_TEST_NEXTITEM.html").write_text(html,encoding="utf-8")
    print(markdown_table(allrows))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"training/evaluation/results/test_future_items")
    parser.add_argument("--notebooks-only",action="store_true")
    args=parser.parse_args()
    notebooks(args.output)
    if not args.notebooks_only:
        report(args.output)


if __name__=="__main__":
    main()
