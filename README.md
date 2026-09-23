# MerRec

## Notebook EDA local bằng DuckDB

Mở `training/eda_local_merrec_professional.ipynb`, chọn kernel `.venv`, **Restart Kernel** rồi **Run All**. Notebook này dùng DuckDB trực tiếp, không cần Java/Spark. Các thư viện nằm trong `requirements.txt`.

Cell đầu cấu hình `DATA_PATH` (mặc định `data/raw/20230501`) và `ARTIFACT_DIR` (mặc định `artifacts/eda_local`). Thống kê chạy trong DuckDB, chỉ chuyển bảng tổng hợp hoặc mẫu có giới hạn sang Pandas. Kết quả gồm CSV, PNG, `eda_insights.txt` và `eda_summary.json`. Phân tích thời gian dùng UTC. Các cột bắt buộc là `user_id`, `item_id`, `event_id`, `stime`; các phân tích phụ được bỏ qua khi thiếu dữ liệu phù hợp.

Chạy kiểm thử toàn bộ cell trên mẫu Parquet thật và dữ liệu biên:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_local_eda -v
```

## Môi trường chạy notebook EDA

Cài thư viện từ thư mục gốc bằng Python của môi trường ảo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Mở `training/eda.ipynb` trong VS Code, chọn **Select Kernel → Python Environments → .venv** (`D:\MerRec\.venv\Scripts\python.exe`), rồi **Restart Kernel** và chạy các cell từ đầu.

Requirements bao gồm Pandas, Matplotlib, PySpark, PyArrow và ipykernel. Spark cần JDK 21 đầy đủ: cài Eclipse Temurin rồi đặt `JAVA_HOME`, hoặc giải nén JDK vào `.cache/java21/` sao cho có `.cache/java21/bin/java.exe`. Khi chạy local trên Windows mà chưa đặt `JAVA_HOME`, notebook tự dùng JDK trong thư mục này. Spark workers dùng cùng Python với kernel. Dữ liệu đầu vào nằm tại `data/raw/20230501/*.parquet`; kết quả EDA ghi vào `artifacts/eda/`.

## Cấu trúc

- `data/raw/20230501/`: dữ liệu parquet gốc.
- `data/catalog/`: catalog CSV, các phần CSV, SQL ảnh và SQLite checkpoint.
- `data/processed/`: đầu ra preprocessing (interactions, users, items, train, val, test).
- `training/`: khung preprocessing, huấn luyện, đánh giá, models và utils.
- `artifacts/`: đầu ra huấn luyện: model.pt, item_mapping.pkl, user_mapping.pkl, config.json, metrics.json.
- `backend/`: khung API, services, ML inference và database.
- `frontend/`: khung giao diện và API client.
- `database/`: schema, seed, migrations và bản sao SQL ảnh để import.
- `scripts/`: các script xử lý catalog và bộ `merrec_image_resolver` hiện có.
- `tests/`: kiểm thử, bao gồm hai test resolver đang hoạt động.
- `logs/`: log và PID cũ của quá trình tìm ảnh.

Các module mới có ghi TODO, chưa triển khai nghiệp vụ. Frontend đã có bộ khung Next.js App Router chạy được; xem cách chạy và cấu trúc tại [frontend/README.md](frontend/README.md). Các trang hiện chưa tích hợp nghiệp vụ backend. File dữ liệu processed và artifacts chỉ được tạo khi pipeline tương ứng được triển khai và chạy; không tạo file nhị phân rỗng.

## Chạy từ thư mục gốc

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/split_csv.py
.\.venv\Scripts\python.exe scripts/resolve_images_to_sql.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Hai script dùng đường dẫn mặc định dựa trên vị trí file, không phụ thuộc thư mục làm việc. Resolver cũng hỗ trợ `python -m scripts.resolve_images_to_sql` và các tùy chọn `--input-dir`, `--db`, `--sql`.

`data/catalog/product_images.sql` là đầu ra resolver. `database/product_images.sql` là bản sao tại thời điểm sắp xếp thư mục. Sau khi cập nhật ảnh, đồng bộ trước khi import:

```powershell
Copy-Item data/catalog/product_images.sql database/product_images.sql
```

Xem hướng dẫn bộ resolver tại [scripts/merrec_image_resolver/README_VI.md](scripts/merrec_image_resolver/README_VI.md).
