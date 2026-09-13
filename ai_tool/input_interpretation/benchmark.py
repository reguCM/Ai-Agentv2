"""Layered black-box acceptance and white-box diagnostic benchmark."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from .playground import InputInterpretationPlayground, conservative_compaction_candidates
from .schema import EvaluationType, RequirementImportance

LEVELS = ("MICRO", "CONTEXTUAL", "REALISTIC")
WEIGHTS = {"CRITICAL": 8.0, "MAJOR": 4.0, "MINOR": 2.0, "OPTIONAL": 1.0}


def _contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and _contains(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and all(any(_contains(item, wanted) for item in actual) for wanted in expected)
    return actual == expected


def _field(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _rubric_items(case: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(case.get("rubric", []))
    rows.extend({**row, "importance": "CRITICAL"} for row in case.get("critical_requirements", []))
    if not rows and case.get("expected_request_ir"):
        rows.append({"field": "request_ir", "expected": case["expected_request_ir"], "importance": "MAJOR", "weight": 1})
    return rows


def evaluate_case(case: dict[str, Any], playground: InputInterpretationPlayground | None = None) -> dict[str, Any]:
    engine = playground or InputInterpretationPlayground()
    result = engine.interpret(case["input"], profile_id=case.get("profile_id", "all"), input_id=case["case_id"], adapter_ids=case.get("_adapter_ids"))
    result.compaction.extend(conservative_compaction_candidates(result.semantic_selection.interpreted_text, input_id=result.envelope.input_id))
    actual_ir = asdict(result.request_ir)
    actual = {"request_ir": actual_ir, "semantic_selection": asdict(result.semantic_selection)}
    evaluation_type = case.get("evaluation_type", EvaluationType.HARD_GOLD.value)
    expected = case.get("expected_request_ir", {})
    acceptable = case.get("acceptable_interpretations", [])
    forbidden = case.get("forbidden_interpretations", [])
    acceptable_match = (
        any(_contains(actual_ir, row) for row in acceptable)
        if evaluation_type == EvaluationType.ACCEPTABLE_SET.value
        else _contains(actual_ir, expected)
    )
    forbidden_hits = [row for row in forbidden if _contains(actual_ir, row)]
    rubric_rows, earned, possible, critical_losses = [], 0.0, 0.0, []
    for requirement in _rubric_items(case):
        importance = requirement.get("importance", RequirementImportance.MAJOR.value)
        weight = float(requirement.get("weight", WEIGHTS.get(importance, 1.0)))
        observed = _field(actual, requirement["field"])
        matched = _contains(observed, requirement.get("expected"))
        possible += weight
        if matched: earned += weight
        elif importance == RequirementImportance.CRITICAL.value: critical_losses.append(requirement["field"])
        rubric_rows.append({**requirement, "actual": observed, "matched": matched, "weighted_score": weight if matched else 0.0})
    clarification_expected = case.get("clarification_expected")
    clarification_ok = clarification_expected is None or result.request_ir.needs_clarification is bool(clarification_expected)
    provisional_expected = case.get("provisional_expected")
    provisional_ok = provisional_expected is None or (result.request_ir.certainty == "PROVISIONAL") is bool(provisional_expected)
    unsafe_overcommit = bool(
        forbidden_hits
        or (clarification_expected is True and not result.request_ir.needs_clarification)
        or (result.request_ir.certainty == "KNOWN" and case.get("gold_certainty") in {"AMBIGUOUS", "UNKNOWN", "PROVISIONAL"})
    )
    checks = {
        "acceptable_interpretation": acceptable_match,
        "clarification_decision": clarification_ok,
        "provisional_handling": provisional_ok,
        "constraint_preservation": all(value in actual_ir["constraints"] for value in case.get("must_preserve_constraints", [])),
        "negation_preservation": all(value in actual_ir["negations"] for value in case.get("must_preserve_negations", [])),
        "execution_order_preservation": _contains(actual_ir["operation_order"], case.get("expected_operation_order", [])),
        "false_removal": not any(value in result.semantic_selection.interpreted_text for value in case.get("must_remove", [])),
        "redundancy_removal": any(row.action == "SUPPRESS" for row in result.compaction) if case.get("expects_redundancy") else True,
    }
    meaning_preserved = all(checks[key] for key in ("constraint_preservation", "negation_preservation", "execution_order_preservation")) and not critical_losses
    score = 1.0 if possible == 0 and acceptable_match else (earned / possible if possible else 0.0)
    passed = all(checks.values()) and meaning_preserved and not unsafe_overcommit
    if evaluation_type == EvaluationType.RUBRIC.value:
        passed = passed and score >= float(case.get("pass_score", 0.7))
    if evaluation_type == EvaluationType.HUMAN_ADJUDICATED.value:
        passed = clarification_ok and provisional_ok and not unsafe_overcommit and not critical_losses
    return {
        "case_id": case["case_id"], "level": case.get("level", "MICRO"), "pair_id": case.get("pair_id"),
        "evaluation_type": evaluation_type, "input": case["input"], "expected_request_ir": expected,
        "result": result.as_dict(), "checks": checks, "rubric": rubric_rows, "score": round(score, 4),
        "critical_losses": critical_losses, "forbidden_hits": forbidden_hits,
        "unsafe_overcommit": unsafe_overcommit, "meaning_preserved": meaning_preserved, "passed": passed,
        "clarification_evaluated": clarification_expected is not None,
        "provisional_evaluated": provisional_expected is not None,
        "diagnostic_stage": "EVALUATION" if not passed else None,
    }


def load_cases(fixture_path: str | Path) -> list[dict[str, Any]]:
    path = Path(fixture_path)
    paths = sorted(path.glob("*.json")) if path.is_dir() else [path]
    cases: list[dict[str, Any]] = []
    for item in paths:
        payload = json.loads(item.read_text(encoding="utf-8"))
        cases.extend(payload["cases"] if isinstance(payload, dict) else payload)
    ids = [row["case_id"] for row in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark case_id must be unique")
    return cases


def _rate(rows: Iterable[dict[str, Any]], predicate) -> dict[str, Any]:
    selected = list(rows)
    return {"passed": sum(bool(predicate(row)) for row in selected), "total": len(selected), "rate": round(sum(bool(predicate(row)) for row in selected) / len(selected), 4) if selected else None}


def run_benchmark(fixture_path: str | Path, *, playground=None) -> dict[str, Any]:
    rows = [evaluate_case(case, playground) for case in load_cases(fixture_path)]
    level_scores = {level: _rate((row for row in rows if row["level"] == level), lambda row: row["passed"]) for level in LEVELS}
    type_counts = Counter(row["evaluation_type"] for row in rows)
    type_scores = {kind: _rate((row for row in rows if row["evaluation_type"] == kind), lambda row: row["passed"]) for kind in EvaluationType._value2member_map_}
    critical_total = sum(sum(item.get("importance") == "CRITICAL" for item in row["rubric"]) for row in rows)
    critical_losses = sum(len(row["critical_losses"]) for row in rows)
    metrics = {
        "micro_diagnostic": level_scores["MICRO"], "contextual_japanese": level_scores["CONTEXTUAL"], "realistic_agent": level_scores["REALISTIC"],
        "hard_gold_accuracy": type_scores["HARD_GOLD"],
        "critical_preservation": {"preserved": critical_total - critical_losses, "total": critical_total, "rate": round((critical_total - critical_losses) / critical_total, 4) if critical_total else None},
        "acceptable_interpretation": _rate(rows, lambda row: row["checks"]["acceptable_interpretation"]),
        "ambiguity_handling": _rate((row for row in rows if row["evaluation_type"] == "HUMAN_ADJUDICATED"), lambda row: not row["unsafe_overcommit"]),
        "clarification_decision": _rate((row for row in rows if row["clarification_evaluated"]), lambda row: row["checks"]["clarification_decision"]),
        "unsafe_overcommit_count": sum(bool(row["unsafe_overcommit"]) for row in rows),
        "provisional_handling": _rate((row for row in rows if row["provisional_evaluated"]), lambda row: row["checks"]["provisional_handling"]),
        "prompt_reduction_average": round(sum(row["result"]["metrics"]["reduction_ratio"] for row in rows) / len(rows), 4) if rows else None,
        "constraint_loss_count": sum(not row["meaning_preserved"] for row in rows),
    }
    return {"case_count": len(rows), "passed": sum(bool(row["passed"]) for row in rows), "failed": sum(not row["passed"] for row in rows), "level_scores": level_scores, "evaluation_type_counts": dict(type_counts), "evaluation_type_scores": type_scores, "capability_metrics": metrics, "cases": rows}


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Input Interpretation Benchmark", "", f"PASS: {report['passed']} / {report['case_count']}", "", "## Capability scores", ""]
    for name, metric in report["capability_metrics"].items():
        lines.append(f"- {name}: {json.dumps(metric, ensure_ascii=False)}")
    lines.extend(["", "| Level | Case | Evaluation | Result | Score | Certainty | Critical loss | Reduction | Availability |", "|---|---|---|---|---:|---|---|---:|---|"])
    for row in report["cases"]:
        result = row["result"]
        availability = ", ".join(item["adapter_id"] + "=" + item["availability"] for item in result["adapter_executions"])
        lines.append(f"| {row['level']} | {row['case_id']} | {row['evaluation_type']} | {'PASS' if row['passed'] else 'FAIL'} | {row['score']:.0%} | {result['request_ir']['certainty']} | {', '.join(row['critical_losses']) or '-'} | {result['metrics']['reduction_ratio']:.1%} | {availability} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run isolated Input Interpretation benchmark")
    parser.add_argument("fixture", nargs="?", default="tests/fixtures/input_interpretation")
    parser.add_argument("--json", dest="json_path"); parser.add_argument("--markdown", dest="markdown_path")
    args = parser.parse_args(argv); report = run_benchmark(args.fixture)
    if args.json_path: Path(args.json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_markdown(report)
    if args.markdown_path: Path(args.markdown_path).write_text(markdown, encoding="utf-8")
    print(markdown, end=""); return 0 if report["failed"] == 0 else 1

if __name__ == "__main__": raise SystemExit(main())
