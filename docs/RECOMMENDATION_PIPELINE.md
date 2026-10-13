# Pipeline recommendation MerRec

Tham khảo cách tổ chức benchmark của Shopee, áp dụng vào bài toán và dữ liệu MerRec.
Không phải bản sao hệ thống production Shopee.

## Nguồn và cách áp dụng

- [LightSAGE, mục 3.1](https://arxiv.org/html/2310.19394): retrieval đối chiếu với click những ngày sau, đóng góp riêng của từng nguồn, long-tail.
- [OnePiece, mục 4.1 và Appendix A](https://arxiv.org/html/2509.18091): đánh giá theo thứ tự thời gian; retrieval Recall@100/@500, ranking AUC/GAUC cho click/cart/order.
- MerRec hiện thiếu log impression đầy đủ và ngữ cảnh request/search của Shopee. Benchmark chính dùng tất cả item tương tác tương lai; PURCHASE/POSITIVE được báo riêng. AUC/GAUC ở đây chỉ là proxy phân biệt item tương lai với candidate không được quan sát tương tác, không phải CTR/CVR.

## Giao thức chính

1. Cohort cố định 5.000 user. Cutoff là tương tác TEST đầu tiên mỗi user.
2. History chỉ TRAIN + VAL, timestamp nhỏ hơn cutoff; không dùng TEST tạo query.
3. Retrieval giữ các checkpoint hiện có, chấm điểm trên toàn catalog/index. Cache top100 được xác minh artifact, cohort, thứ tự user và mapping score/item.
4. Ground truth là mọi cặp `(user_id,item_id)` khác nhau trong TEST sau cutoff: 61.030 target. Không có giới hạn 20 target/user.
5. Cho phép tương tác lại item đã xem (`allow_repeat`). Không chèn target vào candidate.
6. Hợp nhất top100 từ 5 nguồn, tối đa 500 item/user trước dedup. Tạo features bằng metadata catalog và popularity TRAIN. DCN, LightGBM và RRF xếp hạng cùng pool.
7. Báo số item bắt trúng, macro Recall, micro Recall, NDCG @20/50/100, đóng góp riêng của từng nguồn, WARM/COLD/POSITIVE/PURCHASE. AUC/GAUC proxy có mẫu số eligible rõ ràng.

Macro Recall là trung bình Recall từng user. Micro Recall là tổng cặp user-item bắt trúng / tổng target. Không nhân macro Recall với số target để suy ra hit count.

Benchmark xuất thêm `single_next_item_metrics.csv`: dự đoán item TEST đầu tiên trên cùng history, checkpoint và candidate pool với benchmark nhiều item. Đây là cách đối chiếu hai kiểu target công bằng. Kết quả DCN cũ 24,10% dùng target cuối TEST/history có TEST trước target nên chỉ được ghi ở bảng tham khảo riêng.

## Chạy

Tại `D:\MerRec`:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.evaluate_recommendation_pipeline --output training/evaluation/results/pipeline_new_run
.\.venv\Scripts\python.exe -m unittest tests.test_recommendation_pipeline tests.test_future_items_evaluation tests.test_dcn_ranker tests.test_lightgbm_ranker -v
```

Thư mục output phải mới. Dùng `--dcn`, `--lightgbm`, `--retrieval-cache` để chọn artifact khác. Cache chỉ được dùng nếu cùng history/cohort/artifact; không tự thay bằng dữ liệu demo.

## Giữ file nào

- `training/models/`: notebook huấn luyện model.
- `scripts/train_dcn_ranker.py`, `train_lightgbm_ranker.py`: trainer và encoder được notebook/evaluator gọi.
- `scripts/candidate_case_builder.py`, `export_all_candidate_datasets.py`, `build_ranker_datasets.py`: pipeline candidate cho ranker.
- `training/evaluation/`: adapter inference, tạo cohort, metrics và benchmark.
- `scripts/evaluate_recommendation_pipeline.py`: entry point benchmark chung.
- `scripts/online_models.py`, `personalized_recommendations.py`, API/backend/frontend: phục vụ website; giữ nguyên trong lần sửa benchmark này.
- Checkpoint, dataset, index, mappings và báo cáo cũ: giữ để đối chiếu, không xóa.

## Giới hạn phải giữ trong báo cáo

- Đây là snapshot trước TEST đánh giá trên cả khoảng TEST, chưa phải incremental training từng ngày như OnePiece. Không đổi target thành leave-last rồi gọi cùng protocol.
- Content catalog/IDF hiện dùng metadata toàn catalog, gồm VAL/TEST: đánh giá transductive, chưa chứng minh availability theo thời điểm.
- DCN/LightGBM hiện train trên pool last-interaction cũ, nên có thay đổi phân phối khi dùng pool tương lai mới. Không coi điểm next-item 4.854 target là điểm multi-future 61.030 target.
- GRU checkpoint epoch8 được giữ dù metadata ghi best epoch6; scoring exact tránh index 32D không phù hợp encoder128D. Two-Tower hiện là user embedding tĩnh.
- Chưa có top500 từng nguồn, bảng tần suất toàn bộ item TRAIN cho long-tail percentile, hay online A/B test. Không báo các metric ấy bằng số tự suy đoán.
- Sửa fallback offline dùng TRAIN-only chỉ có tác dụng với exports mới; exports/checkpoint cũ không tự được sửa nguồn dữ liệu.
- Policy online đang có bộ lọc riêng; benchmark này không kích hoạt checkpoint mới lên website và không chứng minh offline/online parity.

## Dọn file thử nghiệm ngày 10/10/2026

Đã kiểm tra caller, tài liệu, notebook và Git history trước khi xóa:

- `scratch/check_splits.py`, `generate_audit.py`, `read_lgb_nb.py`, `set_env_ranker.py`, `test_online_lightgbm.py`: kiểm tra/ad hoc config dùng một lần.
- `scripts/update_notebooks_export.py`: bộ chèn cell đã chạy; notebook hiện có giữ nguyên.
- `scripts/expand_val_retrieval.py`, `audit_candidate_retrieval.py`: thử nghiệm retrieval VAL cũ.
- `scripts/evaluate_dcn_future_items.py`, `tests/test_dcn_future_items.py`: evaluator neo ở last-TEST, không tạo benchmark multi-future; thay bằng entry point và test pipeline chung.

Giữ các báo cáo thử nghiệm cũ để đối chiếu. Không xóa dataset, checkpoint, index, mappings hay thư mục serving.
