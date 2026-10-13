# DCN và LightGBM trên cùng pool DCN mở rộng

Đã đánh giá ngày 12/10/2026 bằng checkpoint cố định. Hai model nhận cùng
`training/dcn/runs/retrieval_expanded_20261010/dataset/dcn_test.parquet`:
9.233.311 dòng ứng viên, 4.854 case và 1.662 case có target trong pool.
Candidate recall của cả hai bằng **34,2398%**.

Giao thức có một target cuối/case, cho phép tương tác lại item trong lịch sử.
Không phải benchmark nhiều item tương lai với pool top 100 mỗi nguồn.
Không thêm target vào pool, không lọc ứng viên riêng cho từng model và không
chọn checkpoint, trọng số blend hoặc siêu tham số theo TEST.

| Phương pháp | Recall@20 | NDCG@20 | Recall@100 | Conditional Recall@20 |
|---|---:|---:|---:|---:|
| RRF | 16,15% | 0,063443 | 26,39% | 47,17% |
| DCN thuần | 21,34% | 0,136906 | 21,76% | 62,33% |
| LightGBM thuần | 18,81% | 0,140888 | 19,22% | 54,93% |
| LightGBM + RRF, trọng số model cố định 0,7 | 19,80% | 0,130848 | 20,44% | 57,82% |

DCN đưa target vào top 20 ở nhiều case hơn LightGBM thuần. LightGBM có NDCG@20
cao hơn: thứ hạng của những target mà nó bắt được có đóng góp chiết khấu cao hơn.
RRF bắt nhiều target hơn ở top 100, nhưng các ranker ưu tiên target tốt hơn ở đầu
danh sách. Không có phương pháp tốt nhất ở mọi K và mọi chỉ số.

Conditional Recall chỉ tính 1.662 case có target trong pool. Recall thông thường
tính toàn bộ 4.854 case, kể cả 3.192 case retrieval không tìm thấy target.
Vì vậy candidate recall × conditional Recall@K = Recall@K.

## Checkpoint và phạm vi so sánh

- DCN: `training/dcn/runs/numeric_earlystop_20261010/model/dcn_best.pt`, epoch 1.
- LightGBM: `training/lightgbm_ranker/model/lightgbm_ranker.txt`, 6 cây.
- Hai checkpoint giữ nguyên các bộ dữ liệu huấn luyện trước đó. Lần chạy này
  kiểm soát chung TEST/candidate pool, chưa phải thực nghiệm train cùng TRAIN/VAL.
- Schema LightGBM cũ ghi serving policy `exclude_history`; lần đánh giá này
  cố định pool `allow_repeat` cho cả hai model, không thực hiện lọc ở serving.
- Trọng số blend 0,7 được chọn trên VAL của lần train LightGBM cũ, không chọn lại
  trên TEST chung. Blend là phương pháp phối hợp và được báo riêng với model thuần.
- History policy của candidate pool mở rộng chưa được kiểm chứng độc lập.
  Đây là hạn chế đã có trong run DCN gốc, không bị loại bỏ bởi việc dùng chung pool.
- Không thay checkpoint phục vụ, đường dẫn notebook hay nội dung slide Canva.

## Tái chạy và bằng chứng

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_shared_rankers.py --output training/evaluation/results/shared_dcn_pool_new
```

Thư mục output phải mới để không ghi đè kết quả. Chương trình kiểm tra SHA-256 của
TEST khớp manifest checkpoint DCN và kiểm tra lại các input sau khi chấm. Chấm theo
batch case để hạn chế RAM; các case không có target được giữ trong mẫu số với hit 0.

Kết quả: `training/evaluation/results/shared_dcn_pool_20261012/summary.json`,
`comparison.csv` và `comparison.md`. Các chỉ số DCN tái lập kết quả gốc trong sai
số số thực. Bốn unit test kiểm tra mẫu số chung, batch, case thiếu và nhãn/ứng viên
không hợp lệ đã chạy thành công (`tests.test_shared_rankers`).
