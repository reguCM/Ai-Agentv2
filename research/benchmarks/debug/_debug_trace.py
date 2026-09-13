import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT, bootstrap_repo_root

bootstrap_repo_root()
ROOT = REPO_ROOT
import json

data = json.load(open(ROOT / "research" / "llm_benchmarks" / "research_implement_results.json", encoding="utf-8"))
run = data["runs"][-1]
trace = run.get("trace") or []
for t in trace[:2]:
    phase = t.get("phase", "")
    payload = t.get("payload")
    if payload and isinstance(payload, dict):
        proposals = payload.get("proposals", [])
        if proposals:
            p = proposals[0]
            print(f"{phase}: name={p.get('name')} module={p.get('module')} function={p.get('function')}")
        else:
            print(f"{phase}: no proposals, keys={list(payload.keys())}")
    else:
        print(f"{phase}: payload={type(payload)}")
