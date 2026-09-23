
from pathlib import Path

PROJECT_ROOT = Path(r"D:\MerRec")

TRAINING_DIR = PROJECT_ROOT / "training"
MODELS_DIR = TRAINING_DIR / "models"
UTILS_DIR = TRAINING_DIR / "utils"
CHECKPOINT_DIR = TRAINING_DIR / "checkpoints"

DATA_ROOT = PROJECT_ROOT / "data" / "processed" / "recommender"
MODEL_DATA_DIR = DATA_ROOT / "model_data"
SERVING_DIR = DATA_ROOT / "serving"
MODEL_SPECIFIC_DIR = DATA_ROOT / "model_specific"

INTERACTIONS_DIR = MODEL_DATA_DIR / "interactions"

CF_TRAIN = MODEL_DATA_DIR / "cf_train.parquet"
CATALOG_TRAIN = MODEL_DATA_DIR / "item_catalog_train.parquet"

POPULARITY_TRAIN = MODEL_DATA_DIR / "popularity_train.parquet"
TRENDING_TRAIN = MODEL_DATA_DIR / "trending_train.parquet"

EVAL_COHORT = MODEL_DATA_DIR / "eval_events_with_cold_start.parquet"

TRAIN_GLOB = (INTERACTIONS_DIR / "split=train" / "*.parquet").as_posix()
VAL_GLOB = (INTERACTIONS_DIR / "split=val" / "*.parquet").as_posix()
TEST_GLOB = (INTERACTIONS_DIR / "split=test" / "*.parquet").as_posix()

for p in [CHECKPOINT_DIR, MODEL_SPECIFIC_DIR]:
    p.mkdir(parents=True, exist_ok=True)
