"""User-facing decision support presentation — material, not mechanical winner."""
from __future__ import annotations

from typing import Any


def format_candidate_decision_block(
    candidate: dict[str, Any],
    factors: list[dict[str, Any]],
) -> str:
    """Format one candidate for user review."""
    lines = [f"### {candidate.get('name')} ({candidate.get('candidate_id')})"]
    lines.append(f"- Type: {candidate.get('type')}")
    lines.append(f"- Version: {candidate.get('version', 'UNKNOWN')}")
    lines.append(f"- License: {candidate.get('license', 'UNKNOWN')}")

    reasons = [f for f in factors if f.get("status") in ("match", "partial")]
    if reasons:
        lines.append("理由:")
        for f in reasons[:5]:
            lines.append(f"  - {f.get('factor')}: {f.get('detail')}")

    unknowns = candidate.get("unknowns") or []
    if unknowns:
        lines.append("不明:")
        for u in unknowns:
            lines.append(f"  - {u}")

    conflicts = candidate.get("conflicts") or []
    if conflicts:
        lines.append("競合/差異 (保持):")
        for c in conflicts[:3]:
            lines.append(f"  - {c.get('note', c)}")

    lines.append("出典:")
    lines.append(f"  - [{candidate.get('source_category')}] {candidate.get('source_title')}")
    if candidate.get("url"):
        lines.append(f"    {candidate.get('url')}")
    return "\n".join(lines)


def format_decision_comparison(
    candidates: list[dict[str, Any]],
    factors_by_candidate: dict[str, list[dict[str, Any]]],
) -> str:
    """Side-by-side narrative — only when multiple real candidates exist."""
    real = [c for c in candidates if c.get("type") != "Custom Build"]
    if not real and not candidates:
        return "候補なし — RESEARCH_NOT_REQUIRED または Evidence 未収集"
    if len(real) < 2:
        chosen = real[0] if real else candidates[0]
        cid = str(chosen.get("candidate_id"))
        return format_candidate_decision_block(chosen, factors_by_candidate.get(cid, []))

    blocks = []
    for c in real[:3]:
        cid = str(c.get("candidate_id"))
        blocks.append(format_candidate_decision_block(c, factors_by_candidate.get(cid, [])))

    summary = ["## 候補比較 (判断材料)"]
    for c in real[:3]:
        cid = str(c.get("candidate_id"))
        fac = factors_by_candidate.get(cid, [])
        match_n = sum(1 for f in fac if f.get("status") == "match")
        unk_n = sum(1 for f in fac if f.get("status") == "unknown")
        summary.append(
            f"- {c.get('candidate_id')}: 適合情報 {match_n}件 / 不明 {unk_n}件 / License={c.get('license')}"
        )
    return "\n\n".join(summary + [""] + blocks)
