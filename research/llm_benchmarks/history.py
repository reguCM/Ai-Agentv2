"""
ベンチ結果から score / class / PASS の履歴を抜き、モデル別・ケース別に比較する。

unittest ではない。generated_code は持たない。
仕様は docs/scoring.md。
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from tools.system.config import ROOT
from tools.system.tool_builder.score import SCORING_VERSION, score_implementation


IMPLEMENTATION_RESULTS_PATH = (
    ROOT / "research" / "llm_benchmarks" / "implementation_results.json"
)
HISTORY_PATH = ROOT / "research" / "llm_benchmarks" / "history.json"
SUMMARY_PATH = ROOT / "research" / "llm_benchmarks" / "summary.json"


def load_json_file(path, default):
    target = Path(path)
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def save_json_file(path, payload):
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def compact_run(entry, *, benchmark="implementation"):
    """1 run から比較用の短い記録を作る。score が無ければ class から採点する。"""
    classified = entry.get("implementation_class")
    if not isinstance(classified, dict):
        classified = {}
    kind = classified.get("class") or entry.get("class")
    scored = None
    if entry.get("score") is None and classified.get("class"):
        scored = score_implementation(
            classified=classified, error=entry.get("error")
        )

    def pick(key, default=None):
        if key in entry and entry.get(key) is not None:
            return entry[key]
        if scored and scored.get(key) is not None:
            return scored[key]
        return default

    passed = pick("pass")
    if passed is None:
        passed = pick("ok")
    return {
        "timestamp": entry.get("timestamp"),
        "benchmark": benchmark,
        "case": entry.get("case"),
        "profile": entry.get("profile"),
        "model": entry.get("model"),
        "n": entry.get("n"),
        "pass": bool(passed) if passed is not None else False,
        "score": pick("score"),
        "grade": pick("grade"),
        "scoring_version": pick("scoring_version") or SCORING_VERSION,
        "class": kind,
        "timing": entry.get("timing"),
    }


def _stats(runs):
    scores = [item["score"] for item in runs if item.get("score") is not None]
    passed = sum(1 for item in runs if item.get("pass"))
    classes = {}
    grades = {}
    for item in runs:
        kind = item.get("class") or "unknown"
        classes[kind] = classes.get(kind, 0) + 1
        grade = item.get("grade") or "?"
        grades[grade] = grades.get(grade, 0) + 1
    timestamps = [item.get("timestamp") for item in runs if item.get("timestamp")]
    return {
        "runs": len(runs),
        "pass": passed,
        "fail": len(runs) - passed,
        "pass_rate": round(passed / len(runs), 3) if runs else 0,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
        "grades": grades,
        "classes": classes,
        "last": max(timestamps) if timestamps else None,
        "scoring_version": (runs[-1].get("scoring_version") if runs else None),
    }


def summarize(runs):
    by_case = defaultdict(lambda: defaultdict(list))
    by_model = defaultdict(lambda: defaultdict(list))
    for item in runs:
        case = item.get("case") or ""
        profile = item.get("profile") or ""
        by_case[case][profile].append(item)
        by_model[profile][case].append(item)
    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "scoring_version": SCORING_VERSION,
        "runs": len(runs),
        "by_case": {
            case: {
                profile: _stats(items) for profile, items in sorted(profiles.items())
            }
            for case, profiles in sorted(by_case.items())
        },
        "by_model": {
            profile: {
                case: _stats(items) for case, items in sorted(cases.items())
            }
            for profile, cases in sorted(by_model.items())
        },
    }


def compact_implementation_results(results=None):
    payload = results
    if payload is None:
        payload = load_json_file(IMPLEMENTATION_RESULTS_PATH, {"runs": []})
    return [
        compact_run(item, benchmark="implementation")
        for item in payload.get("runs") or []
    ]


def refresh_history(*, results=None):
    """implementation_results.json から history.json と summary.json を作り直す。"""
    runs = compact_implementation_results(results)
    save_json_file(
        HISTORY_PATH,
        {
            "note": "score / class / PASS の履歴。generated_code は持たない。",
            "scoring_version": SCORING_VERSION,
            "runs": runs,
        },
    )
    summary = summarize(runs)
    save_json_file(SUMMARY_PATH, summary)
    return summary


def format_stats(stats):
    total = stats.get("runs") or 0
    passed = stats.get("pass") or 0
    avg = stats.get("avg_score")
    avg_text = "-" if avg is None else f"{avg:g}"
    classes = stats.get("classes") or {}
    class_text = ",".join(
        f"{name}:{count}" for name, count in sorted(classes.items())
    )
    return f"{passed}/{total}  avg {avg_text:>5}  {class_text}"


def format_summary(summary, *, case=None, profile=None):
    lines = [
        f"scoring_version={summary.get('scoring_version')}  runs={summary.get('runs')}"
    ]
    by_case = summary.get("by_case") or {}
    cases = [case] if case else list(by_case)
    lines.append("")
    lines.append("## by case")
    for case_id in cases:
        profiles = by_case.get(case_id) or {}
        if profile:
            profiles = {profile: profiles[profile]} if profile in profiles else {}
        if not profiles:
            continue
        lines.append(case_id)
        width = max((len(name) for name in profiles), default=8)
        for name, stats in profiles.items():
            lines.append(f"  {name:<{width}}  {format_stats(stats)}")
    by_model = summary.get("by_model") or {}
    models = [profile] if profile else list(by_model)
    lines.append("")
    lines.append("## by model")
    for name in models:
        cases = by_model.get(name) or {}
        if case:
            cases = {case: cases[case]} if case in cases else {}
        if not cases:
            continue
        lines.append(name)
        width = max((len(item) for item in cases), default=8)
        for case_id, stats in cases.items():
            lines.append(f"  {case_id:<{width}}  {format_stats(stats)}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="ベンチ履歴をモデル別・ケース別に比較する"
    )
    parser.add_argument("--rebuild", action="store_true", help="results から作り直す")
    parser.add_argument("--case", help="ケース ID で絞る")
    parser.add_argument("--model", dest="profile", help="プロファイル ID で絞る")
    parser.add_argument("--json", action="store_true", help="summary.json を出す")
    args = parser.parse_args(argv)
    if args.rebuild or not SUMMARY_PATH.exists():
        summary = refresh_history()
    else:
        summary = load_json_file(SUMMARY_PATH, {})
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(format_summary(summary, case=args.case, profile=args.profile), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
