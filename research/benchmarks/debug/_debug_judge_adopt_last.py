import json
import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT, bootstrap_repo_root

bootstrap_repo_root()
ROOT = REPO_ROOT


def main():
    path = ROOT / "research" / "llm_benchmarks" / "judge_adopt_usable_results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    runs = data.get("runs") or []
    print("runs_total:", len(runs))
    if not runs:
        return
    run = runs[-1]
    print("last_case:", run.get("case"))
    print("last_pass:", run.get("pass"))
    print("last_grades:", run.get("grades"))
    trials = run.get("trials") or []
    if not trials:
        return
    t = trials[-1]
    print("last_trial_n:", t.get("n"))
    held = t.get("held") or {}
    print("held_grade:", held.get("grade"))
    print("held_ok:", held.get("ok"))
    print("held_misreject:", held.get("misreject"))
    print("held_missing:", held.get("missing"))
    print("held_reason:", held.get("reason"))
    print("llm_text_preview:", (t.get("llm_text") or "")[:500])


if __name__ == "__main__":
    main()
