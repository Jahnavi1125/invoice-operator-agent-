import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOG = BASE / "logs" / "run_log.jsonl"

STATE = {"approved": False}


def log(entry):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
