from pathlib import Path
import json
root=Path("report/merrec_canva")
new_rows=json.loads(r'''[[3,"01 Introduction","Bối cảnh và thực trạng thương mại điện tử",["Theo Bộ Công Thương, quy mô TMĐT Việt Nam năm 2024 vượt 25 tỷ USD, tăng 20% so với năm 2023.","Catalog đa dạng đặt ra bài toán giúp người mua khám phá sản phẩm phù hợp.","Trong bài toán C2C, dữ liệu hành vi và thuộc tính item là nguồn tín hiệu cho gợi ý.","Đề tài dùng MerRec từ Mercari để thực nghiệm; không dùng dữ liệu thị trường Việt Nam để huấn luyện."],"Hai thẻ >25 tỷ USD và +20%, ghi rõ năm 2024; bên dưới là liên hệ tới bài toán khám phá sản phẩm.",[],["https://moit.gov.vn/khoa-hoc-va-cong-nghe/thuong-mai-dien-tu-viet-nam-nam-2024-nhung-buoc-tien-va-thach-thuc.html","https://arxiv.org/abs/2402.14230"],"Số liệu Việt Nam chỉ là bối cảnh năm 2024, không phải thống kê năm hiện tại. Nhu cầu khám phá sản phẩm là động lực thiết kế, không phải kết quả khảo sát người dùng của đồ án. Nguồn Bộ Công Thương đăng ngày 18/02/2025."],[4,"01 Introduction","Vấn đề thực tiễn: tìm sản phẩm nào giữa catalog lớn?",["Người mua cần thu hẹp lựa chọn và tìm item phù hợp với mối quan tâm.","Tìm kiếm theo từ khóa cần người dùng diễn đạt được nhu cầu; danh sách phổ biến không tự phản ánh sở thích riêng.","Dữ liệu dự án có 30,05 triệu item nhưng 71,17% item có dưới 5 tương tác.","84,55% sự kiện là view: cần khai thác cả lịch sử hành vi thay vì chỉ chờ tín hiệu mua."],"Hai cột: khó khăn khi khám phá sản phẩm và bằng chứng trong MerRec; kết luận nhu cầu gợi ý dựa trên dữ liệu.",[],["data/processed/eda_merrec_may/kernel_1752/tables/02_overview.csv","data/processed/eda_merrec_may/kernel_1752/tables/06_cold_items.csv","data/processed/recommender/tables/01_event_mapping.csv"],"Các hạn chế của tìm kiếm/phổ biến là phân tích thiết kế phương pháp; không khẳng định tất cả sàn thương mại điện tử đang hoạt động như vậy. Không suy ra conversion từ tỷ lệ event."],[5,"01 Introduction","Lý do chọn đề tài",["Tính thực tiễn: hỗ trợ khám phá sản phẩm dựa trên nhu cầu và lịch sử người dùng.","Tính học thuật: nghiên cứu implicit feedback, long-tail, cold-start và dữ liệu tuần tự trong C2C.","Tính khả thi: MerRec có timestamp, nhiều hành vi và metadata để xây dựng thực nghiệm.","Tính ứng dụng: kết nối quy trình dữ liệu, mô hình gợi ý và giao diện minh họa."],"Bốn thẻ lý do: Thực tiễn · Học thuật · Dữ liệu phù hợp · Khả năng ứng dụng.",[],["https://arxiv.org/abs/2402.14230","training/00_eda.ipynb","training/01_preprocess.ipynb"],"Đây là lý do lựa chọn và giá trị kỳ vọng của đề tài, không phải tuyên bố đồ án đã tăng doanh thu, giảm thời gian tìm kiếm hoặc hoàn tất tích hợp model."],[6,"01 Introduction","Mục tiêu, ý nghĩa và phạm vi nghiên cứu",["Mục tiêu tổng quát: xây dựng và đánh giá phương pháp gợi ý Top-K trên dữ liệu hành vi MerRec.","Mục tiêu cụ thể: xử lý dữ liệu, EDA, tạo đặc trưng và thực nghiệm nhiều hướng mô hình.","Ý nghĩa: hiểu tác động của dữ liệu thưa, cold-start và giao thức đánh giá tới chất lượng gợi ý.","Phạm vi: lát dữ liệu tháng 05/2023, đánh giá offline; demo web tách riêng."],"Mục tiêu tổng quát ở dải đầu; ba khối Công việc · Ý nghĩa · Phạm vi bên dưới.",[],["training/00_eda.ipynb","training/01_preprocess.ipynb","training/models"],"Không khẳng định ưu thế mô hình khi các thực nghiệm chưa thống nhất protocol. SASRec, DCN và LightGBM chưa hoàn tất; chưa có kiểm chứng hiệu quả kinh doanh hoặc A/B test."],[7,"02 Problem Definition","Bài toán gợi ý và các thách thức",["Đầu vào: lịch sử user, loại hành vi và metadata; đầu ra: danh sách Top-K item.","Hai hướng nghiên cứu: truy hồi theo sở thích/nội dung và dự đoán item tiếp theo.","Độ thưa user–item khoảng 99,999843%; 32,75% dòng TEST chứa cold item.","Đánh giá Recall, HitRate, NDCG; chú ý coverage, tập user và candidate universe."],"Sơ đồ Đầu vào → Mô hình → Top-K ở trên; hai số liệu thách thức và nhóm metric ở dưới.",[],["training/models/04_gru4rec.ipynb","training/models/05_two_tower.ipynb","data/processed/eda_merrec_may/kernel_1752/tables/12_matrix_sparsity.csv","data/processed/recommender/tables/03_cold_start_summary.csv"],"Gộp phát biểu bài toán và thách thức để dành thêm chỗ cho lý do chọn đề tài, giữ tổng 40 trang."],[8,"03 Dataset Description","MerRec: quy mô và cấu trúc dữ liệu",["312 file Parquet, khoảng 21,57 GB; 174.872.167 tương tác trong lát dữ liệu tháng 05/2023.","2.765.863 user; 30.054.040 item_id; 913.718 product_id duy nhất.","Các nhóm trường: định danh; event/timestamp/session; tên, giá, category và thuộc tính item.","Nguồn là nền tảng C2C Mercari; session EDA dùng cặp (user_id, session_id)."],"Ba thẻ số liệu phía trên; bảng ba nhóm trường ở dưới; nguồn và phạm vi ở chân trang.",[],["https://arxiv.org/abs/2402.14230","data/processed/eda_merrec_may/kernel_1752/tables/01_structure_summary.csv","data/processed/eda_merrec_may/kernel_1752/tables/02_overview.csv","data/processed/eda_merrec_may/kernel_1752/tables/01_union_schema.csv"],"Dataset gốc trong bài báo bao phủ 6 tháng năm 2023; đồ án chỉ dùng lát tháng 05. Phân biệt item_id và product_id. 4.196.977 session_id khác 34.832.704 cặp (user_id, session_id)."]]''')
p=root/"slides.json"
slides=json.loads(p.read_text(encoding="utf-8"))
for row in new_rows:slides[row[0]-1]=row
p.write_text(json.dumps(slides,ensure_ascii=False,indent=2),encoding="utf-8")

