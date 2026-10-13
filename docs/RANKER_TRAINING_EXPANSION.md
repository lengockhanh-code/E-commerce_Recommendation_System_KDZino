# Mở rộng dữ liệu học DCN

Chạy từ `D:\MerRec`:

```powershell
.\.venv\Scripts\python.exe -X utf8 -u scripts/expand_ranker_training.py
```

Thí nghiệm ghi vào `training/dcn/runs/retrieval_expanded_20261010`, không thay
dataset/checkpoint cũ và không đổi đường dẫn Kaggle trong notebook. Có thể chạy
lại để tiếp tục các bước chưa hoàn tất; đổi cấu hình phải chọn thư mục mới.

- TRAIN: giữ 9.997 case cũ, bổ sung đến 30.000 user/case bằng mẫu hash cố định.
  Target là tương tác cuối TRAIN; lịch sử chỉ gồm tương tác có thời gian nhỏ hơn
  target. Cùng timestamp không được đưa vào lịch sử của case mới.
- VAL/TEST: giữ nguyên case cũ để so sánh trên cùng target; đây là giao thức cũ
  lấy target cuối split, cho phép tương tác lại và dùng lịch sử trước target.
- Content: heuristic metadata và item lịch sử xếp theo độ gần đây, top 300;
  không dùng target để chọn candidate. Co-visitation: học từ lịch sử TRAIN
  mở rộng, top 1.000. Two-Tower: checkpoint hiện có, top 3.000,
  `nprobe=24` theo thông số index đã lưu.
- ALS/GRU: dùng lại export cho case cũ. Các case TRAIN bổ sung thiếu hai nguồn
  này; không giả lập kết quả model. Vì vậy đây là thí nghiệm retrieval mở rộng
  ba nguồn, không phải cả năm retriever được export lại hoàn chỉnh.
- Hợp nhất RRF: TRAIN tối đa 1.000 candidate/case, VAL/TEST tối đa 2.000.
  Chỉ TRAIN ưu tiên giữ positive **đã được retrieval tìm thấy** khi cắt pool.
  VAL/TEST không ưu tiên target. Không chèn target thất lạc vào candidate.
- Model retrieval hiện có không được train lại. Metadata catalog và checkpoint
  kế thừa cách xây dựng cũ; không tuyên bố đây là đánh giá retrieval out-of-fold.

Sau khi có `dataset/candidate_audit.json`, train checkpoint DCN riêng:

```powershell
.\.venv\Scripts\python.exe -X utf8 -u scripts/train_dcn_ranker.py --dataset training/dcn/runs/retrieval_expanded_20261010/dataset --output training/dcn/runs/retrieval_expanded_20261010/dcn --profile legacy --epochs 10 --patience 3 --threads 4 --train-negatives 499 --streaming
```

DCN chỉ học các case có positive trong pool; số case thực sự học và số dòng
sau lấy negative được in trong log. Tăng số case/candidate không bảo đảm tăng
Recall@20. Chọn checkpoint bằng VAL, TEST chỉ đánh giá sau chọn checkpoint.
Chế độ `--streaming` lấy negative trong SQL trước khi đọc batch Arrow, lưu tensor
vào file memory map và fit scaler trên TRAIN theo từng batch để giới hạn RAM.

Kết quả chạy thực tế ngày 10/10/2026:

| Chỉ số | Cũ | Mở rộng |
| --- | ---: | ---: |
| TRAIN case | 9.997 | 30.000 |
| TRAIN case có positive | 3.159 | 12.003 |
| Dòng thực sự train, tối đa 499 negative/case | 1.579.461 | 6.001.500 |
| VAL candidate recall | 32,11% | 35,51% |
| TEST candidate recall, cùng 4.854 case | 31,62% | 34,24% |
| DCN TEST Recall@20 | 24,10% | 10,94% |
| DCN TEST NDCG@20 | 0,158610 | 0,101681 |

