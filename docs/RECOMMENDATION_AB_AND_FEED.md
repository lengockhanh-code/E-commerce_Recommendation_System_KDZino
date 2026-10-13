# Feed cuộn tự tải và A/B DCN–LightGBM

Trang chủ tự tải trang gợi ý tiếp theo khi cuộn gần cuối danh sách, hiển thị spinner,
giữ sản phẩm đã tải khi lỗi và có nút thử lại. Không có nút tải thêm trong luồng bình
thường. Chi tiết và giỏ hàng giữ luồng riêng. Tính năng mô phỏng kiểu duyệt feed;
không tuyên bố tái tạo thuật toán hay hạ tầng nội bộ Shopee.
Mỗi đợt chỉ nối một trang khi người dùng cuộn xuống tới vùng tải. Spinner hiện
ít nhất 450ms trước khi nối sản phẩm; không tự tải dây chuyền khi đứng yên.

## Lịch sử ngắn hạn qua nhiều phiên

GRU được xét khi có ít nhất 3 item khác nhau trong lịch sử tương tác 7 ngày gần
nhất (tối đa 100 sự kiện gần nhất), không yêu cầu tương tác lại trong phiên mới.
Chuỗi đưa vào model theo thứ tự thời gian; impression và unlike không kích hoạt
GRU. Trường `session_distinct_count` vẫn mô tả phiên hiện tại, còn
`recent_distinct_count` quyết định khả năng dùng GRU. Nhãn API `session` chỉ nhóm
có lịch sử chuỗi gần đây, không có nghĩa toàn bộ chuỗi thuộc phiên đang mở.
PostgreSQL local dùng Asia/Bangkok (UTC+7): timestamp aware được chuyển bằng
`astimezone(UTC)` để giữ nguyên thời điểm, không ghi đè nhãn bằng `replace`.
Event/request mới dùng datetime UTC có timezone; không thay timezone DB hoặc
dịch thời gian các row lịch sử. TTL và điều kiện history mới dùng cùng UTC.
API view → PostgreSQL UTC+7 → feed mới với catalog/model thật đã được kiểm tra
trong transaction rollback: thời điểm đúng và request ID của đợt tiếp theo thay
đổi khi có tương tác mới. Kết quả ở
`training/evaluation/results/postgres_interest_refresh_probe_20261012.json`.

Tài khoản dùng lịch sử theo user ID. Khách dùng cùng cookie định danh trình duyệt
để nối lịch sử các session đã lưu; không lấy event của tài khoản hoặc khách khác.
Xóa cookie/chuyển trình duyệt không nhận lại lịch sử khách cũ. Có lịch sử đủ điều
kiện chưa bảo đảm GRU trả điểm: checkpoint và item mapping phải khớp item đã xem;
trạng thái `unmapped_history`/`missing_artifact` được trả rõ khi không dùng được.

## Gợi ý và phân nhóm

Luồng phục vụ hiện tại tách các tín hiệu thay vì thay toàn bộ lịch sử bằng phiên:

| Tín hiệu | Dữ liệu và tác dụng |
| --- | --- |
| Quan tâm gần đây | Metadata của item trong 7 ngày gần nhất, suy giảm theo `exp(-age_hours/24)`; view/click 1, like 2.5, cart 3, mua hoàn thành 4. Click + view lặp của cùng item không tạo hai bằng chứng độc lập. |
| Sở thích lâu dài | Tối đa 100 tương tác đã lưu, kể cả ngoài 7 ngày; profile metadata suy giảm theo `exp(-age_hours/720)`, đồng thời truyền toàn bộ history cho ALS/Two-Tower. |
| GRU | Chỉ nhận chuỗi `recent_history` có thứ tự thời gian; không thay history dài hơn của model khác. |
| Content/co-visitation | Liên quan nội dung và quan hệ cùng tương tác trong pool giới hạn. |
| ALS/Two-Tower | Dùng khi đủ history và artifact/mapping tương thích; có ít nhất 10 item thì bật nhánh long-term cho cả tài khoản/khách có định danh ổn định. Two-Tower cũng được xét khi đủ 3 item gần đây. |
| DCN hoặc LightGBM | Nhóm A/B nhận cùng pool/features và policy; kết hợp 70% điểm ranker với 30% hybrid. |