p=root/"build_pack.py";s=p.read_text(encoding="utf-8-sig")
start=s.index("slides=json.loads(")
if s[start:].startswith("slides=json.loads(r"):
    end=s.index("''')",start)+4
    s=s[:start]+'slides=json.loads((OUT/"slides.json").read_text(encoding="utf-8"))'+s[end:]
s=s.replace('for source in s[6]:assert (ROOT/source).exists(),source','for source in s[6]:assert source.startswith("https://") or (ROOT/source).exists(),source')
old='files=[p for p in OUT.rglob("*") if p.is_file() and p.suffix not in [".zip",".py",".pyc"] and "__pycache__" not in p.parts]'
new='files=[OUT/name for name in ["README.txt","DAN_Y_38_SLIDE.md","PROMPT_CANVA.txt","XEM_DAN_Y_VA_ANH.html","slides.json","danh_muc_anh.csv","ket_qua_trich_xuat.csv"]] + sorted(IMG.glob("*.png"))'
s=s.replace(old,new)
s=s.replace("Đây là dàn ý và tài nguyên ảnh, không phải PowerPoint.","Bản PowerPoint chỉnh sửa được: MERREC_THUYET_TRINH_40_SLIDE.pptx; bản xem nhanh: MERREC_THUYET_TRINH_40_SLIDE.pdf.")
p.write_text(s,encoding="utf-8")

