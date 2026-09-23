import polars as pl

BASE = r"D:\MerRec\data\processed\recommender\model_data\interactions"

for split in ["train", "val", "test"]:
    print(f"\n=== {split.upper()} ===")
    print(
        pl.scan_parquet(BASE + fr"\split={split}\*.parquet")
        .group_by("event_group")
        .len()
        .sort("len", descending=True)
        .collect(engine="streaming")
    )