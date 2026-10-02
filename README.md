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
- `scripts/`: storefront catalog and image persistence used by the website.
- `tests/`: tests for image persistence and local data processing.
- `logs/`: log và PID cũ của quá trình tìm ảnh.

Các module mới có ghi TODO, chưa triển khai nghiệp vụ. Frontend đã có bộ khung Next.js App Router chạy được; xem cách chạy và cấu trúc tại [frontend/README.md](frontend/README.md). Các trang hiện chưa tích hợp nghiệp vụ backend. File dữ liệu processed và artifacts chỉ được tạo khi pipeline tương ứng được triển khai và chạy; không tạo file nhị phân rỗng.

## Script phục vụ website

Frontend gọi `scripts/storefront_catalog.py` để đọc thông tin sản phẩm từ catalog Parquet và tìm ảnh theo nhu cầu. `scripts/storefront_images.py` kiểm tra URL ảnh, lưu kết quả vào SQLite cục bộ và đồng bộ sang PostgreSQL.

Chạy kiểm tra bộ lưu ảnh và đồng bộ các bản ghi đang chờ:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_storefront_images -v
.\.venv\Scripts\python.exe scripts/storefront_catalog.py sync-images
```

Xem cấu trúc lưu trữ và cơ chế đồng bộ tại [database/PRODUCT_IMAGES.md](database/PRODUCT_IMAGES.md). Giữ dữ liệu SQLite khi còn bản ghi đang chờ đồng bộ.

Các script chia CSV và xuất SQL của bộ resolver cũ đã được loại bỏ; website dùng luồng tìm ảnh ở trên.