p=root/"create_pptx.py";s=p.read_text(encoding="utf-8")
for old,new in {
'text(s,.72,1.55,7.2,1.0,"MerRec",64':'text(s,.72,1.55,7.2,1.15,"MerRec",64',
'text(s,.96,4.87,11.4,.3,"user':'text(s,.96,4.87,11.4,.39,"user',
'text(s,3.97,2.65,.8,.6,"≈"':'text(s,3.97,2.65,.8,.74,"≈"'
}.items():s=s.replace(old,new,1)
start=s.index("    elif n==3:")
end=s.index("    elif n==9:",start)
block=r'''    elif n==3:
        metric(s,.72,1.98,5.82,2.02,">25 tỷ USD","Quy mô TMĐT Việt Nam · 2024")
        metric(s,6.8,1.98,5.82,2.02,"+20%","Tăng trưởng so với năm 2023")
        bullets(s,["Nhu cầu ứng dụng: giúp người mua khám phá sản phẩm phù hợp trong catalog đa dạng.",
                   "Bài toán nghiên cứu: khai thác dữ liệu hành vi và metadata cho gợi ý C2C."],.88,4.37,11.6,20,.78)
        callout(s,"Bối cảnh: Việt Nam. Dữ liệu thực nghiệm: MerRec từ Mercari — hai phạm vi khác nhau.",y=6.16,h=.43)
        source=text(s,.85,6.69,11.7,.2,"Nguồn: Bộ Công Thương, báo cáo năm 2024 (18/02/2025); Li et al., MerRec (2024).",9,"muted")
        source.text_frame.paragraphs[0].runs[0].hyperlink.address=sources[0]
    elif n==4:
        box(s,.73,1.98,5.8,3.97,"pale",radius=True)
        label(s,1.0,2.26,5.2,"GÓC NHÌN NGƯỜI DÙNG",size=13)
        bullets(s,["Cần thu hẹp lựa chọn theo mối quan tâm.",
                   "Từ khóa cần diễn đạt rõ nhu cầu.",
                   "Danh sách phổ biến không tự phản ánh sở thích riêng."],1.0,2.94,5.13,20,.86)
        box(s,6.8,1.98,5.8,3.97,"pale",radius=True)
        label(s,7.08,2.26,5.2,"BẰNG CHỨNG TỪ MERREC",size=13)
        for j,(v,t) in enumerate([("30,05M","item trong lát dữ liệu"),("71,17%","item có dưới 5 tương tác"),("84,55%","sự kiện là lượt xem")]):
            yy=2.83+j*.94
            text(s,7.08,yy,2.16,.52,v,29,"blue",True)
            text(s,9.32,yy+.11,2.85,.5,t,17)
        callout(s,"Động lực: tận dụng nhiều tín hiệu để gợi ý một danh sách ngắn phù hợp hơn.",y=6.27,h=.53)
    elif n==5:
        reasons=[("01 · Tính thực tiễn","Hỗ trợ khám phá sản phẩm từ nhu cầu và lịch sử người dùng."),
                 ("02 · Tính học thuật","Nghiên cứu implicit feedback, long-tail, cold-start và chuỗi."),
                 ("03 · Dữ liệu phù hợp","MerRec có timestamp, nhiều hành vi và metadata để thực nghiệm."),
                 ("04 · Khả năng ứng dụng","Kết nối xử lý dữ liệu, mô hình và giao diện minh họa.")]
        for i,(t,d) in enumerate(reasons):
            x=.73+(i%2)*6.08;y=1.98+(i//2)*2.07
            box(s,x,y,5.81,1.79,"pale",radius=True)
            text(s,x+.24,y+.23,5.28,.43,t,22,"blue",True)
            text(s,x+.24,y+.86,5.28,.65,d,19)
        callout(s,"Giá trị kỳ vọng của đề tài; chưa phải bằng chứng tăng doanh thu hoặc hiệu quả online.",y=6.33,h=.48)
    elif n==6:
        box(s,.73,1.96,11.87,1.04,"navy",radius=True)
        text(s,.98,2.19,11.34,.64,"Xây dựng và đánh giá gợi ý Top-K từ dữ liệu hành vi MerRec",25,"white",True,PP_ALIGN.CENTER)
        columns=[("CÔNG VIỆC","Xử lý dữ liệu và EDA.\nTạo đặc trưng.\nThực nghiệm mô hình."),
                 ("Ý NGHĨA","Hiểu sparsity và cold-start.\nĐọc đúng giao thức đánh giá.\nLàm cơ sở tích hợp."),
                 ("PHẠM VI","Dữ liệu tháng 05/2023.\nĐánh giá offline.\nDemo web tách riêng.")]
        for i,(t,d) in enumerate(columns):
            x=.73+i*4.08
            box(s,x,3.43,3.71,2.36,"pale",radius=True)
            label(s,x+.22,3.7,3.27,t,size=13)
            text(s,x+.22,4.25,3.27,1.43,d,18)
        callout(s,"SASRec, DCN và LightGBM chưa hoàn tất; chưa có A/B test hoặc kiểm chứng kinh doanh.",y=6.27,h=.52)
    elif n==7:
        flow(s,[("Đầu vào","Lịch sử + hành vi + metadata"),("Mô hình","Retrieval / next-item"),("Top-K","Danh sách item xếp hạng")],y=1.99,h=1.74)
        for x,v,t in [(.89,"99,999843%","Độ thưa user–item"),(7.07,"32,75%","Dòng TEST chứa cold item")]:
            text(s,x,4.19,5.18,.62,v,34,"blue",True)
            text(s,x,4.99,5.18,.42,t,19,"muted")
        callout(s,"Recall@K · HitRate@K · NDCG@K — đọc cùng coverage, tập user và candidate universe.",y=6.12,h=.66)
    elif n==8:
        for x,v,t in [(.74,"174,87M","tương tác"),(4.83,"2,77M","người dùng"),(8.92,"30,05M","item_id duy nhất")]:
            box(s,x,1.94,3.69,1.29,"pale",radius=True)
            text(s,x+.2,2.13,3.27,.56,v,31,"blue",True)
            text(s,x+.2,2.8,3.27,.26,t,15)
        table(s,.74,3.57,11.88,2.18,["Nhóm trường","Thông tin chính"],
              [["Định danh","user_id · item_id · product_id"],
               ["Hành vi / thời gian","event_id · stime · session_id · sequence_id"],
               ["Metadata","name · price · category · brand · condition"]],[3.29,8.59],17)
        callout(s,"312 file · ~21,57 GB · 913.718 product_id · Đồ án dùng lát tháng 05/2023.",y=6.03,h=.48)
        source=text(s,.85,6.64,11.7,.25,"Nguồn: Li et al., MerRec (2024) và bảng tổng hợp local. Dataset gốc 6 tháng; đồ án dùng 1 tháng.",10,"muted")
        source.text_frame.paragraphs[0].runs[0].hyperlink.address=sources[0]
'''
s=s[:start]+block+s[end:]
s=s.replace('Nguồn trong D:/MerRec:', 'Nguồn tham khảo (URL hoặc đường dẫn trong D:/MerRec):')
p.write_text(s,encoding="utf-8")

