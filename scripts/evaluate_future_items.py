"""TEST: recommend all products users will interact with, using fixed models."""
import argparse
import os
from pathlib import Path
import sys

for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ.setdefault(key,"2")
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from training.evaluation.future_items import build_future_cases,evaluate_future_model,summarize_future
from training.evaluation.nextitem import MODELS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",choices=("cases","summary",*MODELS),required=True)
    parser.add_argument("--output",type=Path,default=ROOT/"training/evaluation/results/test_future_items")
    args=parser.parse_args()
    if args.model=="summary":
        print(summarize_future(args.output).to_string(index=False))
        return
    u,t,h,m=build_future_cases(ROOT,args.output)
    if args.model!="cases":
        result=evaluate_future_model(args.model,ROOT,args.output,u,t,h,m)
        print(result.to_string(index=False))
        summarize_future(args.output)


if __name__=="__main__":
    main()
