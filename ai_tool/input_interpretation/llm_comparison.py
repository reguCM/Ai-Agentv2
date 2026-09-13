"""Model × Input View comparison runner for the isolated playground."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .adapters import LLMLinguaAdapter, RawAdapter, SafeNormalizerAdapter, SudachiAdapter
from .benchmark import LEVELS, evaluate_case, load_cases
from .llm_comparator import OllamaSemanticComparator
from .playground import InputInterpretationPlayground
from .tool_comparison import MODEL_NAME

INPUT_VIEWS = {
    "RAW": ("raw",),
    "RAW_SAFE": ("raw", "safe_normalizer"),
    "RAW_SUDACHI": ("raw", "sudachi"),
    "RAW_SAFE_SUDACHI": ("raw", "safe_normalizer", "sudachi"),
    "RAW_SUDACHI_LLMLINGUA": ("raw", "sudachi", "llmlingua"),
}


def load_compression_diagnostics(path: str | Path | None) -> dict[str, Any]:
    if not path: return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {row["case_id"]: {"llmlingua_critical_loss": row["llmlingua"]["lost_critical_information"], "candidate_is_experimental": True} for row in payload.get("cases", [])}


def _summary(rows: list[dict[str, Any]], calls: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if not row.get("error")]
    by_level = {level: {"passed": sum(row["passed"] for row in valid if row["level"] == level), "total": sum(row["level"] == level for row in valid)} for level in LEVELS}
    types = sorted({row["evaluation_type"] for row in valid})
    by_type = {kind: {"passed": sum(row["passed"] for row in valid if row["evaluation_type"] == kind), "total": sum(row["evaluation_type"] == kind for row in valid)} for kind in types}
    critical_total = sum(sum(item.get("importance") == "CRITICAL" for item in row["rubric"]) for row in valid)
    critical_loss = sum(len(row["critical_losses"]) for row in valid)
    return {
        "passed": sum(row["passed"] for row in valid), "total": len(rows), "errors": len(rows)-len(valid),
        "levels": by_level, "evaluation_types": by_type,
        "critical_preservation": {"preserved": critical_total-critical_loss, "total": critical_total},
        "ambiguity_handling": {"passed": sum(not row["unsafe_overcommit"] for row in valid if row["evaluation_type"] == "HUMAN_ADJUDICATED"), "total": sum(row["evaluation_type"] == "HUMAN_ADJUDICATED" for row in valid)},
        "clarification": {"count": sum(call["needs_clarification"] for call in calls)},
        "unsafe_overcommit": sum(row["unsafe_overcommit"] for row in valid),
        "provisional": sum(row["result"]["request_ir"]["certainty"] == "PROVISIONAL" for row in valid),
        "constraint_loss": sum(not row["meaning_preserved"] for row in valid),
        "latency_ms": round(sum(call["elapsed_ms"] for call in calls), 3),
        "input_tokens_estimated": sum(call["input_tokens_estimated"] for call in calls),
        "output_tokens_estimated": sum(call["output_tokens_estimated"] for call in calls),
        "selected_candidate_sources": dict(Counter(source for call in calls for source in call["selected_candidate_sources"])),
        "none_of_the_above": sum(call["none_of_the_above"] for call in calls),
    }


def _effects(groups: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for model, model_groups in groups.items():
        raw = {row["case_id"]: row for row in model_groups["RAW"]["cases"] if not row.get("error")}
        result[model] = {}
        for view, group in model_groups.items():
            if view == "RAW": continue
            improved, worsened, unchanged = [], [], []
            for row in group["cases"]:
                base = raw.get(row["case_id"])
                if not base or row.get("error"): continue
                target = improved if row["passed"] and not base["passed"] else worsened if base["passed"] and not row["passed"] else unchanged
                target.append(row["case_id"])
            result[model][view] = {"improved": improved, "worsened": worsened, "unchanged": unchanged}
    return result


def run_comparison(*, fixture_path: str | Path, models: list[str], chat_fn, compressor=None, compression_diagnostics=None, checkpoint_path: str | Path | None = None) -> dict[str, Any]:
    cases = load_cases(fixture_path); groups: dict[str, dict[str, Any]] = {}
    started = time.perf_counter()
    adapters = {row.adapter_id: row for row in (RawAdapter(), SafeNormalizerAdapter(), SudachiAdapter(), LLMLinguaAdapter(compressor, rate=0.7, model_name=MODEL_NAME, device="cpu"))}
    for model in models:
        groups[model] = {}
        for view_id, adapter_ids in INPUT_VIEWS.items():
            comparator = OllamaSemanticComparator(chat_fn=chat_fn, model=model, view_id=view_id, candidate_diagnostics=compression_diagnostics)
            engine = InputInterpretationPlayground(adapters=adapters, comparator=comparator)
            rows = []
            groups[model][view_id] = {"cases": rows, "calls": comparator.calls, "summary": None}
            for case in cases:
                selected_case = {**case, "_adapter_ids": adapter_ids}
                try:
                    rows.append(evaluate_case(selected_case, engine))
                except Exception as exc:
                    rows.append({"case_id": case["case_id"], "level": case.get("level", "MICRO"), "evaluation_type": case.get("evaluation_type", "HARD_GOLD"), "passed": False, "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}})
                if checkpoint_path:
                    partial = {"status": "RUNNING", "models": models, "groups": groups, "current": {"model": model, "view": view_id, "case": case["case_id"]}}
                    Path(checkpoint_path).write_text(json.dumps(partial, ensure_ascii=False, indent=2), encoding="utf-8")
            groups[model][view_id]["summary"] = _summary(rows, comparator.calls)
    report = {"status": "COMPLETED", "contract": {"raw_always_present": True, "tool_candidates_not_canonical": True, "llm_output_is_semantic_proposal": True, "gold_not_in_prompt": True}, "models": models, "input_views": {key: list(value) for key,value in INPUT_VIEWS.items()}, "elapsed_ms": round((time.perf_counter()-started)*1000, 3), "groups": groups}
    report["effects_vs_raw"] = _effects(groups)
    if checkpoint_path: Path(checkpoint_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Input Interpretation LLM Comparator A/B", "", "| Model | View | PASS | Micro | Contextual | Realistic | Critical | Unsafe | Constraint loss | Latency ms | Input tok est. | Output tok est. |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for model, views in report["groups"].items():
        for view, group in views.items():
            s=group["summary"]; levels=s["levels"]; critical=s["critical_preservation"]
            lines.append(f"| {model} | {view} | {s['passed']}/{s['total']} | {levels['MICRO']['passed']}/{levels['MICRO']['total']} | {levels['CONTEXTUAL']['passed']}/{levels['CONTEXTUAL']['total']} | {levels['REALISTIC']['passed']}/{levels['REALISTIC']['total']} | {critical['preserved']}/{critical['total']} | {s['unsafe_overcommit']} | {s['constraint_loss']} | {s['latency_ms']:.0f} | {s['input_tokens_estimated']} | {s['output_tokens_estimated']} |")
    lines.extend(["", "## Effects versus RAW", "", "```json", json.dumps(report["effects_vs_raw"], ensure_ascii=False, indent=2), "```", "", "## Representative failures", ""])
    representative = {"context_typo_001", "context_indirect_request_001", "context_negation_scope_001", "context_condition_order_001", "context_dialect_001", "micro_voice_001", "realistic_old_new_instruction_001", "realistic_artifact_review_001"}
    for model, views in report["groups"].items():
        for view, group in views.items():
            for row in group["cases"]:
                if row["case_id"] not in representative or row.get("passed"): continue
                lines.extend([f"### {model} / {view} / {row['case_id']}", "", "```json", json.dumps(row, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Run isolated real-LLM comparator A/B")
    parser.add_argument("--fixture", default="tests/fixtures/input_interpretation"); parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--json", required=True); parser.add_argument("--markdown", required=True)
    parser.add_argument("--compression-report", default="reports/input_interpretation/external_tool_comparison_20260907.json")
    args=parser.parse_args(argv)
    from llmlingua import PromptCompressor  # type: ignore[import-not-found]
    from ollama import Client  # type: ignore[import-not-found]
    compressor=PromptCompressor(model_name=MODEL_NAME, device_map="cpu", use_llmlingua2=True)
    client=Client(timeout=180)
    report=run_comparison(fixture_path=args.fixture, models=args.models, chat_fn=client.chat, compressor=compressor, compression_diagnostics=load_compression_diagnostics(args.compression_report), checkpoint_path=args.json)
    Path(args.markdown).write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status":report["status"],"elapsed_ms":report["elapsed_ms"],"summaries":{m:{v:g["summary"] for v,g in views.items()} for m,views in report["groups"].items()}},ensure_ascii=False,indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
