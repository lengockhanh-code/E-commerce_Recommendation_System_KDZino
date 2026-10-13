# Đánh giá DCN bắt nhiều sản phẩm tương lai

Không đổi nhãn trên dataset single-target cũ. Đánh giá riêng bằng lịch sử
TRAIN + VAL, chốt trước tương tác TEST đầu tiên của mỗi user. Model dự đoán
một danh sách tại mốc này; ground truth là toàn bộ item phân biệt user tương
tác trong TEST. Cho phép tương tác lại item đã xem. Không dùng item TEST để
tạo history, chọn candidate hay train/chọn epoch.

Ví dụ user có 10 target tương lai, top 20 bắt được 4: hits@20 = 4,
Recall@20 = 4/10 = 40%, Precision@20 = 4/20 = 20%. Item không trúng nhãn
TEST chưa chắc là item user không thích; đây là đánh giá tương tác quan sát.
Precision dùng K vị trí cố định; vị trí thiếu được tính zero.

Chạy từ root, output phải là thư mục mới:

```powershell
.\.venv\Scripts\python.exe -X utf8 -u -m scripts.evaluate_recommendation_pipeline --output training/evaluation/results/pipeline_multifuture_numeric_20261010 --dcn training/dcn/runs/numeric_earlystop_20261010/model/dcn_best.pt
```

Run đã hoàn tất với checkpoint numeric epoch 1: 5.000 user, 61.030 cặp
user–item tương lai (trung bình 12,206 item/user). Giữ riêng báo cáo cũ.

| Top K | DCN hits (cặp user–item) | Macro Recall | Micro Recall | Precision |
| --- | ---: | ---: | ---: | ---: |
| 20 | 801 | 3,43% | 1,31% | 0,801% |
| 50 | 1.388 | 5,17% | 2,27% | 0,5552% |
| 100 | 2.720 | 8,71% | 4,46% | 0,544% |

Macro Recall là trung bình hits/targets của từng user. Micro Recall là tổng
hits / 61.030 target; user nhiều target góp nhiều hơn vào micro. `avg_hits@20`
= 0,1602 item/user, 637 user có ít nhất một hit trong top 20.

Đối chứng cùng pool: RRF top 20 có 1.362 hit, macro Recall 5,46%, micro
Recall 2,23%; LightGBM có 1.383 hit, macro Recall 5,18%, micro Recall 2,27%.
DCN numeric chưa tốt bằng hai baseline ở top 20 trên giao thức này.

Giới hạn: cache chỉ top100 mỗi retriever, hợp nhất 2.444.585 candidate rows;
pool có 4.547/61.030 target, micro coverage 7,45%. Không dùng lại pool đánh
giá last-target mở rộng. DCN train trên target cuối từng case; inference mới
có mốc cắt lịch sử sớm hơn và nhiều target. Điểm 21,34% single-target không
so trực tiếp với điểm nhiều target này. Catalog/content có metadata tương
lai kế thừa pipeline cũ; chưa phải đánh giá inductive catalog hoàn toàn.

Feature rank normalization của DCN đọc từ `source_topk` trong checkpoint;
không sửa feature dùng cho RRF/LightGBM hoặc dùng target để chọn item.

Kết quả: `training/evaluation/results/pipeline_multifuture_numeric_20261010/`
gồm `summary.json`, `metrics.csv`, `dcn_top100.parquet` và
`verification_audit.json`. SQL độc lập đã khớp hits, macro/micro Recall,
Precision và coverage của pool. 20 kiểm thử liên quan đạt. Không retrain,
không sửa đường dẫn notebook và không kích hoạt model lên website.