Run mới dừng sau 4 epoch, checkpoint tốt nhất là epoch 1. Train loss giảm
0,634567 → 0,241597 nhưng VAL NDCG@20 giảm 0,103142 → 0,041747: vẫn có
dấu hiệu overfit. Pool và đặc trưng retrieval đã thay đổi, nên không quy toàn bộ
chênh lệch DCN cho riêng số lượng dữ liệu. Retrieval tăng độ bao phủ nhưng
run DCN này chưa cải thiện xếp hạng; chưa thay model đang phục vụ.

Audit: `training/dcn/runs/retrieval_expanded_20261010/dataset/candidate_audit.json`.
Kết quả/checkpoint: `training/dcn/runs/retrieval_expanded_20261010/dcn/`.

## DCN giảm độ phức tạp

Trainer CLI hỗ trợ `--profile compact`; `DCN()` không truyền cấu hình
vẫn tải được kiến trúc checkpoint cũ. Cấu hình mới được lưu trong checkpoint
và các loader offline/online đọc cấu hình này, không đoán số tầng.

- Bỏ embedding `user_id`, `candidate_item_id`, `candidate_product_id` để hạn chế
  ghi nhớ ID ít tương tác. Cá nhân hóa vẫn đến từ điểm/rank của retrieval.
- Giữ embedding brand/category/condition/shipper và toàn bộ 24 đặc trưng số.
- Embedding 8 → 4 chiều; deep 256–128–64 → 64–32; cross 3 → 2 tầng.
- Dropout 0,15 → 0,35; AdamW weight decay 0,00001 → 0,001;
  learning rate 0,001 → 0,0003. Có thể ghi đè hai thông số optimizer bằng CLI.
- Giữ nguyên candidate, target, scaler chỉ fit TRAIN và trọng số positive theo
  tỉ lệ mẫu. Chọn epoch bằng VAL NDCG@20, TEST không chọn cấu hình/epoch.

```powershell
.\.venv\Scripts\python.exe -X utf8 -u scripts/train_dcn_ranker.py --dataset training/dcn/runs/retrieval_expanded_20261010/dataset --output training/dcn/runs/compact_expanded_20261010 --profile compact --streaming --train-negatives 499 --epochs 12 --patience 4 --threads 4 --batch-size 2048
```

Đây là run riêng; không kích hoạt model phục vụ và không sửa đường dẫn notebook.

Kết quả compact đã chạy trên đúng dataset mở rộng (SHA256 ba split khớp run lớn):

| Chỉ số | DCN lớn, pool mở rộng | DCN compact, cùng pool |
| --- | ---: | ---: |
| Tham số | 1.891.809 | 117.777 |
| Dòng TRAIN thực sự học | 6.001.500 | 6.001.500 |
| Epoch đã chạy / epoch tốt nhất | 4 / 1 | 5 / 1 |
| VAL NDCG@20 tốt nhất | 0,103142 | 0,112063 |
| VAL NDCG@20 epoch 4 | 0,041747 | 0,103966 |
| TEST Recall@20 | 10,94% | 11,87% |
| TEST NDCG@20 | 0,101681 | 0,109995 |
| TEST candidate recall | 34,24% | 34,24% |

Giảm 93,77% tham số và giảm rõ mức suy giảm VAL qua các epoch. Tuy nhiên
compact vẫn chọn epoch 1, VAL NDCG@20 giảm còn 0,098674 ở epoch 5 trong
khi train loss tiếp tục giảm: chưa loại bỏ overfit. RRF cùng pool có Recall@20
16,15% và NDCG@20 0,063443; compact cải thiện NDCG nhưng Recall@20 vẫn thấp
hơn RRF. Kết quả cũ 24,10% dùng pool khác, không gộp làm đối chứng cùng pool.

Notebook `training/models/06_dcn.ipynb` đã đồng bộ cấu hình compact, optimizer
và checkpoint metadata; chỉ thay cell 36/37/39/43/45. Đường dẫn giữ nguyên.
Notebook chưa chạy toàn bộ trên Kaggle; lớp model notebook đã kiểm tra khớp
logit trainer với cùng state dict. Run CPU dùng trainer streaming ở trên.

