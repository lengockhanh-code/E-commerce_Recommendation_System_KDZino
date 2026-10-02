# MerRec End-to-End System Status & Plan

> **Trạng thái:** Đã hoàn thiện sẵn sàng cho Model Trained & PostgreSQL Sync  
> **Ngày cập nhật:** 2026-09-26  
> **Repository Root:** `D:\MerRec`

---

## 1. Kiểm kê Chức năng & Kết quả Triển khai (Inventory & Implementation)

| Chức năng / Luồng | Trạng thái hiện tại | Chi tiết giải pháp đã triển khai |
|---|---|---|
| **Catalog Metadata** | Đã sẵn sàng PostgreSQL + Parquet | - Script `scripts/sync_catalog_to_postgres.py` hỗ trợ upsert idempotent theo batch.<br>- Migration SQL `database/migrations/001_initial_schema_and_constraints.sql` tạo schema an toàn.<br>- `scripts/storefront_catalog.py` đọc từ PostgreSQL khi có `DATABASE_URL`, trả lỗi safe error 503 khi DB gián đoạn. |
| **Image Resolution & Storage** | Đã hoàn thiện & bảo vệ DB | - `scripts/storefront_images.py` xác minh ảnh công khai HTTPS (SSRF check, public IP, image size/dimension valid).<br>- Unique index `(item_id, image_url)` trong PostgreSQL ngăn trùng.<br>- SQLite outbox `data/storefront/product_images.sqlite3` đảm bảo mất kết nối DB không làm mất kết quả ảnh. |
| **Recommendation Engine** | Đã triển khai động & Sẵn sàng cho Trained Model | - `scripts/recommendation_engine.py` + API `/api/recommendations`.<br>- Tự động ghi nhận `recommendation_requests` và `recommendation_items` trong PostgreSQL.<br>- Hỗ trợ các phương pháp: `metadata_similarity_v1`, `overall_popular_v1`, và giao diện động `trained_model_v1` khi người dùng train xong model.<br>- Component UI `RecommendationStrip` chuẩn phong cách Shopee ở Home, Product Detail, Cart. |
| **User Interactions & Tracking** | Đã hoàn thiện | - API `/api/events` ghi nhận các sự kiện `view`, `like`, `cart`, `buy_comp` vào bảng `user_events` trong PostgreSQL.<br>- Liên kết được click từ recommendation với `recommendation_request_id` và vị trí `position`. |
| **Cart & Order Flow** | Đã hoàn thiện persistence | - Cart client-side kết hợp API `/api/orders` lưu đơn hàng thực tế vào bảng `orders` và `order_items` trong PostgreSQL. |
| **Authentication & Profile** | Mock minh bạch | Giữ đúng scope, hiển thị thông báo minh bạch khi mock UI. |

---

## 2. Tiến độ Thực hiện (Progress Tracking)

- [x] **Bước 1:** Kiểm kê repository & lập tài liệu `docs/end-to-end-status.md`.
- [x] **Bước 2:** Xây dựng migration database (`database/migrations/001_initial_schema_and_constraints.sql`) & script đồng bộ catalog parquet vào PostgreSQL (`scripts/sync_catalog_to_postgres.py`).
- [x] **Bước 3:** Chuyển đổi `scripts/storefront_catalog.py` & `frontend/src/lib/catalog-server.ts` đọc từ PostgreSQL với safe error handling.
- [x] **Bước 4:** Bổ sung unique constraint `(item_id, image_url)` cho `product_images` và bảo toàn SQLite outbox.
- [x] **Bước 5:** Xây dựng Recommendation Engine (`scripts/recommendation_engine.py`) + API `/api/recommendations` + lưu vết request/items + sẵn sàng kết nối trained model.
- [x] **Bước 6:** Xây dựng API tracking `/api/events` & API đơn hàng `/api/orders`.
- [x] **Bước 7:** Triển khai `RecommendationStrip` chuẩn phong cách Shopee ở Home ("✨ Gợi ý dành riêng cho bạn"), Product Detail ("Sản phẩm tương tự"), và Cart ("Có thể bạn cũng thích").
- [x] **Bước 8:** Chạy đầy đủ verification gates theo `AGENTS.md` (typecheck, lint, Python unittests, build optimization).

---

## 3. Lệnh Kiểm chứng đã chạy & Kết quả (Verification Evidence)

1. **Python Unittests:**
   - `.\.venv\Scripts\python.exe -m unittest tests.test_storefront_images -v` (OK)
   - `.\.venv\Scripts\python.exe -m unittest tests.test_catalog_and_recommendation -v` (OK)

2. **Frontend Typecheck & Linting:**
   - `npm run typecheck` (0 errors)
   - `npm run lint` (0 errors)

3. **Production Build:**
   - `npm run build` (Build thành công 19/19 static & dynamic routes).
