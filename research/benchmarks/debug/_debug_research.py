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
research = run.get("pipeline", {}).get("research")
if research:
    if isinstance(research, dict):
        print("research keys:", list(research.keys()))
        findings = research.get("findings") or research.get("selected_findings") or []
        print(f"findings: {len(findings)}")
        for i, f in enumerate(findings[:3]):
            cmd = f.get("command", "?")
            sample = str(f.get("sample", ""))[:80]
            print(f"  [{i}] command={cmd} sample={sample}")
    else:
        print("research type:", type(research))
else:
    print("no research in pipeline")
