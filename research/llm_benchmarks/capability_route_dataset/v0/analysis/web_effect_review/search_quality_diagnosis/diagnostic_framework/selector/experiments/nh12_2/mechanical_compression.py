"""NH12-2 mechanical log compression — observation facts only, no cause inference."""

from __future__ import annotations

import json
import re
from typing import Any

COMPRESSION_SLOTS = [
    "runtime",
    "tool",
    "search",
    "ranking",
    "evidence",
    "state",
    "error",
    "output",
    "code_path",
    "timestamp",
]

# status: FACT | PRESENT | ABSENT | UNKNOWN


def slot(value: Any, status: str, source: str, confidence: str = "high") -> dict[str, Any]:
    return {"value": value, "status": status, "source": source, "confidence": confidence}


def empty_unknown(source: str = "compression") -> dict[str, Any]:
    return slot(None, "UNKNOWN", source, "low")


def parse_stages(runtime: str) -> dict[str, Any]:
    m = re.search(r"stages=(\{[^}]+\})", runtime)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def parse_tools_tried(runtime: str) -> list[dict[str, Any]]:
    m = re.search(r"agent_tools_tried=(\[[\s\S]*?\])\n", runtime + "\n")
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return []


def parse_case_trace_row(row: str) -> dict[str, str]:
    if not row or row == "なし":
        return {}
    # key=value pairs from observed line
    out: dict[str, str] = {}
    for part in re.findall(r"(\w+)=([^\s,]+)", row.replace(" ", "")):
        out[part[0]] = part[1]
    if "return" in row:
        m = re.search(r"return=(\d+)", row.replace(" ", ""))
        if m:
            out["return_count"] = m.group(1)
        m = re.search(r"content_nonempty=(\d+)", row.replace(" ", ""))
        if m:
            out["content_nonempty"] = m.group(1)
        m = re.search(r"content_empty=(\d+)", row.replace(" ", ""))
        if m:
            out["content_empty"] = m.group(1)
    return out


