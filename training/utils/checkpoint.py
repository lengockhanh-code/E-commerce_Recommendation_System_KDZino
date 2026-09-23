
from pathlib import Path
import os
from .paths import CHECKPOINT_DIR

def model_checkpoint_dir(name):
    p = CHECKPOINT_DIR / name
    p.mkdir(parents=True, exist_ok=True)
    return p

def atomic_torch_save(obj, path):
    import torch
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)
