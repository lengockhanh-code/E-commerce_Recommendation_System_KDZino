# Đánh giá theo vai trò model — báo cáo Canva ngày 10/10/2026

Bản này mô tả benchmark offline hiện có, không phải kết quả A/B của website. Nội dung đề xuất thay phần báo cáo ở slide 44–50. Không đổi checkpoint, đường dẫn notebook Kaggle hay cấu hình serving.

## Bài toán và dữ liệu

Chốt lịch sử mỗi user **trước tương tác TEST đầu tiên**. Dùng TRAIN + VAL trước mốc đó để gợi ý một danh sách; đối chiếu với mọi item phân biệt user tương tác trong TEST. Cho phép tương tác lại item đã xem. Đây là dự đoán **nhiều item tương lai ở một mốc cố định**, không phải cập nhật lịch sử sau mỗi sự kiện TEST.

- 5.000 user; 61.030 cặp user–item target, trung bình 12,206 target/user.
- Lịch sử: 813.657 sự kiện. Mỗi nguồn retrieval đưa tối đa 100 item; hợp nhất và khử trùng được 2.444.585 candidate.
- Pool có 4.547 target: coverage micro = 4.547 / 61.030 = **7,45%**. Có 2.037 user có target trong pool, 2.963 user không có.
- Không chèn target vào pool, không loại dự đoán sai dựa trên nhãn và không chọn checkpoint theo TEST. Giữ các user không được retrieval bắt trúng trong đánh giá toàn pipeline, với điểm bằng 0.

## Retrieval: đo đóng góp vào pool

| Nguồn | Target bắt được @100 | Target riêng @100 | Hit ngoài TRAIN @100 | HR next-item @20 |
| --- | ---: | ---: | ---: | ---: |
| Content-Based | 1.276 | 519 | 292 | 3,64% |
| Co-visitation | 3.493 | 2.538 | 437 | 8,28% |
| ALS | 305 | 203 | 24 | 0,34% |
| GRU4Rec | 252 | 44 | 0 | 0,54% |
| Two-Tower | 365 | 240 | 0 | 0,18% |

“Target riêng” là số cặp user–item đúng mất khỏi pool nếu bỏ riêng nguồn đó, giữ nguyên output các nguồn khác. Đây là ablation về **membership**, không phải kết quả retrain hay rerank sau khi bỏ nguồn. HR next-item dùng item TEST đầu tiên ở cùng mốc history; là phép đo bổ sung phù hợp với nhiệm vụ dự đoán kế tiếp, vẫn không thay đổi checkpoint để làm đẹp TEST.

- **Co-visitation:** đóng góp riêng lớn nhất; hữu ích cho liên hệ giữa các item trong lịch sử/phiên.
- **Content-Based:** bổ sung 519 target riêng và bắt 292 target ngoài TRAIN; hỗ trợ khai thác metadata. Catalog/IDF có metadata TRAIN + VAL + TEST, nên đây là thiết lập có catalog sẵn, chưa chứng minh cold-start hoàn toàn ở thời điểm triển khai.
- **ALS:** bắt ít target khi chạy riêng nhưng bổ sung 203 target khác các nguồn còn lại. 24 hit ngoài TRAIN vẫn có thể có factors học từ VAL; không gọi đó là item hoàn toàn chưa thấy khi fit.
- **GRU4Rec:** phép đo next-item phản ánh vai trò học chuỗi; kết quả hiện tại còn yếu. File weights là epoch 8, metadata ghi best epoch 6; báo cáo nêu sự lệch này. Scoring chính xác trên catalog TRAIN, không giả định có cold item mới.
- **Two-Tower:** đóng góp 240 target riêng; kiến trúc embedding/ANN có mục tiêu tìm ứng viên nhanh. User query hiện là embedding ID tĩnh, chưa cập nhật bằng lịch sử inference; index TRAIN cố định. Chưa đo latency cùng phần cứng, không tuyên bố tốc độ thực nghiệm.

Catalog khả dụng của các nguồn khác nhau. Các số trên phản ánh đóng góp của artifact đang có trong pipeline, chưa phải so sánh kiến trúc với catalog, dữ liệu train và ngân sách compute đồng nhất.

## Ranker: đo thứ tự trên cùng pool

Chỉ đổi thứ tự candidate của cùng pool, dùng đúng checkpoint hiện có. Nhãn phù hợp để đánh giá riêng khả năng rerank là **target đã có trong pool**. Chỉ có 2.037 user đủ nhãn cho phép đo này.

| Phương thức | Giữ target pool @20 | Giữ target pool @100 | NDCG pool @20 | NDCG pool @100 | GAUC proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| RRF | 29,95% | 56,12% | 0,2149 | 0,2706 | 0,7461 |
| DCN numeric | 17,62% | 59,82% | 0,1251 | 0,2086 | 0,7900 |
| LightGBM | 30,42% | 76,89% | 0,1921 | 0,2887 | 0,8466 |

