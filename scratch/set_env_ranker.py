from pathlib import Path

env_path = Path(".env")
if env_path.exists():
    lines = env_path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    has_ranker = False
    has_lgb_path = False
    for line in lines:
        if line.startswith("MERREC_RANKER="):
            new_lines.append("MERREC_RANKER=lightgbm")
            has_ranker = True
        elif line.startswith("MERREC_LIGHTGBM_PATH="):
            new_lines.append("MERREC_LIGHTGBM_PATH=training/lightgbm_ranker/model/lightgbm_ranker.txt")
            has_lgb_path = True
        else:
            new_lines.append(line)
    if not has_ranker:
        new_lines.append("MERREC_RANKER=lightgbm")
    if not has_lgb_path:
        new_lines.append("MERREC_LIGHTGBM_PATH=training/lightgbm_ranker/model/lightgbm_ranker.txt")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("Updated .env with MERREC_RANKER=lightgbm")