def compress_materials(materials: dict[str, Any]) -> dict[str, Any]:
    """Mechanically compress case materials into fixed slots. No cause inference."""
    runtime = str(materials.get("runtime_log") or "")
    raw = str(materials.get("raw_api_digest") or "")
    code = str(materials.get("code_excerpt") or "")
    state = str(materials.get("state_context") or "")
    row_s = str(materials.get("case_trace_row") or "")
    gaps = list(materials.get("material_gaps") or [])

    slots: dict[str, dict[str, Any]] = {}
    omissions: list[str] = []
    facts: list[str] = []

    # runtime
    if "[OBSERVED]" in runtime:
        slots["runtime"] = slot(True, "PRESENT", "runtime_log")
        facts.append("runtime_log_has_observed_lines")
    elif "なし" in runtime or "未提供" in runtime:
        slots["runtime"] = slot(False, "ABSENT", "runtime_log")
    else:
        slots["runtime"] = empty_unknown("runtime_log")

    # tool
    tools = parse_tools_tried(runtime)
    if tools:
        names = [t.get("tool") for t in tools if t.get("tool")]
        slots["tool"] = slot(
            {"tools": names, "count": len(tools)},
            "FACT",
            "runtime_log.agent_tools_tried",
        )
        facts.append("tool_list_extracted")
    elif "tool_call" in runtime.lower():
        slots["tool"] = slot("search_web", "PRESENT", "runtime_log.execution_identity")
    else:
        slots["tool"] = empty_unknown("runtime_log")

    # search
    search_info: dict[str, Any] = {}
    for t in tools:
        if t.get("tool") == "search_web":
            search_info["outcome"] = t.get("outcome")
            search_info["hit_count"] = t.get("hit_count")
            search_info["error"] = t.get("error")
            ap = t.get("args_preview")
            if ap:
                try:
                    search_info["args"] = json.loads(ap) if isinstance(ap, str) else ap
                except json.JSONDecodeError:
                    search_info["args_preview"] = str(ap)[:200]
    stages = parse_stages(runtime)
    if stages:
        search_info["api_raw_total"] = stages.get("api_raw_total")
        search_info["search_web_return"] = stages.get("search_web_return")
    if search_info:
        slots["search"] = slot(search_info, "FACT", "runtime_log")
        facts.append("search_metrics_extracted")
    else:
        slots["search"] = empty_unknown("runtime_log")

    # ranking
    ranking_info: dict[str, Any] = {}
    if stages:
        for k in (
            "hit_accepted_before_unique",
            "hit_after_unique",
            "after_ranking",
            "search_web_return",
        ):
            if k in stages:
                ranking_info[k] = stages[k]
    row = parse_case_trace_row(row_s)
    if row:
        for k in ("API生件数", "ranking後", "return_count", "content_nonempty", "content_empty"):
            if k in row:
                ranking_info[k] = row[k]
    if "ranking" in runtime.lower() or ranking_info:
        slots["ranking"] = slot(ranking_info or True, "PRESENT" if ranking_info else "PRESENT", "runtime_log|case_trace")
        facts.append("ranking_data_present")
    else:
        slots["ranking"] = empty_unknown("runtime_log|case_trace")

    # evidence
    if raw.strip() not in {"", "なし"}:
        slots["evidence"] = slot("digest_present", "PRESENT", "raw_api_digest")
        facts.append("raw_api_digest_present")
    elif "evidence" in state.lower():
        slots["evidence"] = slot(False, "ABSENT", "state_context")
    else:
        slots["evidence"] = empty_unknown("raw_api_digest")

    # state
    if "変更要求はない" in state or "変更なし" in state:
        slots["state"] = slot(False, "FACT", "state_context")
    elif "変更" in state:
        slots["state"] = slot(True, "PRESENT", "state_context")
    else:
        slots["state"] = empty_unknown("state_context")

    # error
    err: dict[str, Any] = {}
    if any(t.get("outcome") == "error" for t in tools):
        err["search_web_error"] = True
        err["messages"] = [t.get("error") for t in tools if t.get("error")]
    if "exception" in runtime.lower() or "traceback" in runtime.lower():
        err["runtime_exception"] = True
    if "timeout" in runtime.lower():
        err["timeout"] = True
    if err:
        slots["error"] = slot(err, "FACT", "runtime_log")
        facts.append("error_observed")
    else:
        slots["error"] = slot(False, "ABSENT", "runtime_log")

    # output / handoff
    out_info: dict[str, Any] = {}
    if stages:
        for k in ("llm_handoff_live_return", "llm_handoff_stored_log", "content_nonempty_in_return"):
            if k in stages:
                out_info[k] = stages[k]
    if "handoff" in code.lower() or out_info:
        slots["output"] = slot(out_info or "handoff_mentioned_in_code", "PRESENT", "stages|code_excerpt")
    elif runtime:
        slots["output"] = empty_unknown("stages")
    else:
        slots["output"] = empty_unknown("stages")

    # code_path
    if code.strip() and not code.startswith("なし"):
        slots["code_path"] = slot(True, "PRESENT", "code_excerpt")
        facts.append("code_excerpt_present")
    else:
        slots["code_path"] = empty_unknown("code_excerpt")

    # timestamp
    ts_matches = re.findall(r'"ts":\s*"([^"]+)"', runtime)
    if ts_matches:
        slots["timestamp"] = slot(ts_matches[0], "FACT", "execution_identity")
        facts.append("timestamp_extracted")
    else:
        slots["timestamp"] = empty_unknown("execution_identity")

    # material shortage heuristic (compression layer view)
    known_slots = sum(1 for s in slots.values() if s["status"] != "UNKNOWN")
    coverage = round(known_slots / len(COMPRESSION_SLOTS), 4)
    # shortage: core diagnostic slots all unknown (compression could not extract)
    core_unknown = all(
        slots.get(k, {}).get("status") == "UNKNOWN" for k in ("runtime", "tool", "search")
    )
    material_shortage = core_unknown

    if not tools and not stages and raw.strip() in {"", "なし"}:
        omissions.append("F1_compression_omission:no_tools_no_stages")
    if gaps:
        omissions.extend([f"F5_material_gap:{g}" for g in gaps])

    return {
        "compression_slots": slots,
        "facts_extracted": facts,
        "omissions": omissions,
        "slot_coverage": coverage,
        "unknown_count": sum(1 for s in slots.values() if s["status"] == "UNKNOWN"),
        "material_shortage": material_shortage,
        "no_cause_inference": True,
    }


def compression_to_prompt_block(compressed: dict[str, Any]) -> str:
    """Format compressed slots for Observation LLM input."""
    lines = ["## Mechanical Compression (pre-LLM, no cause inference)", ""]
    for name in COMPRESSION_SLOTS:
        s = compressed["compression_slots"].get(name) or empty_unknown()
        lines.append(
            f"- {name}: status={s['status']} value={json.dumps(s.get('value'), ensure_ascii=False)} "
            f"source={s.get('source')} confidence={s.get('confidence')}"
        )
    lines.append(f"\nSlot coverage: {compressed.get('slot_coverage')}")
    lines.append(f"Material shortage (compression view): {compressed.get('material_shortage')}")
    return "\n".join(lines)
