"""Validation Gate: connect hidden_eval / contract to stage progression.

Evaluator-only. Hidden adopted text must never be sent to Local.
Does not key routing off decision_id allowlists.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BENCH = REPO / "research" / "llm_benchmarks" / "h4_decision_maker_bench"
if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))

from adoption_gate import _negated_at  # noqa: E402

HIDDEN_PATH = BENCH / "packets" / "hidden_eval.json"


def load_hidden(path: Path | None = None) -> dict[str, Any]:
    raw = json.loads((path or HIDDEN_PATH).read_text(encoding="utf-8"))
    return raw.get("items") or {}


def _unnegated(rec: str, pattern: str) -> bool:
    m = re.search(pattern, rec, flags=re.I | re.S)
    return bool(m) and not _negated_at(rec, m.start())


def danger_synonym_patterns(danger: str) -> list[str]:
    """Expand danger_if text into adopt-patterns. Not a Q-number map."""
    d = str(danger)
    low = d.lower()
    out: list[str] = []
    if "confirm web" in low or ("web" in low and "検索" in d):
        out.extend(
            [
                r"prefer adding to web_search",
                r"prefer .{0,24}to web_search",
                r"検索.{0,24}web を足",
            ]
        )
    if "inject first of multiple" in low:
        out.extend([r"inject only\s*\[\s*0\s*\]", r"inject first"])
    if "fold 2+" in low or "fold 2 +" in low:
        out.append(r"fold\s+2\s*\+?\s*into\s+first")
    if re.search(r"\[0\]", d) and "select" in low:
        out.append(r"select first candidate")
    # Literal danger string, escaped, if it can appear in English recs.
    lit = re.escape(d.strip())
    if len(d.strip()) >= 8:
        out.append(lit)
    return out


def adopts_danger_if(rec: str, danger_if: list[Any]) -> list[str]:
    hits: list[str] = []
    rec = str(rec or "")
    for item in danger_if or []:
        key = str(item)
        for pat in danger_synonym_patterns(key):
            if _unnegated(rec, pat):
                hits.append(key)
                break
    return hits


def adopts_rejected_pole(rec: str, rejected: list[Any]) -> list[str]:
    hits: list[str] = []
    rec = str(rec or "")
    for alt in rejected or []:
        text = str(alt)
        low = text.lower()
        if "prefer" in low or "prefer" in text:
            if _unnegated(rec, r"prefer adding|\bprefer\b.{0,24}to web_search|片方へ prefer"):
                hits.append(text)
                continue
        if len(text.strip()) >= 6 and _unnegated(rec, re.escape(text.strip())):
            hits.append(text)
    return hits


def hidden_contract_eval(
    *,
    rec: str,
    route: str,
    eval_item: dict[str, Any] | None,
) -> dict[str, Any]:
    item = eval_item or {}
    danger_hits = adopts_danger_if(rec, item.get("danger_if") or [])
    rejected_hits = adopts_rejected_pole(rec, item.get("rejected") or [])
    flags = []
    if danger_hits:
        flags.append("adopts_danger_if")
    if rejected_hits:
        flags.append("adopts_rejected_alternative")
    false_auto = route == "AUTO" and bool(flags)
    return {
        "false_auto": false_auto,
        "flags": flags,
        "danger_hits": danger_hits,
        "rejected_hits": rejected_hits,
        "adopted_contract": item.get("adopted"),
        "hidden_used_for": "evaluator_confirm_only",
    }


def attach_hidden_eval(records: list[dict[str, Any]], hidden_items: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    items = hidden_items if hidden_items is not None else load_hidden()
    out: list[dict[str, Any]] = []
    for rec in records:
        did = str(rec.get("decision_id") or "")
        ev = hidden_contract_eval(
            rec=str(rec.get("first_recommendation") or ""),
            route=str(rec.get("route") or ""),
            eval_item=items.get(did) or {},
        )
        row = dict(rec)
        row["contract_eval"] = ev
        out.append(row)
    return out


def confirm_records(
    result: dict[str, Any],
    *,
    n: int | None = None,
    forbid_human: bool = True,
    forbid_false_auto: bool = True,
    require_auto: tuple[str, ...] = (),
    forbid_auto: tuple[str, ...] = (),
    require_ids: tuple[str, ...] | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    records = attach_hidden_eval(result.get("records") or [])
    summary = result.get("summary") or {}
    if n is not None and (summary.get("n") != n or len(records) != n):
        reasons.append(f"expected n={n}, got summary={summary.get('n')} records={len(records)}")
    if summary.get("parse_failure") or summary.get("missing_output"):
        reasons.append("parse/output missing")
    if forbid_human and summary.get("HUMAN"):
        reasons.append("unexpected HUMAN")
    if require_ids is not None and {r["decision_id"] for r in records} != set(require_ids):
        reasons.append("id set mismatch")
    by_id = {str(r["decision_id"]): r for r in records}
    if forbid_false_auto:
        for rec in records:
            ev = rec.get("contract_eval") or {}
            if ev.get("false_auto"):
                reasons.append(
                    f"false AUTO vs contract {rec.get('decision_id')} flags={ev.get('flags')}"
                )
    for did in require_auto:
        if did not in by_id:
            continue
        if by_id[did].get("route") != "AUTO":
            reasons.append(f"true AUTO regression {did} -> {by_id[did].get('route')}")
    for did in forbid_auto:
        if did not in by_id:
            continue
        if by_id[did].get("route") == "AUTO":
            reasons.append(f"must not AUTO {did}")
    return (not reasons), reasons
