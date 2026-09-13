"""NH11 shadow gate: LOW / MEDIUM / HIGH / UNKNOWN with structured high_slots."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

NH11 = Path(__file__).resolve().parent
NH10 = NH11.parent / "nh10"
sys.path.insert(0, str(NH10))

from high_slot_gate import build_high_slots  # noqa: E402


def classify_gate_level(base: dict[str, Any], materials: dict[str, Any]) -> dict[str, Any]:
    """Map NH10 HIGH/LOW into NH11 LOW|MEDIUM|HIGH|UNKNOWN without inventing causes."""
    out = dict(base)
    reasons = list(base.get("reasons") or [])
    hs = list(base.get("high_slots") or [])
    runtime = str((materials or {}).get("runtime_log") or "")
    row = str((materials or {}).get("case_trace_row") or "")
    raw = str((materials or {}).get("raw_api_digest") or "")
    missing_ctx = ("実測ログ未提供" in runtime) or (
        raw.strip() in {"", "なし"} and "[OBSERVED]" not in runtime and "stages=" not in runtime
    )
    contradictory = ("矛盾" in runtime) or ("一致しない" in runtime and "小型" not in runtime)

    # Real-log: return count >0 but content empty → confirmation HIGH (not a root-cause claim)
    content_empty = (
        "snippet非空=0" in runtime
        or "内容問題" in runtime
        or ("content_empty=" in row and "content_nonempty=0" in row.replace(" ", ""))
        or ("内容なし件数_return" in row and ",0" not in row)  # weak
    )
    # stronger parse from runtime case_trace line
    if "content_nonempty=0" in runtime.replace(" ", "") or "内容なし" in runtime:
        content_empty = True
    if "content_nonempty=0" in runtime or "snippet非空=0" in runtime or "内容問題" in runtime:
        content_empty = True
        reasons.append("real_log_content_empty_return")
        # attach structured high slots if missing
        have = {x.get("slot") for x in hs}
        for slot, reason in (
            ("stdout_present", "real_log_content_empty_return"),
            ("llm_handoff_present", "real_log_content_empty_return"),
            ("evidence_content_known", "real_log_content_empty_return"),
        ):
            if slot not in have:
                hs.append(
                    {
                        "slot": slot,
                        "reason": reason,
                        "evidence": ["runtime_log", "case_trace_row"],
                        "source": "real_log_rule",
                    }
                )
                have.add(slot)

    # Agent search_web outcome=error in tools_tried
    if "\"outcome\": \"error\"" in runtime or "'outcome': 'error'" in runtime or 'outcome": "error"' in runtime:
        reasons.append("real_log_search_web_error_outcome")
        have = {x.get("slot") for x in hs}
        if "runtime_issue_observed" not in have:
            hs.append(
                {
                    "slot": "runtime_issue_observed",
                    "reason": "real_log_search_web_error_outcome",
                    "evidence": ["runtime_log"],
                    "source": "real_log_rule",
                }
            )

    if missing_ctx and not hs:
        level = "UNKNOWN"
        escalation = "HUMAN_REVIEW"
        reasons = reasons + ["missing_context_P2"]
    elif contradictory and hs:
        level = "UNKNOWN"
        escalation = "HUMAN_REVIEW"
        reasons = reasons + ["contradictory_evidence_P3"]
    elif content_empty and hs:
        level = "HIGH"
        escalation = "LARGE_LLM"
    elif "real_log_search_web_error_outcome" in reasons and hs:
        level = "MEDIUM"
        escalation = "LARGE_LLM"
    elif base.get("level") == "HIGH":
        if base.get("escalation") == "HUMAN_REVIEW" or "sparse_fingerprint_insufficient_info" in reasons:
            level = "HIGH"
            escalation = "HUMAN_REVIEW"
        elif len(hs) <= 2 and any(
            "runtime" in (x.get("slot") or "") or "stdout" in (x.get("slot") or "") for x in hs
        ):
            level = "MEDIUM"
            escalation = "LARGE_LLM"
        else:
            level = "HIGH"
            escalation = base.get("escalation") or "LARGE_LLM"
    else:
        level = "LOW"
        escalation = "NONE"

    # dedupe high slots
    seen: set[str] = set()
    uniq_hs = []
    for it in hs:
        s = it.get("slot")
        if s in seen:
            continue
        seen.add(s)
        uniq_hs.append(it)

    out["level"] = level
    out["escalation"] = escalation
    out["reasons"] = list(dict.fromkeys(reasons))
    out["high_slots"] = uniq_hs
    out["high_slot_names"] = [x["slot"] for x in uniq_hs]
    out["auto_fix_allowed"] = False
    return out

def evaluate_shadow_gate(
    *,
    slots: dict[str, Any],
    materials: dict[str, Any],
    mapped: dict[str, Any] | None = None,
    prefill_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = build_high_slots(
        slots=slots,
        materials=materials,
        mapped=mapped,
        prefill_meta=prefill_meta,
    )
    return classify_gate_level(base, materials)