Chi tiết: `training/dcn/runs/compact_expanded_20261010/metrics/summary.json`;
đối chiếu/checkpoint parity: `metrics/complexity_comparison.json`;
đồ thị: `metrics/learning_curve.png` trong cùng run.

## Cấu hình hạn chế overfit hơn: numeric + dừng sớm

Sau đối chiếu bằng VAL, CLI và notebook hiện mặc định cấu hình numeric:

- Không dùng embedding categorical; giữ 24 đặc trưng số của retrieval và
  price/popularity. Đây là biến thể DCN bỏ embedding, không phải toàn bộ
  cấu hình DCN trong paper. Cá nhân hóa đến từ các nguồn retrieval.
- Deep 32–16, cross 1 tầng, dropout 0,5: tổng cộng 1.513 tham số.
- Clip đặc trưng sau chuẩn hóa TRAIN vào [-5, 5] ngay trong model để inference
  và training giống nhau. AdamW learning rate 0,0001, weight decay 0,01.
- Patience 1: dừng khi một epoch không cải thiện VAL NDCG@20, nạp lại checkpoint
  tốt nhất. Điều này ưu tiên dừng sớm và có thể bỏ qua sự phục hồi ở epoch sau.
- `--monitor-overfit`: đo cố định 256 case TRAIN có positive và các case VAL
  có positive, cùng tối đa 499 hard negative/case. Probe chỉ chẩn đoán; VAL
  chính thức vẫn dùng toàn bộ candidate và tính cả case retrieval thất bại.

```powershell
.\.venv\Scripts\python.exe -X utf8 -u scripts/train_dcn_ranker.py --dataset training/dcn/runs/retrieval_expanded_20261010/dataset --output training/dcn/runs/numeric_earlystop_20261010 --profile numeric --streaming --train-negatives 499 --epochs 12 --patience 1 --threads 4 --batch-size 2048 --monitor-overfit
```

Run chẩn đoán `numeric_regularized_20261010` đã chạy 5 epoch (patience 4),
chọn epoch 1: VAL NDCG@20 0,136623, VAL Recall@20 22,28%; TEST NDCG@20
0,136906, TEST Recall@20 21,34%, conditional Recall@20 62,33%. Các split
và candidate SHA256 khớp run compact. Compact cùng pool có TEST Recall@20
11,87%, NDCG@20 0,109995. Candidate recall vẫn 34,24%.

Ở checkpoint tốt nhất, chênh lệch NDCG@20 của probe TRAIN–VAL giảm từ
0,098860 (compact) xuống 0,082053 (numeric). Probe lấy mẫu và hai split khác
thời gian, nên khoảng cách không chỉ phản ánh overfit. Numeric vẫn suy giảm
VAL khi train tiếp (epoch 5 NDCG@20 0,093819); không bảo đảm loại bỏ overfit.
Run cuối dùng patience 1 để tránh tiếp tục đến các epoch suy giảm này.

Notebook đã đồng bộ numeric và patience 1, giữ nguyên mọi đường dẫn. 27 kiểm
thử liên quan đạt; lớp notebook khớp state dict và logit trainer. Chưa chạy
toàn notebook trên Kaggle và chưa kích hoạt checkpoint phục vụ.

So sánh/probe/đường học: `training/dcn/runs/numeric_regularized_20261010/metrics/`.
Run cuối: `training/dcn/runs/numeric_earlystop_20261010/metrics/summary.json`.

Run cuối đã hoàn tất: dừng sau epoch 2, nạp checkpoint epoch 1. Trọng số
checkpoint khớp chính xác checkpoint tốt nhất của run chẩn đoán; TEST Recall@20
21,34%, NDCG@20 0,136906. Kiểm tra dataset không đổi, parity loader online
trên checkpoint thật và đường dẫn notebook giữ nguyên được lưu trong
`numeric_earlystop_20261010/metrics/verification.json`. Đường học so sánh nằm
ở `metrics/learning_curve.png` trong run cuối.
