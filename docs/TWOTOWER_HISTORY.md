# Two-Tower nhận lịch sử người dùng

## Bài toán đang làm

Tại một thời điểm, biết các sản phẩm user đã tương tác trước đó, hệ thống trả về danh sách sản phẩm họ có thể tương tác tiếp. Tương tác lại sản phẩm đã xem vẫn được tính đúng.

Ví dụ: trước thời điểm dự đoán, user đã xem A, B, C. Hệ thống đề xuất D, B, E. Sau đó user tương tác B, F, D:

- **Next item:** tương tác kế tiếp là B. Kiểm tra B có nằm trong top K và đứng ở vị trí nào.
- **Nhiều item tương lai:** tập đúng là {B, F, D}. Danh sách trên bắt được 2/3 sản phẩm, nên Recall@3 = 66,67% cho user này.

Hai cách chấm có thể cùng dùng để báo cáo, nhưng phải ghi rõ target, thời điểm lấy lịch sử, số user và candidate pool. Không so trực tiếp hai con số từ hai giao thức khác nhau.

## Notebook mới xử lý thế nào

Notebook: `training/models/05_two_tower.ipynb`. Giữ nguyên các đường dẫn Kaggle và đường dẫn artifact đã có.

1. Đọc tương tác **TRAIN có timestamp**, thay vì chỉ lấy cặp user–item đã gộp trong CF.
2. Mỗi mẫu train: tối đa 20 tương tác xảy ra **trước timestamp của target** → item tại timestamp đó. Các sự kiện cùng timestamp không trở thành lịch sử của nhau. Lịch sử giữ cả lần tương tác lặp lại.
3. User tower kết hợp embedding user ID với vector lịch sử. Các item lịch sử đi qua item tower dùng chung trọng số; lấy trung bình có trọng số, tương tác mới có trọng số lớn hơn (`history_decay=0.9`). MLP kết hợp hai vector, rồi chuẩn hóa L2.
4. Item tower vẫn dùng metadata đã hash, giá log + z-score và MLP. Train bằng InfoNCE với negative trong batch. Dropout toàn lịch sử trên một phần mẫu giúp model có thể xử lý user đã biết nhưng chưa truyền history.
5. **VAL:** lịch sử TRAIN trước tương tác VAL đầu tiên. Chọn checkpoint theo ALL NDCG@20 trong candidate pool lấy mẫu; đây không phải full-catalog validation. Sau đó báo cáo riêng VAL với full index.
6. **TEST:** lịch sử TRAIN+VAL trước tương tác TEST đầu tiên, không đưa TEST vào history. Target là các item khác nhau trong TEST; item ngoài TRAIN universe vẫn nằm trong mẫu số Recall và NDCG. Không loại sản phẩm đã xem khỏi gợi ý. Chấm bằng full FAISS index, tức ANN thay vì tìm kiếm exact.

User ngoài mapping vẫn dùng được nếu lịch sử có item thuộc TRAIN universe. Nếu cả user và toàn bộ history đều chưa biết, cần nguồn dự phòng. Thay đổi này chưa giải quyết việc truy hồi item mới ngoài TRAIN item universe.

## Truyền lịch sử vào notebook

Sau khi train và tạo index, chạy:

```python
recommend_user(
    user_id="USER_ID_THAT",
    history_item_ids=["ITEM_CU_NHAT", "ITEM_TIEP_THEO", "ITEM_MOI_NHAT"],
    k=20,
)
```

Truyền **item_id gốc**, không phải item_idx. Danh sách từ cũ đến mới; chỉ đưa tương tác đã xảy ra trước lúc cần gợi ý. Hàm trả về `item_id`, `score`, `rank`. Hàm tự ánh xạ ID và lấy tối đa `CFG['history_length']` item đã biết gần nhất. Điểm là độ tương đồng, không phải xác suất mua hàng.

## Train và dùng artifact

- Trên Kaggle, dùng phiên bản notebook đã sửa và Run All. Thời gian tạo dữ liệu lịch sử và train phụ thuộc toàn bộ dữ liệu TRAIN; không có kết quả mới chỉ bằng việc sửa code.
- Checkpoint ID-only cũ không thể resume sang kiến trúc mới. Notebook giữ bản sao checkpoint cũ và bắt đầu v2; checkpoint v2 chỉ resume khi config và dữ liệu khớp.
- Các cell đánh giá và export local được tách nhánh để Kaggle không import thư mục `D:\MerRec`.
- ZIP giữ tên cũ, bổ sung `features/*.npy` và module inference `twotower_history.py`. Các feature này cần để mã hóa lịch sử với đúng metadata đã dùng lúc train, nên ZIP sẽ lớn hơn.
- Khi đưa ZIP mới về local, cần dùng cùng bộ checkpoint, index, mappings và features. Không trộn model mới với index cũ.
- Các adapter đánh giá, export candidate và demo đã nhận history cho checkpoint mới. Với checkpoint cũ, chúng vẫn dùng embedding user ID như trước. Sửa code không biến checkpoint cũ thành model đã học lịch sử.

Kiểm thử local chạy các cell tạo dữ liệu, train, chọn checkpoint, full-index đánh giá, đóng ZIP, nạp lại và gọi adapter demo trên fixture nhỏ. Chưa chạy full dataset Kaggle hay đo mức tăng Recall của model mới.
