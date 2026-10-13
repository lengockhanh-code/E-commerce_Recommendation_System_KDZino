# Kết quả đánh giá model MerRec ngày 10/10/2026

## Hai benchmark cùng mốc dự đoán

Cùng 5.000 user, history TRAIN + VAL trước tương tác TEST đầu tiên, checkpoint giữ nguyên và candidate pool giữ nguyên. Cho phép tương tác lại item đã xem.

- Next-item: một item TEST đầu tiên/user, tổng 5.000 target.
- Multi-future: mọi item khác nhau/user trong TEST, tổng 61.030 cặp user-item, trung bình 12,21 target/user.

Recall bên dưới là macro, trung bình theo user. Với multi-future, không nhân Recall với tổng target để suy ra số item bắt trúng.

| Model | Next Recall@20 | Next Recall@100 | Future Recall@20 | Future Recall@100 | Future hits@20 | Future hits@100 |
|---|---:|---:|---:|---:|---:|---:|
| Content-Based | 3,64% | 6,28% | 3,09% | 5,31% | 635 | 1.276 |
| Co-visitation | 8,28% | 14,46% | 6,20% | 10,92% | 1.827 | 3.493 |
| ALS | 0,34% | 0,78% | 0,32% | 0,70% | 92 | 305 |
| GRU4Rec | 0,54% | 0,70% | 0,94% | 1,08% | 233 | 252 |
| Two-Tower | 0,18% | 1,10% | 0,23% | 1,01% | 93 | 365 |
| RRF | 6,86% | 11,28% | 5,46% | 9,01% | 1.362 | 2.552 |
| DCN | 6,66% | 12,70% | 5,12% | 9,54% | 1.239 | 2.783 |
| LightGBM thuần | 6,54% | 14,70% | 5,18% | 11,32% | 1.383 | 3.496 |

## Giải thích từng model

- **Content-Based** so khớp biểu diễn nội dung với history. Nó ít phụ thuộc vào việc user khác đã tương tác item, nên có thể bổ sung item chưa có trong TRAIN. Có 117 hit ở top20 thuộc nhóm không xuất hiện TRAIN. Nhưng metadata giống nhau không bảo đảm đúng listing cụ thể; catalog/IDF hiện còn transductive.
- **Co-visitation** dùng quan hệ đồng tương tác và history gần đây. Nó đang bắt trúng nhiều target nhất trong top20, và đóng góp riêng 2.538 hit tương lai ở top100 so với bốn retrieval route còn lại. Kết quả cho thấy quan hệ này hữu ích trên tập hiện tại; không chứng minh nó luôn tốt hơn mạng neural ở mọi dataset.
- **ALS** dùng latent factors collaborative và fold-in history với item factors cố định. Recall thấp trên cả hai benchmark, nên checkpoint hiện tại đóng góp hạn chế. Không thể kết luận nguyên nhân chính là overfit chỉ từ bảng này; cần kiểm tra riêng objective, confidence weights, training và khả năng chọn đúng listing trong catalog lớn.
- **GRU4Rec** dùng chuỗi tương tác để dự đoán item. Artifact đang là epoch8 dù metadata ghi best epoch6; không có checkpoint epoch6 để đối chiếu. Evaluator dùng exact scoring, tránh index32D không tương thích encoder128D. Không bắt được target ngoài TRAIN ở top100. Những hạn chế artifact/output universe này đã được xác nhận; chưa chứng minh chúng giải thích toàn bộ điểm thấp.
- **Two-Tower** hiện dùng user ID embedding tĩnh; history mới không cập nhật user query. Vì vậy chưa tận dụng được thay đổi sở thích gần đây như một user tower có history encoder. Item trong index hiện cố định; nhóm target ngoài TRAIN có 0 hit ở top100. Metadata item không tự biến index cố định thành cold-item retrieval.
- **RRF** hợp nhất thứ hạng nguồn bằng `sum(1/(60+rank))`; không phải model học. Một nguồn yếu có thể làm giảm thứ hạng item tốt từ nguồn mạnh. Ở đây top20 thấp hơn Co-visitation, nên chỉ là baseline, chưa nên mặc định ensemble luôn tăng điểm.
- **DCN** học tương tác giữa features để rerank pool. Top20 thấp hơn RRF, nhưng top100 cao hơn RRF. Model vẫn phân biệt được relevance ở mức tổng thể, song chưa đặt đủ item phù hợp lên đầu danh sách. Nó train trên legacy pool last-interaction, còn benchmark này là pre-TEST multi-future; có thay đổi context và phân phối feature. Learning curve cũ có dấu hiệu overfit; chưa tách được tác động của overfit khỏi distribution shift.
- **LightGBM thuần** tốt nhất Recall@100 ở cả hai benchmark và có AUC/GAUC proxy cao nhất. Tuy nhiên top20 vẫn thua Co-visitation và RRF. Đánh giá này dùng model thuần, không dùng bản blend cũ 17,10% và không chọn blend weight theo TEST.

## Retrieval giới hạn ranker như thế nào

Pool chứa 2.444.585 candidate rows, hợp nhất top100 từ mỗi route, tối đa 500 item/user trước dedup. Pool bắt được 4.547/61.030 target, micro coverage 7,45%. Ranker không thể bắt target nằm ngoài pool.

Đây là micro coverage theo cặp user-item, không phải trần cho macro Recall trong bảng. Hai mẫu số khác nhau.

WARM có 40.479 target/4.431 user; COLD có 20.551 target/3.410 user. Một user có thể thuộc cả hai nhóm. COLD ở đây nghĩa là không xuất hiện trong TRAIN, không nhất thiết hoàn toàn mới với model đã dùng TRAIN+VAL.

## AUC/GAUC trên candidate

| Ranker | AUC proxy | GAUC proxy |
|---|---:|---:|
| RRF | 0,73189 | 0,74612 |
| DCN | 0,78933 | 0,76824 |
| LightGBM | 0,85187 | 0,84663 |

Positive là candidate user tương tác trong tương lai; negative là candidate không quan sát thấy tương tác trong khoảng TEST. Không có log impression đầy đủ, nên đây không phải CTR AUC. GAUC tính trên 2.037 user có cả positive và negative, bỏ 2.963 nhóm một lớp và weight theo số candidate.

## Bảng tham khảo legacy last-item

DCN checkpoint hiện tại từng đạt Recall@20 24,10%, Recall@100 29,27%, NDCG@20 0,15861 trên 4.854 case. Target là tương tác cuối TEST; history có TRAIN + VAL + phần TEST trước target; pool cũ khác pool benchmark chính.

Kết quả này hợp lệ cho bài toán dự đoán một bước với history tại thời điểm đó, nhưng không đặt chung cột để xếp hạng với benchmark pre-TEST. Điểm cao hơn không chứng minh model tốt hơn: checkpoint DCN giữ nguyên.

## File kết quả và kiểm tra

- `training/evaluation/results/pipeline_merrec_20261010/single_next_item_metrics.csv`
- `training/evaluation/results/pipeline_merrec_20261010/metrics.csv`
- `training/evaluation/results/pipeline_merrec_20261010/summary.json`
- `training/evaluation/results/pipeline_merrec_20261010/verification_audit.json`

Đã kiểm tra bằng unit tests, dữ liệu Parquet thật và đối chiếu metric RRF/DCN/LightGBM với SQL độc lập. Giới hạn catalog, artifact, exposure labels và serving được ghi ở [pipeline](RECOMMENDATION_PIPELINE.md). Không kích hoạt model lên website và không retrain trong lần tổng hợp này.
