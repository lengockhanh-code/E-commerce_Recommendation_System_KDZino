import csv
import os
import io
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parents[1] / "data" / "catalog"
INPUT_FILE = CATALOG_DIR / "product_catalog.csv"
OUTPUT_DIR = CATALOG_DIR / "catalog_split"

MAX_SIZE = 450 * 1024 * 1024   # 450 MB

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as src:

    reader = csv.reader(src)

    # Lấy header
    header = next(reader)

    part = 1
    current_size = 0
    out = None
    writer = None

    def open_new_part(part_number):
        filename = os.path.join(
            OUTPUT_DIR,
            f"product_catalog_part_{part_number:03d}.csv"
        )

        f = open(filename, "w", encoding="utf-8-sig", newline="")
        w = csv.writer(f)
        w.writerow(header)

        return f, w, os.path.getsize(filename)

    out, writer, current_size = open_new_part(part)

    for row in reader:

        # Tính dung lượng của dòng trước khi ghi
        temp = io.StringIO()
        temp_writer = csv.writer(temp)
        temp_writer.writerow(row)

        row_text = temp.getvalue()
        row_size = len(row_text.encode("utf-8"))

        # Nếu thêm dòng này làm file vượt 450MB -> tạo part mới
        if current_size + row_size >= MAX_SIZE:
            out.close()

            print(f"Part {part:03d} hoàn thành")

            part += 1
            out, writer, current_size = open_new_part(part)

        writer.writerow(row)
        current_size += row_size

    if out:
        out.close()

print("\nDONE")
print(f"Tổng số part: {part}")
print(f"Lưu tại: {OUTPUT_DIR}")