p=root/"export_powerpoint.ps1";s=p.read_text(encoding="utf-8-sig")
old="""        foreach ($shape in $slide.Shapes) {
            if ($shape.HasTextFrame"""
new="""        foreach ($shape in $slide.Shapes) {
            if ($shape.HasTable -eq -1) {
                for ($ri = 1; $ri -le $shape.Table.Rows.Count; $ri++) {
                    for ($ci = 1; $ci -le $shape.Table.Columns.Count; $ci++) {
                        $cellShape = $shape.Table.Cell($ri, $ci).Shape
                        $cellTf = $cellShape.TextFrame
                        $cellAvailable = $cellShape.Height - $cellTf.MarginTop - $cellTf.MarginBottom
                        $cellActual = $cellTf.TextRange.BoundHeight
                        if ($cellActual -gt ($cellAvailable + 2)) {
                            $overflow += [PSCustomObject]@{slide=$slide.SlideIndex;shape="Table cell $ri,$ci";available=$cellAvailable;actual=$cellActual;text=$cellTf.TextRange.Text}
                        }
                    }
                }
            }
            if ($shape.HasTextFrame"""
if "cellAvailable" not in s:
    assert old in s
    s=s.replace(old,new,1)
s=s.replace("$overflow | ConvertTo-Json -Depth 4","ConvertTo-Json -InputObject @($overflow) -Depth 4")
p.write_text(s,encoding="utf-8-sig")
(root/"NGUON_BOI_CANH.md").write_text("""# Nguồn bổ sung cho phần mở đầu

- Bộ Công Thương (18/02/2025): Thương mại điện tử Việt Nam năm 2024: Những bước tiến và thách thức.
  https://moit.gov.vn/khoa-hoc-va-cong-nghe/thuong-mai-dien-tu-viet-nam-nam-2024-nhung-buoc-tien-va-thach-thuc.html
  Sử dụng hai số liệu: quy mô năm 2024 trên 25 tỷ USD và tăng 20% so với năm 2023. Không gọi đây là số liệu năm 2026.
- Lichi Li và cộng sự (2024), MerRec: A Large-scale Multipurpose Mercari Dataset for Consumer-to-Consumer Recommendation Systems.
  https://arxiv.org/abs/2402.14230
  Dùng để xác định nguồn Mercari/C2C và đặc trưng dataset. Quy mô thực nghiệm lấy từ bảng local tháng 05/2023, không lấy toàn bộ 6 tháng trong bài báo.
- Hạn chế tìm kiếm/phổ biến và giá trị ứng dụng được trình bày như phân tích thiết kế, mục tiêu kỳ vọng; không phải kết quả khảo sát hoặc bằng chứng tăng doanh thu.

Đã đối chiếu nguồn ngày 28/09/2026.
""",encoding="utf-8")
print("Updated slides 3–8, outline generator, PPT layouts, and overflow checks.")