Two-Tower ANN lấy tối đa 300 hit, map item_idx về item_id và lấy metadata thật
từ catalog để thêm vào union, rồi loại history/item đã cấp. Không chỉ chấm điểm
giao giữa ANN với một pool content sẵn có (cách cũ có thể cho 0 hit). Cache điểm
ANN trong cùng worker để không load model/index hai lần. GRU/ALS chấm điểm trên
pool đã hợp nhất; nguồn không khả dụng được báo đúng trạng thái.

Với checkpoint Two-Tower cũ, user trong TRAIN giữ query từ user tower đã học.
User mới có item history trong TRAIN dùng `history_item_pool`: khôi phục vector
item từ index hiện có, pooling theo độ mới/cường độ hành động và chuẩn hóa để
ANN tìm ứng viên. DirectMap chỉ tạo trong RAM, không ghi đè index/checkpoint.
Đây là fallback phục vụ bằng item tower, không phải user tower đã được train
nhận history. Checkpoint history-aware mới sẽ dùng `trained_history_tower`.
`retrieval_modes` phân biệt các nhánh; item chưa có mapping không được giả vector.
Probe user ngoài TRAIN với item history có mapping đã lấy được 300 ANN hit,
mode `history_item_pool`, khoảng 2,48s trên index thật; không ghi DB hoặc sửa index.

Hybrid ưu tiên gần đây, vẫn giữ phần lịch sử dài hơn. Ví dụ người có cả hai:
recent metadata .32, long metadata .14, GRU .14, co-vis .12, content .10,
Two-Tower .10, ALS .05, freshness .03. Nguồn không trả được điểm bị bỏ và các
trọng số còn lại được chuẩn hóa lại. Đây là policy heuristic của MerRec, chưa
phải trọng số được tối ưu bằng A/B và không phải công thức nội bộ Shopee.

Khi tối thiểu 2 item gần đây có một nhóm metadata chiếm ít nhất 65% trọng số,
rerank ưu tiên nhóm đó: mỗi 12 item có tối đa 9 vị trí ưu tiên và 3 khám phá nếu
hai phía đều đủ ứng viên. Chọn model score tốt nhất trong mỗi phía, giảm penalty
đổi ngành hàng. Không ép mỗi ngành chỉ 4 item khi quan tâm đã rõ. Nếu tín hiệu
mâu thuẫn hoặc không còn item cùng nhóm, dùng ranking/diversity thông thường.
Quota này là lựa chọn UX cần đánh giá, không phải Recall hay độ chính xác.

