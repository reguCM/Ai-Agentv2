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
research = run.get("pipeline", {}).get("research") or {}
for key in ["usable_findings", "reference_findings", "selected_findings", "findings"]:
    val = research.get(key) or []
    if val:
        print(f"{key}: {len(val)} items")
        for i, f in enumerate(val[:2]):
            if isinstance(f, dict):
                print(f"  [{i}] keys={list(f.keys())}")
                print(f"      command={f.get('command', '?')}")
                print(f"      sample={str(f.get('sample', ''))[:120]}")
            else:
                print(f"  [{i}] {str(f)[:120]}")
    else:
        print(f"{key}: empty")
