from agent import memory
import os
from memory import STATE, log
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "agent"))
from verifier import verify

RESET_URL = "http://127.0.0.1:5000/reset"

CASES = [
    {"name": "Globex (under limit)",
     "task": "Find the latest invoice from Globex Traders and enter it into the company finance system.",
     "invoice": "GLX-220", "stdin": "", "expect_saved": True},
    {"name": "Acme (approved)",
     "task": "Find the latest invoice from Acme Supplies and enter it into the company finance system.",
     "invoice": "ACM-1007", "stdin": "yes\n", "expect_saved": True},
    {"name": "Acme (rejected)",
     "task": "Find the latest invoice from Acme Supplies and enter it into the company finance system.",
     "invoice": "ACM-1007", "stdin": "no\n", "expect_saved": False},
    {"name": "Initech (different vendor)",
     "task": "Enter the latest Initech Services invoice into the finance system.",
     "invoice": "INT-3090", "stdin": "", "expect_saved": True},
]

# Optional: choose cases by number, e.g.  python evals/run_evals.py 2 3
if len(sys.argv) > 1:
    chosen = [int(a) - 1 for a in sys.argv[1:]]
    CASES = [CASES[i] for i in chosen]

env = dict(os.environ, PYTHONIOENCODING="utf-8")
results = []

for case in CASES:
    print(f"\n>>> Running: {case['name']}")
    urllib.request.urlopen(RESET_URL).read()
    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "agent/loop.py", case["task"]],
            input=case["stdin"], text=True, capture_output=True,
            cwd=BASE, timeout=400, env=env, encoding="utf-8", errors="replace",
        )
        out = proc.stdout
    except subprocess.TimeoutExpired:
        out = ""
    steps = out.count("[step ")
    retries = out.count("retrying in")
    saved, msg = verify(case["invoice"])
    completed = "=== FINAL ANSWER ===" in out
    asked = "AGENT NEEDS HUMAN INPUT" in out
    needs_approval = bool(case["stdin"].strip())
    passed = completed and (saved == case["expect_saved"]) and (asked or not needs_approval)
    if not completed:
        msg = "AGENT DID NOT FINISH (model error). " + msg
    results.append((case["name"], passed, steps, retries, round(time.time() - start), msg))
    print(f"    {'PASS' if passed else 'FAIL'} ({steps} steps)")

print("\n=== EVAL RESULTS ===")
for name, passed, steps, retries, secs, msg in results:
    print(f"{'PASS' if passed else 'FAIL'} | {name} | steps={steps} | model retries={retries} | {secs}s")
    print(f"      verifier: {msg}")
ok = sum(1 for r in results if r[1])
print(f"\nSuccess rate: {ok}/{len(results)}")