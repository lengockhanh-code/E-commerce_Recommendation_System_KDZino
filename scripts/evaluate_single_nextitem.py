"""Đánh giá một sản phẩm TEST đầu tiên/user với Recall@20/50/100."""
import argparse
import os
from pathlib import Path
import sys

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(key, "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.evaluation.nextitem import MODELS, build_cases, summarize
from training.evaluation.retrievers import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("all", *MODELS), default="all")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "training/evaluation/results/test_single_nextitem_top100")
    args = parser.parse_args()
    cases, history, manifest = build_cases(ROOT, ROOT / "training/evaluation/results/test_nextitem")
    # Each model writes resumable progress; the original Top-20 results are preserved.
    for model in (("covis", "twotower", "als", "gru", "content") if args.model == "all" else (args.model,)):
        print(f"Đánh giá {model}: Top-100, cùng {len(cases):,} users", flush=True)
        result = evaluate(model, ROOT, args.output, cases, history, manifest, ks=(10,20,50,100))
        print(result[["model", "cohort_scope", "target_group", "users", "Recall@20",
                      "Recall@50", "Recall@100"]].to_string(index=False), flush=True)
        summary = summarize(args.output)
        summary.query("cohort_scope=='ALL_CASES' and target_group=='ALL'").to_csv(
            args.output / "next_item_test_all.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
