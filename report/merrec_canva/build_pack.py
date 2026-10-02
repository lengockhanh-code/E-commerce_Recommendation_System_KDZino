"""Generate Canva-ready outline and figures from existing aggregate artifacts."""
from pathlib import Path
import csv, hashlib, html, json, shutil, zipfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
IMG=OUT/"images"
IMG.mkdir(exist_ok=True)
EDA=ROOT/"data/processed/eda_merrec_may/kernel_1752"
PRE=ROOT/"data/processed/recommender/tables"
MODELS=ROOT/"artifacts/merrec_models"
slides=json.loads((OUT/"slides.json").read_text(encoding="utf-8"))
manifest=[]
BLUE="#244BFF"
TEAL="#159C98"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":13,"axes.spines.top":False,"axes.spines.right":False,"axes.titleweight":"bold","savefig.facecolor":"white"})
def js(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def register(name,sources,note,kind="generated"):
    manifest.append({"file":"images/"+name,"kind":kind,"sources":"; ".join(str(p.relative_to(ROOT)).replace(chr(92),"/") for p in sources),"note":note})
def save(fig,name,sources,note):
    fig.savefig(IMG/name,dpi=200,bbox_inches="tight")
    plt.close(fig)
    register(name,sources,note)
originals={
"03_missing_percentage.png":"Missing tính theo dòng tương tác, không phải item duy nhất.",
"05_user_interactions_log.png":"Histogram mẫu 100.000 user; thống kê slide từ toàn bộ user.",
"06_item_interactions_log.png":"Histogram mẫu 100.000 item; thống kê slide từ toàn bộ item.",
"06_popularity_pareto.png":"Tích lũy tương tác theo độ phổ biến item.",
"07_session_length.png":"Histogram mẫu 100.000 session; khóa (user_id, session_id).",
"07_session_duration.png":"Mẫu 100.000 session; duration = max(ts)-min(ts).",
"09_daily_interactions.png":"UTC; ngày 31/05 chỉ có 88 sự kiện, không đầy đủ ngày.",
"09_hourly_interactions.png":"Giờ UTC, không phải giờ địa phương.",
"09_day_hour_heatmap.png":"Heatmap theo UTC.",
"10_top_category0.png":"Số tương tác, không phải số item.",
"10_top_category1.png":"Số tương tác, không phải số item.",
"11_price_hist.png":"Ảnh EDA gốc; xem notebook về cách lấy mẫu.",
"11_price_log_hist.png":"Ảnh giá trên thang log; không tự quy đổi tiền tệ.",
"12_k_core_removed.png":"One-pass diagnostic, không phải k-core hội tụ hoặc bước lọc cuối."
}
for name,note in originals.items():
    src=EDA/"figures"/name
    shutil.copy2(src,IMG/name)
    register(name,[src,ROOT/"training/00_eda.ipynb"],note,"original_copy")

events=pd.read_csv(PRE/"01_event_mapping.csv")
events["pct"]=100*events.interactions/events.interactions.sum()
fig,ax=plt.subplots(figsize=(12,5.5))
bars=ax.barh(events.event_group,events.pct,color=[BLUE,TEAL,"#7590FF","#8996B5","#F3B047","#E87A62"])
ax.invert_yaxis()
ax.set(xlabel="Tỷ lệ trên tổng tương tác (%)",title="Sáu hành vi sau khi chuẩn hóa đúng mapping",xlim=(0,108))
for b,r in zip(bars,events.itertuples()):
    ax.text(b.get_width()+.7,b.get_y()+b.get_height()/2,f"{r.pct:.3f}% | {r.interactions:,}",va="center",fontsize=11)
save(fig,"s15_event_mapping_corrected.png",[PRE/"01_event_mapping.csv"],"Vẽ từ số đếm đã lưu. cart/offer đúng mapping preprocessing; không dùng funnel EDA cũ.")

fig,ax=plt.subplots(figsize=(11,5))
bars=ax.bar(["view","like","cart","offer","buy_start","buy_comp"],[1,2,4,5,7,10],color=BLUE)
ax.bar_label(bars)
ax.set(ylabel="Trọng số quy ước",title="Trọng số implicit feedback trong preprocessing",ylim=(0,12))
save(fig,"s23_event_weights.png",[ROOT/"training/01_preprocess.ipynb"],"Trọng số cấu hình, không phải tham số học được.")

split=pd.read_csv(PRE/"02_split_summary.csv")
fig,ax=plt.subplots(figsize=(12,4.8))
start=0
for r,color,label in zip(split.itertuples(),[BLUE,TEAL,"#EFAD42"],["TRAIN: 01–25/05","VAL: 26–28/05","TEST: 29–31/05"]):
    width=r.interactions/1e6
    ax.barh([0],[width],left=start,color=color,height=.4)
    ax.text(start+width/2,0,f"{width:.2f}M",ha="center",va="center",color="white",fontsize=11)
    ax.plot([],[],color=color,linewidth=8,label=label)
    start+=width
ax.set(yticks=[],xlabel="Triệu tương tác sau làm sạch",title="TRAIN → VAL → TEST theo thời gian")
ax.legend(loc="lower center",bbox_to_anchor=(.5,-.4),ncol=3,frameon=False,fontsize=11)
fig.subplots_adjust(bottom=.3)
fig.text(.12,.02,"TEST kết thúc 31/05 lúc 00:00:00 UTC; ngày cuối không đầy đủ.",fontsize=11)
save(fig,"s13_temporal_split.png",[PRE/"02_split_summary.csv",PRE/"09_split_integrity.csv"],"Độ rộng theo số tương tác, không phải số ngày. Tổng split 174.725.659.")

cold=pd.read_csv(PRE/"03_cold_start_summary.csv").set_index("split").loc[["val","test"]]
fig,ax=plt.subplots(figsize=(11,5.7))
x=np.arange(2)
for j,(key,label,color) in enumerate([("pct_cold_user","User chưa thấy",BLUE),("pct_cold_item","Item chưa thấy",TEAL),("pct_both_cold","Cả hai chưa thấy","#F3B047")]):
    bars=ax.bar(x+(j-1)*.24,cold[key],width=.24,label=label,color=color)
    ax.bar_label(bars,fmt="%.2f%%",fontsize=10,padding=3)
ax.set(xticks=x,xticklabels=["Validation","Test"],ylabel="% dòng tương tác",ylim=(0,43),title="Cold-start so với ID mapping của TRAIN")
ax.legend(loc="upper left",fontsize=11,frameon=False)
save(fig,"s14_cold_start.png",[PRE/"03_cold_start_summary.csv"],"Tính theo dòng. Cold-user và cold-item giao nhau; không cộng ba cột.")

gh=js(MODELS/"GRU4Rec/metrics/train_history.json")
th=js(MODELS/"TwoTower/metrics/train_history.json")
fig,axs=plt.subplots(1,2,figsize=(13,5))
axs[0].plot([r["epoch"] for r in gh],[r["train_loss"] for r in gh],"o-",color=BLUE)
axs[0].set(title="GRU4Rec · train loss",xlabel="Epoch",ylabel="Loss")
axs[1].plot([r["epoch"] for r in th],[r["loss"] for r in th],"o-",color=TEAL)
axs[1].set(title="Two-Tower · train loss",xlabel="Epoch",ylabel="Loss")
fig.suptitle("Đường huấn luyện từ history đã lưu",fontsize=17,fontweight="bold")
fig.tight_layout()
save(fig,"s34_training_loss.png",[MODELS/"GRU4Rec/metrics/train_history.json",MODELS/"TwoTower/metrics/train_history.json"],"Loss hai mô hình khác mục tiêu; chỉ so xu hướng riêng.")

fig,ax=plt.subplots(figsize=(11,5))
ax.plot([r["epoch"] for r in gh],[100*r["val_Recall@20"] for r in gh],"o-",color=BLUE,linewidth=2)
best=max(gh,key=lambda r:r["val_Recall@20"])
ax.scatter([best["epoch"]],[100*best["val_Recall@20"]],color="#E87A62",s=90,zorder=3)
ax.annotate(f'Epoch {best["epoch"]}: {100*best["val_Recall@20"]:.2f}%',(best["epoch"],100*best["val_Recall@20"]),xytext=(-125,-35),textcoords="offset points",arrowprops={"arrowstyle":"->"})
ax.set(xlabel="Epoch",ylabel="Sampled validation Recall@20 (%)",title="GRU4Rec · 1 target + 255 sampled negatives")
ax.grid(alpha=.15)
save(fig,"s37_gru_sampled_recall.png",[MODELS/"GRU4Rec/metrics/train_history.json",MODELS/"GRU4Rec/metrics/summary.json"],"1.810 user đánh giá; sampled VAL, không phải TEST/full-index.")

ttval=js(MODELS/"TwoTower/metrics/val_full_index_metrics.json")["POSITIVE"]["NDCG@20"]
fig,ax=plt.subplots(figsize=(10,5))
bars=ax.bar(["Pool chọn checkpoint","Full-index FAISS VAL"],[th[-1]["selection"],ttval],color=[BLUE,TEAL])
ax.bar_label(bars,fmt="%.6f",padding=4)
ax.set(ylabel="POSITIVE NDCG@20",title="Two-Tower: metric phụ thuộc giao thức",ylim=(0,.03))
save(fig,"s35_twotower_protocols.png",[MODELS/"TwoTower/metrics/train_history.json",MODELS/"TwoTower/metrics/val_full_index_metrics.json"],"Khác protocol; không quy toàn bộ chênh lệch cho FAISS.")

cbp=ROOT/"training/checkpoints/content_based_full_catalog/evaluation_test.csv"
cvp=ROOT/"training/checkpoints/covisitation/polars_v2/results/test_metrics.csv"
alsp=MODELS/"ALS/metrics/test_metrics.csv"
tp=MODELS/"TwoTower/metrics/test_full_index_metrics.json"
rows=[]
for model,path,scope in [("Content-Based",cbp,"192 user POSITIVE; full metadata catalog"),("Co-visitation",cvp,"2.191 user POSITIVE; refit TRAIN+VAL"),("ALS",alsp,"2.201 user POSITIVE; refit TRAIN+VAL")]:
    r=pd.read_csv(path).query("target_mode == 'POSITIVE'").iloc[0]
    rows.append({"model":model,"Recall@20":float(r["Recall@20"]),"NDCG@20":float(r["NDCG@20"]),"HitRate@20":float(r["HitRate@20"]),"scope":scope,"source":str(path.relative_to(ROOT))})
r=js(tp)["POSITIVE"]
rows.append({"model":"Two-Tower","Recall@20":r["Recall@20"],"NDCG@20":r["NDCG@20"],"HitRate@20":r["HitRate@20"],"scope":"Mẫu TEST cấu hình 5.000 user trước lọc; FAISS full-index","source":str(tp.relative_to(ROOT))})
pd.DataFrame(rows).to_csv(OUT/"ket_qua_trich_xuat.csv",index=False,encoding="utf-8-sig")
fig,ax=plt.subplots(figsize=(14,4.8))
ax.axis("off")
table=ax.table(cellText=[[r["model"],f'{100*r["Recall@20"]:.4f}%',f'{r["NDCG@20"]:.6f}',f'{100*r["HitRate@20"]:.4f}%'] for r in rows],colLabels=["Mô hình","Recall@20","NDCG@20","HitRate@20"],loc="center",cellLoc="center")
table.auto_set_font_size(False);table.set_fontsize(15);table.scale(1,2.3)
for (i,j),cell in table.get_celld().items():
    cell.set_edgecolor("#E0E5EF")
    if i==0:cell.set_facecolor(BLUE);cell.set_text_props(color="white",weight="bold")
    else:cell.set_facecolor("#F4F6FC" if i%2 else "white")
ax.set_title("TEST / POSITIVE đã lưu — không phải bảng xếp hạng",fontsize=17,pad=20)
fig.text(.5,.03,"Khác mẫu user, candidate universe, coverage và lịch sử. GRU4Rec sampled VAL trình bày riêng.",ha="center",fontsize=11)
save(fig,"s36_results_table.png",[cbp,cvp,alsp,tp],"Giữ thứ tự phương pháp, không xếp hạng. Không có SASRec.")

assert len(slides)==40 and [s[0] for s in slides]==list(range(1,41))
for s in slides:
    for name in s[5]:assert (IMG/name).is_file(),name
    for source in s[6]:assert source.startswith("https://") or (ROOT/source).exists(),source
for m in manifest:
    m["sha256"]=hashlib.sha256((OUT/m["file"]).read_bytes()).hexdigest()
    m["slides"]=", ".join(str(s[0]) for s in slides if Path(m["file"]).name in s[5])
pd.DataFrame(manifest).to_csv(OUT/"danh_muc_anh.csv",index=False,encoding="utf-8-sig")
(OUT/"slides.json").write_text(json.dumps(slides,ensure_ascii=False,indent=2),encoding="utf-8")

intro="""# MerRec — Dàn ý 38 slide chính + 2 trang demo riêng

Trích từ notebook, CSV, JSON và PNG có trong dự án. Không chạy lại EDA hoặc training.

**Phạm vi:** dữ liệu, xử lý, EDA, đặc trưng, mô hình và kết quả. Demo ở phụ lục 39–40. Theo xác nhận của người dùng, SASRec, DCN và LightGBM Ranker chưa có kết quả để báo cáo; không sử dụng metric SASRec cũ.

**Thiết kế:** 16:9, nền trắng, xanh #244BFF, mỗi slide 3–4 ý, nội dung 22–26 pt, ảnh khoảng 55–70%. Ghi chú thuyết trình đưa vào speaker notes. Chỉ các nhãn thiết yếu về protocol/mẫu phải hiện trên slide kết quả.

**Dùng với Canva:** giải nén → tải ảnh trong images lên Canva → dùng tên file tương ứng ở từng slide. Prompt văn bản không tự đọc ảnh trên máy; bạn cần tải ảnh lên. Ảnh web để khung trống cho ảnh chụp sau.

**Nguồn ảnh:** 14 ảnh EDA gốc từ kernel_1752 và 8 ảnh vẽ từ bảng tổng hợp/history. danh_muc_anh.csv ghi nguồn, slide, lưu ý và SHA256. Histogram user/item/session dùng mẫu 100.000; số liệu tóm tắt lấy từ bảng tổng hợp toàn bộ. Biểu đồ event được vẽ lại theo mapping preprocessing chính xác.

**Đánh giá:** các mô hình có tập user, candidate universe và protocol khác nhau; kết quả là bản ghi từng thực nghiệm, không phải leaderboard. GRU4Rec chỉ trình bày sampled validation. Chưa chạy lại kiểm chứng model hoặc ứng dụng web trong công việc chuẩn bị slide.

"""
parts=[intro]
prompt="""Thiết kế 38 slide nghiên cứu tiếng Việt + 2 slide demo tách riêng cuối bài theo nội dung sau. Giữ thứ tự và số trang. Nền trắng, xanh #244BFF, 16:9. Không tự thêm số liệu, phần cứng, mô hình hoàn tất hoặc kết luận vượt quá dữ liệu. SASRec/DCN/LightGBM chưa có kết quả để báo cáo. Không đưa metric SASRec cũ vào slide. Không so sampled VAL của GRU4Rec trực tiếp với TEST/full-index. Bảng slide 36 không phải leaderboard. Dùng ảnh người dùng đã tải lên đúng tên file; không tạo biểu đồ giả hoặc thay bằng hình stock. Nếu chưa có ảnh tải lên, giữ khung đúng tên file. Demo chỉ trang 39–40, để trống khung ảnh web. Đưa ghi chú nguồn và hạn chế chi tiết vào speaker notes, nhưng vẫn hiển thị nhãn giao thức ở slide kết quả.

"""
cards=[]
for n,section,title,bullets,visual,images,sources,note in slides:
    parts.append(f"## Slide {n:02d} — {title}\n\n**Phần:** {section}\n\n**Nội dung lên slide:**\n\n"+"\n".join("- "+b for b in bullets)+"\n\n**Bố cục / hình:** "+visual+"\n\n")
    prompt+=f"SLIDE {n:02d} | {section} | {title}\n"+"\n".join("- "+b for b in bullets)+"\nBố cục: "+visual+"\n"
    for name in images:parts.append(f"![{name}](images/{name})\n\nẢnh: [images/{name}](images/{name})\n\n")
    if images:prompt+="Ảnh tải lên: "+", ".join(images)+"\n"
    if note:
        parts.append("**Ghi chú thuyết trình:** "+note+"\n\n")
        prompt+="Speaker notes: "+note+"\n"
    if sources:parts.append("**Nguồn:** "+"; ".join("`"+p+"`" for p in sources)+"\n\n")
    parts.append("---\n\n");prompt+="\n"
    pics="".join(f'<figure><a href="images/{name}" download><img loading="lazy" src="images/{name}" alt="{name}"></a><figcaption>{name} · nhấn ảnh để tải</figcaption></figure>' for name in images)
    card=f'<section id="s{n}"><div class="tag">{n:02d}/40 · {html.escape(section)}</div><h2>{html.escape(title)}</h2><ul>'
    card+="".join("<li>"+html.escape(b)+"</li>" for b in bullets)+"</ul><p class=layout>"+html.escape(visual)+'</p><div class=pictures>'+pics+"</div>"
    if note:card+="<aside>"+html.escape(note)+"</aside>"
    card+="<details><summary>Nguồn trong repository</summary><p>"+html.escape("; ".join(sources))+"</p></details></section>"
    cards.append(card)
(OUT/"DAN_Y_38_SLIDE.md").write_text("".join(parts),encoding="utf-8")
(OUT/"PROMPT_CANVA.txt").write_text(prompt,encoding="utf-8")
page="""<!doctype html><html lang=vi><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>MerRec — Dàn ý và ảnh Canva</title><style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;background:#edf1f8;color:#15223a;margin:0;line-height:1.65}header,main{max-width:1180px;margin:auto;padding:28px}h1{font-size:34px;line-height:1.2}h2{font-size:27px;line-height:1.3}.tag{color:#244bff;font-weight:bold;font-size:14px}section{background:white;border-radius:16px;padding:32px;margin-bottom:24px}li{margin:8px 0;font-size:18px}.pictures{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}figure{margin:12px 0}img{max-width:100%;height:auto;border:1px solid #e1e6f0}figcaption,details{font-size:13px;color:#52627a;overflow-wrap:anywhere}aside{background:#fff7e6;padding:14px;border-left:4px solid #e8af42;margin:18px 0}.layout{color:#58677d}a{color:#244bff}nav a{display:inline-block;margin:5px;padding:5px 10px;background:white;border-radius:6px}@media(max-width:600px){header,main{padding:14px}section{padding:20px}.pictures{grid-template-columns:1fr}}@media print{body{background:white}section{break-after:page}header,nav{display:none}}
</style><header><h1>MerRec · Dàn ý và ảnh Canva</h1><p>38 slide nghiên cứu + 2 trang demo riêng. Không sử dụng kết quả SASRec.</p><p><a href=DAN_Y_38_SLIDE.md>Dàn ý đầy đủ</a> · <a href=PROMPT_CANVA.txt>Prompt Canva</a> · <a href=danh_muc_anh.csv>Danh mục ảnh và nguồn</a></p><nav>"""
page+="".join(f'<a href="#s{s[0]}">{s[0]:02d}</a>' for s in slides)+"</nav></header><main>"+"".join(cards)+"</main></html>"
(OUT/"XEM_DAN_Y_VA_ANH.html").write_text(page,encoding="utf-8")
(OUT/"README.txt").write_text("MerRec Canva pack\n\nMở XEM_DAN_Y_VA_ANH.html để xem nội dung và ảnh theo từng slide.\nTải ảnh trong images lên Canva rồi dùng PROMPT_CANVA.txt hoặc DAN_Y_38_SLIDE.md.\n38 trang nghiên cứu + 2 trang demo riêng; ảnh demo chèn sau.\nSASRec, DCN, LightGBM chưa có kết quả để báo cáo theo xác nhận người dùng.\nBản PowerPoint chỉnh sửa được: MERREC_THUYET_TRINH_40_SLIDE.pptx; bản xem nhanh: MERREC_THUYET_TRINH_40_SLIDE.pdf.\nNguồn và checksum trong danh_muc_anh.csv.\n",encoding="utf-8")
files=[OUT/name for name in ["README.txt","DAN_Y_38_SLIDE.md","PROMPT_CANVA.txt","XEM_DAN_Y_VA_ANH.html","slides.json","danh_muc_anh.csv","ket_qua_trich_xuat.csv"]] + sorted(IMG.glob("*.png"))
zp=OUT/"MERREC_CANVA_ANH_VA_DAN_Y.zip"
with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(OUT))
with zipfile.ZipFile(zp) as z:assert z.testzip() is None
print(json.dumps({"slides":len(slides),"main":38,"demo":2,"images":len(manifest),"files":len(files),"zip_bytes":zp.stat().st_size,"output":str(OUT)},ensure_ascii=False))
