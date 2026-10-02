import json
import subprocess
import os
from pathlib import Path

ROOT = Path(".")
venv_python = ROOT / ".venv" / "Scripts" / "python.exe"

payload = {
    "context": "home",
    "user_id": "test-user-lgb",
    "preferences": ["tech", "beauty"],
    "history": [
        {"item_id": "100003961", "event_type": "view", "age_hours": 1.0}
    ],
    "segment": "few",
    "limit": 6,
    "covis": {},
    "popularity": {},
    "trending": {}
}

proc = subprocess.run(
    [str(venv_python), "scripts/personalized_recommendations.py"],
    input=json.dumps(payload),
    text=True,
    capture_output=True,
    env={**os.environ, "MERREC_RANKER": "lightgbm"}
)

print("STDOUT:")
try:
    data = json.loads(proc.stdout)
    print("ranker:", data.get("ranker"))
    print("model_name:", data.get("model_name"))
    print("model_status:", data.get("model_status"))
    print("items count:", len(data.get("items", [])))
    if data.get("items"):
        print("top item:", data["items"][0]["name"], "score:", data["items"][0]["score"])
except Exception as e:
    print("Error parsing stdout:", e)
    print("Raw stdout:", proc.stdout)

if proc.stderr:
    print("STDERR:", proc.stderr)
