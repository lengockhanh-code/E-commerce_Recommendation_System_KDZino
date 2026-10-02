"""Explicit local export: NPZ -> mmap item factors + Gram matrix for online ALS.

Run once after replacing the trusted ALS checkpoint. Requires several GB free.
Never runs at web startup; source checkpoints remain unchanged.
"""
import os
from pathlib import Path
import shutil
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def prepare(root=ROOT / "artifacts/merrec_models/ALS"):
    output = root / "serving"
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(root / "model/final_model.npz") as archive:
        info = archive.getinfo("item_factors.npy")
        if shutil.disk_usage(output).free < info.file_size + 512 * 1024 * 1024:
            raise RuntimeError("Not enough free space for ALS serving export")
        temporary = output / "item_factors.partial.npy"
        with archive.open(info) as source, temporary.open("wb") as target:
            shutil.copyfileobj(source, target, length=8 * 1024 * 1024)
    factors = np.load(temporary, mmap_mode="r", allow_pickle=False)
    gram = np.zeros((factors.shape[1], factors.shape[1]), dtype=np.float64)
    for offset in range(0, len(factors), 100000):
        block = np.asarray(factors[offset:offset + 100000], dtype=np.float64)
        gram += block.T @ block
    del factors
    np.save(output / "item_gram.partial.npy", gram)
    # Stop inference while replacing a serving version; Windows holds mmap files open.
    os.replace(temporary, output / "item_factors.npy")
    os.replace(output / "item_gram.partial.npy", output / "item_gram.npy")
    print("ALS serving factors and Gram matrix exported.")


if __name__ == "__main__":
    prepare()