Đối chiếu nguồn công khai: [LightSAGE của Shopee](https://arxiv.org/abs/2310.19394)
mô tả retrieval từ hành vi mạnh, CF và vector search trong quảng cáo;
[ResFlow](https://arxiv.org/abs/2411.09705) mô tả kết hợp nhiều loại phản hồi ở
pre-rank Shopee Search. Những bài này không công bố toàn bộ thuật toán homepage.

- A: DCN numeric epoch 1 (`numeric_earlystop_20261010`).
- B: LightGBM checkpoint hiện có (6 cây).
- Mỗi nhóm dùng 70% điểm model sau chuẩn hóa thứ hạng và 30% hybrid, cùng logic
  retrieval/filter/diversity. Không đổi biến môi trường theo request.
- SHA-256 theo experiment ID và user ID chia bucket 50/50, cố định cho tài khoản.
  Khách dùng cookie HTTP-only ẩn danh ổn định; session mới vẫn nhận cùng nhóm.
  Khách và tài khoản là các đơn vị nhận dạng khác nhau khi đăng nhập.
- Chỉ chạy A/B ở home. Khi model được chỉ định không khả dụng, trả lỗi có thể thử
  lại; không thay model bằng rules rồi tính vào kết quả experiment.
- `MERREC_AB_ENABLED=1` đã được bật trong cấu hình local. `.env.example` mặc định
  bằng 0. Policy mới dùng `dcn_lightgbm_home_v2_interest`, không gộp số liệu với v1.
  Cursor của experiment cũ trả 410 để tải feed mới sau khi đổi cấu hình.
- Backend/frontend đang chạy cần restart để nhận code và cấu hình.

## Phân trang và persistence

Backend sinh và lưu snapshot tối đa 240 sản phẩm vào `recommendation_requests` và
`recommendation_items` có sẵn. Mỗi lượt tải lấy 12 sản phẩm theo cursor request ID
và vị trí. Trang tiếp theo đọc snapshot nếu không có tương tác mới. Nếu history
có view/click/like/cart mới sau thời điểm sinh block, backend tạo block mới cho
đợt tiếp theo, giữ sản phẩm cũ, cùng nhóm A/B và loại item đã cấp. Phần đuôi
chưa trả cho client của block cũ được bỏ trong cùng transaction để không loại
nhầm item chưa hiển thị khỏi lượt retrieval mới; mọi rank đã trả hoặc có event
đã ghi nhận đều được giữ. Worker lỗi thì rollback và giữ block cũ. Retry dùng
cùng block đã tạo. Chỉ chủ sở hữu/phiên
tương ứng đọc được cursor; cursor sai trả 422, khác chủ trả 403, quá 6 giờ trả 410.
Item đã ngừng hoạt động được bỏ qua. Hết một snapshot, cursor chuyển sang lượt
retrieval và xếp hạng mới, giữ nguyên nhóm A/B, lấy history mới nhất và loại mọi
item đã cấp ở các snapshot trước. 240 là kích thước xử lý mỗi lượt, không phải
giới hạn tổng số sản phẩm trong bảng tin. Chỉ kết thúc khi lượt mới trả rỗng.
Mỗi block tiếp nối có ID xác định từ request gốc; retry đọc cùng dữ liệu đã lưu.
Khóa request gốc trong PostgreSQL tránh sinh hai block khi tải đồng thời. TTL
tính từ request gốc. Không thêm bảng/cột; mỗi card giữ request ID và vị trí của
block riêng để attribution chính xác.
Nếu pool cá nhân hóa không còn sản phẩm chưa cấp, nguồn khám phá bổ sung tối đa
300 sản phẩm hợp lệ chưa cấp từ catalog, ưu tiên độ mới. Sở thích ở trang chủ là
tín hiệu ưu tiên, không phải bộ lọc cứng khiến feed cạn khi hết một ngành hàng.

Experiment được lưu dưới dạng tag `exp:<id>:<A|B>:<ranker>` trong model_name của
request. Nhận dạng guest được lưu trong source của user_session. Các trường đều
đã có trong PostgreSQL; không thêm cột. Migration 004 đã được người dùng duyệt và
áp dụng để mở rộng `chk_event_type` cho impression, giữ các event type cũ và dữ liệu.
Đã kiểm tra migration trên bảng TEMP PostgreSQL trước khi áp dụng; không có
startup migration hoặc chuyển lượt hiển thị thành view để lách constraint.

## Ghi nhận và đánh giá

Impression được ghi khi ít nhất 50% card xuất hiện liên tục một giây ở tab đang
hiển thị, hoặc ngay khi người dùng nhấp link sản phẩm. Yêu thích/thêm giỏ không
bị tính thành link click. Impression không đi vào history/popularity/trending.

Mỗi `(request, item)` chỉ có một impression nhờ UUID idempotency do server tạo.
Server kiểm tra sở hữu request, item thực sự thuộc danh sách và đúng vị trí;
nhóm experiment lấy từ DB, không tin metadata gửi từ browser. Client giữ outbox
khi ghi lỗi. `/api/events` không báo acknowledged giả và không vượt kiểm tra
ownership bằng fallback.
Gợi ý không chờ hàng đợi đồng bộ xong; đọc history đã lưu trên server trong lúc
client tiếp tục retry outbox. Các tương tác chưa gửi thành công chưa ảnh hưởng
đến personalization, và vẫn được giữ để đồng bộ sau.
Timeout proxy lưu event là 12s và client 15s, dài hơn worker xác minh item 8s;
không ngắt sớm ở 3s rồi chặn gợi ý trong khi backend vẫn xử lý.

Nhấp/thêm giỏ được liên kết với recommendation trong cùng phiên, cửa sổ 30 phút.
Báo cáo đếm unique clicked impressions / impressions; cart_rate tương tự. Khoảng
tin cậy chênh lệch CTR dùng bootstrap theo user/browser, không xem mọi impression
là một người độc lập. Không suy ra purchase conversion từ hành vi thử.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/report_recommendation_ab.py --experiment dcn_lightgbm_home_v2_interest --output training/evaluation/results/ab_live_summary.json
```

Cần chốt cỡ mẫu/thời gian trước khi tuyên bố thắng. Chưa có kết quả A/B người dùng
thực; dữ liệu smoke test chỉ chứng minh cơ chế hoạt động và nằm trong fixture riêng.

## Kiểm chứng

- Test HTTP/ORM/worker dùng SQLite và Parquet cô lập, checkpoint DCN/LightGBM thật:
  chia nhóm, restart/fresh read, phân trang không chạy lại model, quyền truy cập,
  cursor hết hạn, impression idempotency, attribution và báo cáo.
- Chrome headless chạy qua UI Next.js → FastAPI → worker/model → DB fixture → đọc
  lại: tự tải khi cuộn, không trùng, lỗi phân trang/retry, cookie giữ nhóm khi reload,
  impression/click có trong DB, favorite không thành click, mobile 390px không tràn
  và không có JavaScript exception. Chỉ boundary lấy ảnh bên ngoài được thay bằng
  đáp án rỗng trong smoke test; metadata/ranking không bị mock.
- TypeScript, lint file gợi ý/API và Next.js build đã chạy. Build phát hiện lỗi
  Suspense có sẵn tại seller/orders; đã bọc boundary tối thiểu, giữ logic trang đó.
- PostgreSQL hiện có được kiểm tra chỉ đọc: kết nối được, các cột cần dùng tồn tại.
  Migration 004 được kiểm tra riêng trên TEMP và đã áp dụng theo xác nhận của
  người dùng; check constraint được đọc lại và xác nhận có impression.
  FastAPI event route → PostgreSQL thật được kiểm tra trong transaction rollback:
  POST thành công, fresh read thấy event, retry idempotent, vị trí sai 422 và
  query xóa draft giữ item có event. Toàn bộ row probe được rollback sau kiểm tra.
  Chưa ghi tương tác giả lên PostgreSQL thật và chưa đo tải đồng thời/full catalog
  latency của hai nhóm. Không bảo đảm không còn lỗi ở mọi dữ liệu/trình duyệt.

Probe trên catalog/checkpoint thật, dùng ID có trong TRAIN và không ghi DB:
pipeline trả 24 item từ 1.300 ứng viên, gồm 300 ANN hit; content, ALS, GRU,
Two-Tower và DCN đều đóng góp điểm, xử lý khoảng 16,3s trên máy local. Đây là
kiểm tra adapter với lịch sử chủ động dựng, không phải số liệu tương tác thật
hoặc chất lượng ranking. Kết quả nằm ở
`training/evaluation/results/online_model_pipeline_probe_20261012.json`.
Browser smoke kiểm tra riêng sự cố event API: feed guest vẫn hiện, view giữ
trong outbox và được lưu/đọc lại sau khi boundary phục hồi.

Artifacts kiểm tra trình duyệt: `training/evaluation/results/ab_browser_smoke_20261012/`
(checks.json, desktop.png, mobile.png). Fixture server chỉ dùng DB SQLite riêng;
không chạy trực tiếp utility này như backend phục vụ người dùng.

## Tắt thử nghiệm

Đặt `MERREC_AB_ENABLED=0` và restart backend để quay về `MERREC_RANKER` cũ. Snapshot
đã cấp giữ nguyên model/tag đến hết hạn. Event lỗi nằm trong outbox để đồng bộ khi
backend phục hồi; reload feed tạo snapshot mới, không tự đổi group cùng identity.