“Giữ target” là recall micro: tổng hit chia **4.547 target trong pool**. Ví dụ DCN @100 = 2.720 / 4.547 = 59,82%; không phải 59,82% sản phẩm gợi ý đúng. NDCG là trung bình/user, nhãn nhị phân, IDCG dựa trên số target có trong pool của chính user. GAUC dùng trọng số số candidate/user, bỏ user chỉ có một lớp nhãn; nhãn không tương tác trong TEST là proxy negative, không phải impression negative hay CTR.

**DCN:** giữ được nhiều target vào top100 hơn RRF (2.720 so với 2.552), nhưng đầu danh sách kém hơn: NDCG@20 0,1251 so với 0,2149. GAUC cao hơn chỉ chứng minh thứ tự tổng thể giữa positive/negative tốt hơn theo proxy này; không bảo đảm top20 tốt. Không nên tuyên bố DCN tốt nhất.

**LightGBM:** giữ nhiều target nhất ở top100 (3.496), nhưng NDCG@20 vẫn thấp hơn RRF. RRF đưa các hit lên vị trí đầu hiệu quả hơn ở phép đo NDCG@20 này. Tác dụng và lựa chọn ranker phụ thuộc độ sâu danh sách mà ứng dụng dùng.

## Vì sao điểm toàn pipeline thấp hơn điểm ranker?

Retrieval đã bỏ sót 92,55% target tương lai, nên ranker không có khả năng kéo các target đó vào danh sách. Ở top20, DCN toàn pipeline có recall trung bình/user **3,43%**; recall micro = 801 / 61.030 = **1,31%**. Đây là hai mẫu số/cách tổng hợp khác nhau, không được đổi qua lại để so điểm đẹp hơn. Điểm ranker trong pool cũng không thay thế chất lượng toàn pipeline.

Ranker được train theo một target cuối/case, trong khi benchmark này chốt history trước TEST và dùng nhiều target tương lai. Lệch nhiệm vụ và ngữ cảnh có thể ảnh hưởng kết quả, nhưng chưa có ablation riêng để xác định mức ảnh hưởng. Không suy ra overfit chỉ từ best epoch 1 hay số phút train.

DCN numeric: 24 feature số; Cross 1 + MLP 32–16; 1.513 tham số; dropout 0,5; input clip [-5,5]; AdamW lr 0,0001, weight decay 0,01. Train 30.000 case, 12.003 case có positive trong candidate, 6.001.500 dòng với tối đa 499 hard negative/case. Dừng ở epoch 2, chọn epoch 1 theo VAL NDCG@20. Đây là biến thể numeric hiện tại, không đại diện đầy đủ DCN gốc có embedding feature.

PURCHASE chỉ có 40 target; nhãn benchmark chính gồm nhiều loại tương tác. Chưa có đủ bằng chứng để kết luận hiệu quả mua hàng, CTR hay CVR. Chưa đo A/B hoặc latency đồng nhất.

## Phạm vi demo và hướng cải thiện

Demo có routing theo lịch sử/phiên, rules/hybrid và tùy chọn ranker qua cấu hình. Benchmark DCN/LightGBM thuần không chứng minh mọi request demo dùng các model này; cấu hình DCN serving còn blend với baseline. Lần đánh giá này không kích hoạt checkpoint mới cho serving.

Ưu tiên tăng coverage bằng candidate budget/nguồn phù hợp; đo trên VAL trước, chốt cấu hình rồi mới đánh giá TEST mới. Train ranker đúng mốc cắt inference và nhiều target/case. Bổ sung user tower nhận history và cập nhật item index; kiểm tra metadata checkpoint GRU. Sau đó làm ablation rerank, đo latency/coverage trên cùng máy và đo online nếu có dữ liệu impression.

## Tái lập và kiểm chứng

Nguồn frozen predictions: `training/evaluation/results/pipeline_multifuture_numeric_20261010/`. Báo cáo theo vai trò: `training/evaluation/results/model_roles_canva_20261010/summary.json`, `retrieval_roles.csv`, `ranker_metrics.csv`. Script kiểm tra fingerprint checkpoint/cache trước và sau khi đọc, đối chiếu độc lập bằng DuckDB SQL cho recall/NDCG ranker và hit/đóng góp riêng/hit ngoài TRAIN của retrieval. Không train lại trong lần kiểm chứng này.

```powershell
.\.venv\Scripts\python.exe -m scripts.report_pipeline_roles --output training/evaluation/results/model_roles_recheck
.\.venv\Scripts\python.exe -m unittest tests.test_recommendation_pipeline tests.test_future_items_evaluation -q
```

Định nghĩa NDCG tham khảo [tài liệu chính thức scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html). Khác biệt giữa đánh giá ranking offline và CTR/online phải được giữ rõ; không so trực tiếp các số trong báo cáo này với kết quả DCN gốc trên dữ liệu click.
