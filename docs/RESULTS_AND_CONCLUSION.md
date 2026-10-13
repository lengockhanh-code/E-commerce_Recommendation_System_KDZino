# Kết quả thực nghiệm và kết luận cho báo cáo MerRec

Nội dung này mở rộng slide 46–50, dùng cùng benchmark đã kiểm chứng trong `training/evaluation/results/model_roles_canva_20261010/summary.json`. Không thay đổi checkpoint hoặc cách train. Số liệu bổ sung về phối hợp nguồn được đối chiếu bằng SQL trên candidate đã cố định.

## 9. Kết quả thực nghiệm

Benchmark gồm 5.000 user và 61.030 cặp user–item phân biệt sẽ tương tác trong TEST. Mỗi user nhận một danh sách gợi ý tại mốc trước tương tác TEST đầu tiên; lịch sử chỉ gồm các sự kiện TRAIN + VAL trước mốc đó. User được phép tương tác lại item đã xem. Kết quả đánh giá theo vai trò của từng tầng: retrieval có đưa item đúng vào pool hay không, ranker có đưa các item đúng trong pool lên vị trí cao hay không, và cuối cùng toàn pipeline bắt được bao nhiêu target tương lai.

### 9.1. Đóng góp và phối hợp của các nguồn retrieval

**Co-visitation là nguồn bao phủ chính trong cấu hình hiện tại.** Nguồn này bắt được 3.493 target ở top100, trong đó 2.538 target không có trong output các nguồn còn lại. Khi dự đoán item TEST đầu tiên tại cùng mốc lịch sử, HR@20 đạt 8,28%, cao nhất trong năm nguồn. Các kết quả phù hợp với vai trò khai thác liên hệ giữa các item trong lịch sử. Tuy vậy, 3.493 hit chỉ tương ứng 5,72% toàn bộ target tương lai: nguồn này vẫn chưa bao phủ được phần lớn nhu cầu trong cả giai đoạn TEST.

**Content-Based bổ sung tín hiệu nội dung.** Mô hình bắt được 1.276 target, với 519 target riêng. Có 292 hit thuộc item ngoài TRAIN, cho thấy metadata giúp tiếp cận một số item mà tương tác TRAIN chưa bao phủ. Tuy nhiên catalog/IDF hiện có metadata từ cả TRAIN + VAL + TEST; phép đo chưa chứng minh khả năng xử lý item hoàn toàn mới trong một triển khai chỉ biết thông tin tại thời điểm dự đoán.

**ALS bổ sung sở thích cộng tác.** Mặc dù chỉ bắt được 305 target khi chạy riêng, 203 target là đóng góp riêng vào pool. Vì vậy kết quả thấp khi chạy riêng không đồng nghĩa model không có tác dụng trong hệ nhiều nguồn. ALS thực hiện fold-in lịch sử user với item factors cố định. 24 hit ngoài TRAIN không được gọi là cold item hoàn toàn, vì factors được học trên TRAIN + VAL.

**GRU4Rec bổ sung thông tin thứ tự tương tác.** Mô hình bắt được 252 target, trong đó 44 target riêng; HR next-item@20 đạt 0,54%. Đây là đóng góp còn nhỏ trong benchmark hiện tại, chưa đủ bằng chứng khẳng định ưu thế của model chuỗi. Weights thực tế là epoch 8 trong khi metadata ghi best epoch 6; catalog scoring là catalog TRAIN cố định. Cần thống nhất thông tin checkpoint và train/evaluate đúng nhiệm vụ chuỗi trước khi kết luận nguyên nhân model yếu.

**Two-Tower bổ sung ứng viên từ không gian vector.** Mô hình bắt được 365 target, với 240 target riêng. User query hiện là embedding ID tĩnh, chưa cập nhật theo lịch sử tại inference; item index cũng cố định theo TRAIN. Kiến trúc ANN hướng đến retrieval có khả năng mở rộng, nhưng benchmark chưa đo latency trên cùng máy nên chưa có bằng chứng số liệu về lợi thế tốc độ. Cần bổ sung history vào user tower và kiểm tra cập nhật index để khai thác tốt hơn mục đích kiến trúc.

Sự phối hợp được thể hiện trực tiếp trên output đã cố định:

| Nguồn được hợp nhất | Target đúng có trong pool | Coverage micro |
| --- | ---: | ---: |
| Co-visitation | 3.493 | 5,72% |
| Co-visitation + Content-Based | 4.057 | 6,65% |
| Đủ năm nguồn | 4.547 | 7,45% |

Thêm Content vào Co-visitation đưa thêm 564 target vào pool; thêm ALS, GRU và Two-Tower vào hai nguồn này đưa thêm 490 target. Hợp nhất đủ năm nguồn tăng 1.054 target so với Co-visitation, tương đương 30,17% về số hit. Đây là bằng chứng bổ sung coverage của các output, **có kèm ngân sách candidate lớn hơn**: mỗi nguồn top100, hợp nhất tối đa 500 trước khử trùng. Chưa phải so sánh cùng budget hay ablation retrain/rerank.

Con số 564 không mâu thuẫn với 519 target riêng của Content: 564 là phần Content bổ sung so với Co-visitation; 519 là phần chỉ Content có khi xét đủ năm nguồn. Tương tự, 490 là đóng góp hợp nhất của ba nguồn sau, không phải tổng cộng đơn giản mọi hit riêng. Các nguồn có phần overlap nên không cộng thẳng số hit từng model.

### 9.2. Ranker chuyển coverage thành danh sách có ích như thế nào?

Candidate pool sau khử trùng gồm 2.444.585 dòng và chứa 4.547 target. RRF là baseline hợp nhất theo thứ hạng nguồn; DCN và LightGBM là hai phương thức rerank thay thế trên cùng pool. Hai ranker không chạy nối tiếp và không được cộng điểm chung trong benchmark này.

Có 2.037 user có target trong pool, nên phép đo riêng ranker dùng các user này và nhãn là target đã nằm trong pool. Recall micro chia tổng hit cho 4.547; NDCG lấy trung bình/user, IDCG theo số target trong pool của user. Giữ nguyên cả candidate sai và thứ tự dự đoán; không lọc theo nhãn hoặc chèn target. 2.963 user còn lại vẫn được tính điểm 0 trong đánh giá toàn pipeline.

| Phương thức | Hit top20 | Hit top100 | Giữ target pool @20 | Giữ target pool @100 | NDCG pool @20 | NDCG pool @100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| RRF | 1.362 | 2.552 | 29,95% | 56,12% | 0,2149 | 0,2706 |
| DCN numeric | 801 | 2.720 | 17,62% | 59,82% | 0,1251 | 0,2086 |
| LightGBM | 1.383 | 3.496 | 30,42% | 76,89% | 0,1921 | 0,2887 |

**RRF là baseline mạnh ở đầu danh sách.** NDCG@20 cao nhất cho thấy các target đúng được đặt ở vị trí có giá trị cao hơn trong phép đo hiện tại. Dù LightGBM có nhiều hơn 21 hit top20, NDCG top20 thấp hơn; số lượng hit và vị trí của hit trả lời hai câu hỏi khác nhau.

**LightGBM hiệu quả nhất ở top100 trong phép so sánh này.** Model giữ thêm 944 target so với RRF và đạt NDCG@100 cao nhất. Điều này cho thấy lợi ích rõ của học rerank trên pool cố định ở độ sâu 100. Chưa đủ cơ sở chọn LightGBM cho mọi độ sâu hoặc suy ra CTR/CVR tăng trên website.

**DCN có đóng góp ở top100 nhưng yếu ở top20.** DCN giữ thêm 168 target vào top100 so với RRF, song top20 ít hơn 561 hit và NDCG cũng thấp hơn. GAUC proxy đạt 0,7900, cao hơn RRF 0,7461, nhưng đây là khả năng phân biệt target tương lai và item không quan sát tương tác trong pool trên toàn thứ tự. Nó không bảo đảm các hit được đưa lên đầu danh sách. Không dùng GAUC để thay thế NDCG topK hoặc tuyên bố DCN tốt nhất.

### 9.3. Kết quả toàn pipeline và giới hạn hiện tại

