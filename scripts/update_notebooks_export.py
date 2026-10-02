import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(r"D:\MerRec")
MODELS_DIR = ROOT / "training" / "models"

NOTEBOOK_MAP = {
    "01_content_based.ipynb": ("Content-Based", "export_content"),
    "02_covisitation.ipynb": ("Co-Visitation", "export_covis"),
    "03_als.ipynb": ("ALS", "export_als"),
    "04_gru4rec.ipynb": ("GRU4Rec", "export_gru"),
    "05_two_tower.ipynb": ("Two-Tower", "export_twotower"),
}

for nb_name, (model_label, export_fn_name) in NOTEBOOK_MAP.items():
    nb_path = MODELS_DIR / nb_name
    if not nb_path.exists():
        print(f"Skipping missing notebook: {nb_name}")
        continue

    with open(nb_path, "r", encoding="utf-8") as f:
        nb_data = json.load(f)

    # Check if already added
    cell_sources = ["".join(c.get("source", [])) for c in nb_data.get("cells", [])]
    if any(export_fn_name in s for s in cell_sources):
        print(f"Candidate export step already present in {nb_name}")
        continue

    md_cell = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            f"# EXPORT CANDIDATES FOR DCN RANKER — {model_label.upper()}\n",
            "\n",
            f"Bổ sung bước Export Top-K Candidates cho 3 split TRAIN, VAL, TEST vào `{ROOT / 'candidate_exports'}`.\n",
            "Mỗi split sẽ tạo file parquet có schema chuẩn:\n",
            "`case_id`, `user_id`, `candidate_item_id`, `target_item_id`, `score`, `rank`"
        ]
    }

    code_cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import sys\n",
            "from pathlib import Path\n",
            "\n",
            "ROOT = Path(r\"D:\\MerRec\")\n",
            "if str(ROOT) not in sys.path:\n",
            "    sys.path.insert(0, str(ROOT))\n",
            "\n",
            f"from scripts.export_all_candidate_datasets import {export_fn_name}\n",
            "\n",
            f"print(\"=== EXPORTING {model_label.upper()} CANDIDATES FOR DCN RANKER ===\")\n",
            "for split in [\"train\", \"val\", \"test\"]:\n",
            f"    {export_fn_name}(split)\n"
        ]
    }

    nb_data["cells"].extend([md_cell, code_cell])

    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb_data, f, indent=1, ensure_ascii=False)

    print(f"SUCCESS: Added Candidate Export cells to {nb_name}")
