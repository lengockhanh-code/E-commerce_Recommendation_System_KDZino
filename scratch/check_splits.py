import duckdb

with duckdb.connect() as db:
    for split in ("train", "val", "test"):
        path = f"training/dcn/dataset/dcn_{split}.parquet"
        res = db.execute(f"SELECT count(*), count(distinct case_id), sum(label) FROM read_parquet('{path}')").fetchone()
        rows, cases, positives = res
        recall = positives / cases if cases else 0
        print(f"{split}: rows={rows}, cases={cases}, positives={positives}, recall={recall:.4f}")
