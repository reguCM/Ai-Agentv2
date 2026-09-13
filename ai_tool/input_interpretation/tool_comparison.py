"""External-tool comparison report; separate from RequestIR benchmark scoring."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from .adapters import LLMLinguaAdapter, RawAdapter, SafeNormalizerAdapter, SudachiAdapter
from .benchmark import evaluate_case, load_cases
from .playground import InputInterpretationPlayground

MODEL_NAME = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
DETAIL_CASES = {
    "micro_typo_001", "context_typo_001", "micro_voice_001", "context_dialect_001",
    "context_negation_scope_001", "context_condition_order_001", "realistic_artifact_review_001",
}


def _rss_bytes() -> int | None:
    try:
        import psutil  # type: ignore[import-not-found]
        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        return None


def _critical_fragments(case: dict[str, Any], raw: str, protected: list[dict[str, Any]]) -> list[str]:
    fragments = [row["text"] for row in protected]
    fragments.extend(case.get("must_preserve_constraints", [])); fragments.extend(case.get("must_preserve_negations", []))
    for clause in raw.replace("\n", "。").split("。"):
        if clause and any(mark in clause for mark in ("ない", "せず", "禁止", "ただし", "場合", "最初", "その後")):
            fragments.append(clause.strip())
    return list(dict.fromkeys(value for value in fragments if value))


def _model_cache_size(model_name: str) -> int | None:
    folder = Path.home() / ".cache" / "huggingface" / "hub" / ("models--" + model_name.replace("/", "--"))
    if not folder.exists(): return None
    try: return sum(item.stat().st_size for item in folder.rglob("*") if item.is_file())
    except OSError: return None


def run_tool_comparison(fixture_path: str | Path, *, compressor=None, model_name: str = MODEL_NAME, rate: float = 0.7, setup_resources: dict[str, Any] | None = None) -> dict[str, Any]:
    adapters = [RawAdapter(), SafeNormalizerAdapter(), SudachiAdapter(), LLMLinguaAdapter(compressor, rate=rate, model_name=model_name, device="cpu")]
    engine = InputInterpretationPlayground(adapters={row.adapter_id: row for row in adapters})
    process_started = time.perf_counter(); cpu_started = time.process_time(); rss_before = _rss_bytes()
    rows = []
    for case in load_cases(fixture_path):
        evaluated = evaluate_case(case, engine)
        result = evaluated["result"]
        executions = {row["adapter_id"]: row for row in result["adapter_executions"]}
        llm_candidates = executions["llmlingua"]["candidates"]
        compressed = llm_candidates[0]["text"] if llm_candidates else None
        fragments = _critical_fragments(case, case["input"], result["envelope"]["protected_spans"])
        preserved = {fragment: bool(compressed is not None and fragment in compressed) for fragment in fragments}
        sudachi_candidates = executions["sudachi"]["candidates"]
        rows.append({
            "case_id": case["case_id"], "level": case.get("level", "MICRO"), "pair_id": case.get("pair_id"),
            "detailed": case["case_id"] in DETAIL_CASES, "raw": case["input"],
            "safe_normalizer": executions["safe_normalizer"],
            "sudachi": {"availability": executions["sudachi"]["availability"], "latency_ms": executions["sudachi"]["latency_ms"], "detail": executions["sudachi"]["detail"], "tokens": sudachi_candidates[0]["provenance"].get("analysis", []) if sudachi_candidates else []},
            "llmlingua": {"availability": executions["llmlingua"]["availability"], "latency_ms": executions["llmlingua"]["latency_ms"], "detail": executions["llmlingua"]["detail"], "compressed_text": compressed, "provenance": llm_candidates[0]["provenance"] if llm_candidates else {}, "critical_preservation": preserved, "lost_critical_information": [key for key, kept in preserved.items() if not kept]},
            "baseline_semantic_result": result["request_ir"],
            "expected_or_rubric": {key: case.get(key) for key in ("evaluation_type", "expected_request_ir", "acceptable_interpretations", "rubric", "critical_requirements") if case.get(key)},
            "request_ir_benchmark": {"passed": evaluated["passed"], "score": evaluated["score"], "separate_from_tool_output_quality": True},
        })
    rss_after = _rss_bytes()
    origin_tokens = [row["llmlingua"]["provenance"].get("origin_tokens") for row in rows if row["llmlingua"]["provenance"].get("origin_tokens") is not None]
    compressed_tokens = [row["llmlingua"]["provenance"].get("compressed_tokens") for row in rows if row["llmlingua"]["provenance"].get("compressed_tokens") is not None]
    elapsed_ms = round((time.perf_counter() - process_started) * 1000, 3)
    cpu_ms = round((time.process_time() - cpu_started) * 1000, 3)
    return {
        "report_contract": {"tool_output_quality_is_not_request_ir_success": True, "raw_is_canonical_input": True, "compression_is_candidate_only": True},
        "environment": {"python": os.sys.version.split()[0], "model_name": model_name, "model_cache_bytes": _model_cache_size(model_name), "device": "cpu", "gpu_used": False},
        "resources": {"model_setup": dict(setup_resources or {}), "elapsed_ms": elapsed_ms, "process_cpu_ms": cpu_ms, "average_process_cpu_percent": round(cpu_ms / elapsed_ms * 100, 2) if elapsed_ms else None, "rss_before_bytes": rss_before, "rss_after_bytes": rss_after, "rss_delta_bytes": None if rss_before is None or rss_after is None else rss_after-rss_before},
        "tool_output_quality": {
            "sudachi_available_cases": sum(row["sudachi"]["availability"] == "AVAILABLE" for row in rows),
            "sudachi_average_latency_ms": round(sum(row["sudachi"]["latency_ms"] for row in rows) / len(rows), 3) if rows else None,
            "llmlingua_available_cases": sum(row["llmlingua"]["availability"] == "AVAILABLE" for row in rows),
            "llmlingua_average_latency_ms": round(sum(row["llmlingua"]["latency_ms"] for row in rows) / len(rows), 3) if rows else None,
            "origin_tokens": sum(origin_tokens), "compressed_tokens": sum(compressed_tokens),
            "token_reduction_ratio": round(1 - sum(compressed_tokens) / sum(origin_tokens), 4) if origin_tokens and sum(origin_tokens) else None,
            "cases_with_critical_loss": sum(bool(row["llmlingua"]["lost_critical_information"]) for row in rows),
        },
        "case_count": len(rows), "cases": rows,
    }


def render_tool_comparison_markdown(report: dict[str, Any]) -> str:
    env, resource = report["environment"], report["resources"]
    quality = report["tool_output_quality"]
    reduction = "NOT_EVALUATED" if quality["token_reduction_ratio"] is None else f"{quality['token_reduction_ratio']:.1%}"
    lines = ["# Input Interpretation External Tool Comparison", "", "## Separation", "", "- TOOL_OUTPUT_QUALITY is diagnostic only.", "- REQUEST_IR_BENCHMARK is scored separately.", "- Sudachi / LLMLingua output is not Canonical Truth.", "", "## Environment / resource", "", f"- Model: {env['model_name']}", f"- Device: {env['device']} (GPU used: {env['gpu_used']})", f"- Model cache bytes: {env['model_cache_bytes']}", f"- Model setup: {json.dumps(resource['model_setup'], ensure_ascii=False)}", f"- Total elapsed ms: {resource['elapsed_ms']}", f"- Process CPU ms: {resource['process_cpu_ms']}", f"- Average process CPU percent: {resource['average_process_cpu_percent']}", f"- RSS delta bytes: {resource['rss_delta_bytes']}", "", "## Tool output quality", "", f"- Sudachi available: {quality['sudachi_available_cases']} / {report['case_count']}", f"- Sudachi average latency ms: {quality['sudachi_average_latency_ms']}", f"- LLMLingua available: {quality['llmlingua_available_cases']} / {report['case_count']}", f"- LLMLingua average latency ms: {quality['llmlingua_average_latency_ms']}", f"- Token reduction: {quality['origin_tokens']} → {quality['compressed_tokens']} ({reduction})", f"- Cases with critical loss: {quality['cases_with_critical_loss']}", "", "## Cases", ""]
    for row in report["cases"]:
        if not row["detailed"]: continue
        lines.extend([f"### {row['case_id']}", "", "**RAW**", "", row["raw"], "", "**Safe Normalizer**", "", row["safe_normalizer"]["candidates"][0]["text"], "", "**Sudachi tokens**", "", "```json", json.dumps(row["sudachi"]["tokens"], ensure_ascii=False, indent=2), "```", "", "**LLMLingua**", "", str(row["llmlingua"]["compressed_text"]), "", f"Lost critical information: {row['llmlingua']['lost_critical_information']}", "", "**Baseline Semantic / Expected**", "", "```json", json.dumps({"baseline": row["baseline_semantic_result"], "expected": row["expected_or_rubric"], "request_ir_benchmark": row["request_ir_benchmark"]}, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare optional input interpretation tools")
    parser.add_argument("fixture", nargs="?", default="tests/fixtures/input_interpretation")
    parser.add_argument("--json", required=True); parser.add_argument("--markdown", required=True)
    parser.add_argument("--model", default=MODEL_NAME); parser.add_argument("--rate", type=float, default=0.7)
    args = parser.parse_args(argv)
    from llmlingua import PromptCompressor  # type: ignore[import-not-found]
    setup_started = time.perf_counter(); setup_cpu = time.process_time(); setup_rss = _rss_bytes()
    compressor = PromptCompressor(model_name=args.model, device_map="cpu", use_llmlingua2=True)
    setup_after = _rss_bytes()
    setup = {"elapsed_ms": round((time.perf_counter()-setup_started)*1000, 3), "process_cpu_ms": round((time.process_time()-setup_cpu)*1000, 3), "rss_delta_bytes": None if setup_rss is None or setup_after is None else setup_after-setup_rss}
    report = run_tool_comparison(args.fixture, compressor=compressor, model_name=args.model, rate=args.rate, setup_resources=setup)
    Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.markdown).write_text(render_tool_comparison_markdown(report), encoding="utf-8")
    print(json.dumps({"case_count": report["case_count"], "resources": report["resources"], "environment": report["environment"]}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
