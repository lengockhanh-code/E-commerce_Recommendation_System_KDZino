"""One entry point for the Shopee-inspired MerRec multi-future benchmark."""
import argparse
from pathlib import Path
from training.evaluation.pipeline import ROOT, run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retrieval-cache", type=Path,
                        default=ROOT / "training/evaluation/results/test_single_nextitem_top100")
    parser.add_argument("--dcn", type=Path,
                        default=ROOT / "training/dcn/runs/candidates500_agent_20261010/model/dcn_best.pt")
    parser.add_argument("--lightgbm", type=Path,
                        default=ROOT / "training/lightgbm_ranker/model/lightgbm_ranker.txt")
    args = parser.parse_args()
    run(args.output, args.retrieval_cache, args.dcn, args.lightgbm)
