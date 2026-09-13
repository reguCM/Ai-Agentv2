"""
Judge 契約の固定回帰基準。

judge_verify_retry A 3/3 と judge_adopt_usable ACCEPT 3/3 を baseline JSON に凍結する。
④本体や契約変更時は results だけが増え、baseline は上書きしない。

```text
python -m unittest tests.test_judge_regression_baseline
python -m research.llm_benchmarks.judge_regression
python -m research.llm_benchmarks.judge_regression --live
```
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS_DIR = Path(__file__).resolve().parent

JUDGE_CONTRACT_PHASE = "verify_gap_adopt_v5"

BASELINES = {
    "verify_retry": {
        "id": "verify_retry",
        "benchmark": "research.llm_benchmarks.judge_verify_retry",
        "baseline_path": BENCHMARKS_DIR / "judge_verify_retry_baseline_a.json",
        "results_path": BENCHMARKS_DIR / "judge_verify_retry_results.json",
        "pass_criterion": "A",
        "case": "judge_verify_failed_retry",
    },
    "adopt_usable": {
        "id": "adopt_usable",
        "benchmark": "research.llm_benchmarks.judge_adopt_usable",
        "baseline_path": BENCHMARKS_DIR / "judge_adopt_usable_baseline_accept.json",
        "results_path": BENCHMARKS_DIR / "judge_adopt_usable_results.json",
        "pass_criterion": "ACCEPT",
        "case": "judge_usable_usage_percent",
    },
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_baseline(name):
    spec = BASELINES[name]
    path = spec["baseline_path"]
    if not path.exists():
        raise FileNotFoundError(f"baseline がない: {path}")
    return load_json(path)


def trial_grades(entry):
    grades = []
    for item in entry.get("trials") or []:
        held = item.get("held") or {}
        grades.append(held.get("grade"))
    return grades


def compare_entry_to_baseline(entry, baseline):
    errors = []
    if entry.get("contract_phase") != baseline.get("contract_phase"):
        errors.append(
            f"contract_phase: got {entry.get('contract_phase')!r}, "
            f"want {baseline.get('contract_phase')!r}"
        )
    if entry.get("pass_criterion") != baseline.get("pass_criterion"):
        errors.append(
            f"pass_criterion: got {entry.get('pass_criterion')!r}, "
            f"want {baseline.get('pass_criterion')!r}"
        )
    if entry.get("case") != baseline.get("case"):
        errors.append(
            f"case: got {entry.get('case')!r}, want {baseline.get('case')!r}"
        )
    if not entry.get("pass"):
        errors.append("pass: expected true")
    expected_grades = baseline.get("grades") or {}
    actual_grades = entry.get("grades") or {}
    if actual_grades != expected_grades:
        errors.append(f"grades: got {actual_grades}, want {expected_grades}")
    expected_trial = baseline.get("trial_grades") or []
    actual_trial = trial_grades(entry)
    if actual_trial != expected_trial:
        errors.append(f"trial_grades: got {actual_trial}, want {expected_trial}")
    criterion = baseline.get("pass_criterion")
    for item in entry.get("trials") or []:
        held = item.get("held") or {}
        if held.get("grade") != criterion:
            errors.append(
                f"trial {item.get('n')}: grade {held.get('grade')!r} != {criterion!r}"
            )
    return errors


def latest_matching_run(results_path, *, case, contract_phase):
    payload = load_json(results_path)
    for entry in reversed(payload.get("runs") or []):
        if entry.get("case") != case:
            continue
        if entry.get("contract_phase") != contract_phase:
            continue
        return entry
    return None


def check_baseline_files():
    errors = []
    for name, spec in BASELINES.items():
        path = spec["baseline_path"]
        if not path.exists():
            errors.append(f"{name}: missing baseline {path}")
            continue
        baseline = load_json(path)
        if baseline.get("contract_phase") != JUDGE_CONTRACT_PHASE:
            errors.append(
                f"{name}: baseline contract_phase {baseline.get('contract_phase')!r} "
                f"!= {JUDGE_CONTRACT_PHASE!r}"
            )
        if not baseline.get("pass"):
            errors.append(f"{name}: baseline pass is not true")
        criterion = baseline.get("pass_criterion")
        for grade in baseline.get("trial_grades") or []:
            if grade != criterion:
                errors.append(
                    f"{name}: trial grade {grade!r} != pass_criterion {criterion!r}"
                )
    return errors


def check_latest_results():
    errors = []
    for name, spec in BASELINES.items():
        baseline = load_baseline(name)
        entry = latest_matching_run(
            spec["results_path"],
            case=spec["case"],
            contract_phase=baseline.get("contract_phase"),
        )
        if entry is None:
            errors.append(
                f"{name}: no results for case={spec['case']} "
                f"contract_phase={baseline.get('contract_phase')}"
            )
            continue
        errors.extend(
            f"{name}: {item}" for item in compare_entry_to_baseline(entry, baseline)
        )
    return errors


def run_live_benchmark(module_name):
    command = [sys.executable, "-m", module_name]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        check=False,
    )
    return completed.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description="Judge 固定回帰チェック")
    parser.add_argument(
        "--live",
        action="store_true",
        help="両ベンチを LLM 実行してから baseline と比較する",
    )
    args = parser.parse_args(argv)

    file_errors = check_baseline_files()
    if file_errors:
        print("baseline file check: FAIL")
        for item in file_errors:
            print(f"  - {item}")
        return 1
    print("baseline file check: OK")

    if args.live:
        for spec in BASELINES.values():
            print(f"running {spec['benchmark']} ...")
            code = run_live_benchmark(spec["benchmark"])
            if code != 0:
                print(f"{spec['benchmark']}: exit {code}")
                return code

    result_errors = check_latest_results()
    if result_errors:
        print("results vs baseline: FAIL")
        for item in result_errors:
            print(f"  - {item}")
        return 1

    print("results vs baseline: OK")
    for name, spec in BASELINES.items():
        baseline = load_baseline(name)
        print(
            f"  {name}: {baseline.get('pass_criterion')} "
            f"{baseline.get('trial_grades')} "
            f"({baseline.get('contract_phase')})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