| Pipeline trên cùng pool | Hit top100 | Recall micro trên 61.030 target |
| --- | ---: | ---: |
| Retrieval hợp nhất + RRF | 2.552 | 4,18% |
| Retrieval hợp nhất + DCN | 2.720 | 4,46% |
| Retrieval hợp nhất + LightGBM | 3.496 | 5,73% |

Ví dụ LightGBM: coverage retrieval 7,45% × tỷ lệ giữ target pool 76,89% ≈ recall micro toàn pipeline 5,73%. Quan hệ này chỉ dùng cùng mẫu số target micro, không áp dụng trực tiếp cho macro recall hoặc NDCG. 76,89% không phải tỷ lệ sản phẩm gợi ý đúng; đó là phần target trong pool được giữ vào top100.

Nút thắt coverage giải thích vì sao điểm ranker trong pool có thể cao hơn nhiều so với điểm toàn pipeline: retrieval đã bỏ sót 92,55% target, ranker không thể chọn item ngoài pool. Đồng thời trung bình mỗi user có 12,206 target trong cả giai đoạn TEST, trong khi danh sách topK có giới hạn. Kết quả này là dự đoán nhiều item ở một mốc cố định, không phải phép đo last-target/case dễ so sánh trực tiếp với báo cáo cũ.

Train ranker theo target cuối/case nhưng test theo nhiều target và mốc trước TEST có thể tạo lệch task/context; chưa có ablation để tách ảnh hưởng. Không suy ra overfit chỉ từ best epoch 1. Catalog và dữ liệu train của các nguồn cũng khác nhau. PURCHASE chỉ có 40 target, chưa đủ để kết luận hiệu quả mua hàng. Không có impression labels hay A/B; GAUC/AUC là proxy. Demo còn routing/rules/hybrid và có thể blend theo cấu hình, nên benchmark ranker thuần không chứng minh mọi request thực tế chạy cùng pipeline.

## 10. Kết luận

Thực nghiệm cho thấy vai trò của mỗi model cần được đọc trong tầng mà nó phục vụ. Ở tầng retrieval, Co-visitation cung cấp phần lớn target bắt được; Content-Based bổ sung các item dựa trên nội dung; ALS, GRU4Rec và Two-Tower có đóng góp riêng dù số hit standalone còn thấp. Hợp nhất năm nguồn đưa thêm 1.054 target vào pool so với Co-visitation. Điều đó chứng minh tính bổ sung của output hiện có, nhưng gain đi cùng tăng ngân sách candidate, chưa thể quy toàn bộ cho ưu thế kiến trúc.

Ở tầng ranking, LightGBM chuyển phần target đã được retrieval lấy vào thành danh sách top100 hiệu quả nhất trong phép so sánh hiện tại, giữ được 3.496/4.547 target và có NDCG@100 cao nhất. DCN giữ được nhiều target top100 hơn RRF nhưng chưa đưa chúng lên đầu tốt; kết quả top20 còn thấp. RRF vẫn là baseline đáng giữ vì có NDCG@20 cao nhất. Do đó lựa chọn ranker cần theo mục tiêu độ sâu danh sách của ứng dụng, không chỉ chọn một chỉ số đẹp hoặc model phức tạp hơn.

Kết quả toàn pipeline vẫn bị giới hạn chủ yếu bởi coverage 7,45%. Với LightGBM, recall micro top100 trên mọi target đạt 5,73%, cho thấy phần ranker không thể bù các target chưa vào pool. Hướng cải thiện ưu tiên là mở rộng retrieval có kiểm soát trên VAL, đo đóng góp dưới cùng candidate budget, và train ranker khớp mốc cắt cùng nhãn nhiều target. Với Two-Tower cần cho user tower nhận history; với GRU cần đồng bộ weights/metadata và kiểm tra nhiệm vụ chuỗi. Các thay đổi phải được chốt trước khi dùng TEST mới.

Các kết luận trên chỉ áp dụng cho benchmark offline đã nêu. Chưa xác nhận hiệu quả mua hàng, CTR/CVR, tốc độ ANN hoặc hành vi mọi request demo. Cần đo ablation rerank, latency trên cùng máy, sau đó thu thập impression và thực hiện A/B để xác nhận hiệu quả online. Báo cáo cần giữ cả đóng góp đạt được và các giới hạn này để thể hiện đúng tác dụng của pipeline.
