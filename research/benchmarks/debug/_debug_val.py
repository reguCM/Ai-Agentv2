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
print(json.dumps(run.get("validation_1"), ensure_ascii=False, indent=2))
