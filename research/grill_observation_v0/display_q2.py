"""Human-facing view for Grill Q2 intermediate-layer run."""
from __future__ import annotations

from typing import Any


def _fmt_decision(d: dict[str, Any]) -> str:
    title = d.get("title") or d.get("id") or ""
    value = d.get("value")
    by = d.get("decided_by") or ""
    return (
        f"- {title}: {value} "
        f"(decided_by={by}, status={d.get('status')}, human_confirmed={d.get('human_confirmed')})"
    )


def _fmt_unresolved(items: list[Any]) -> list[str]:
    if not items:
        return ["(なし)"]
    lines: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            lines.append(f"- {it}")
            continue
        title = it.get("title") or it.get("id") or ""
        text = it.get("text") or ""
        if title and text:
            lines.append(f"- {title}: {text}")
        else:
            lines.append(f"- {text or title}")
    return lines


def _dump_state(state: dict[str, Any]) -> str:
    lines: list[str] = ["human_requirements:"]
    reqs = state.get("human_requirements") or []
    if not reqs:
        lines.append("(なし)")
    else:
        for r in reqs:
            lines.append(f"- {r.get('id')}: {r.get('text')}")
    lines.append("confirmed_decisions:")
    confirmed = state.get("confirmed_decisions") or []
    if not confirmed:
        lines.append("(なし)")
    else:
        for d in confirmed:
            lines.append(_fmt_decision(d) if isinstance(d, dict) else f"- {d}")
    lines.append("assumptions:")
    assumptions = state.get("assumptions") or []
    if not assumptions:
        lines.append("(なし)")
    else:
        for a in assumptions:
            lines.append(f"- {a}")
    lines.append("delegated:")
    delegated = state.get("delegated") or []
    if not delegated:
        lines.append("(なし)")
    else:
        for d in delegated:
            lines.append(f"- {d}")
    return "\n".join(lines)


def render_q2_view(run: dict[str, Any]) -> str:
    state = run.get("system_state") or {}
    goal = (state.get("goal") or {}).get("text") or run.get("goal") or ""
    q1_adopt = run.get("q1_adoption") or {}
    internals = [
        d for d in (run.get("internal_decisions") or []) if d.get("kind") == "internal_ai_decision"
    ]
    q2 = run.get("q2") or {}
    parsed = q2.get("parsed") or {}
    rec = parsed.get("recommendation") or {}
    focus = parsed.get("focus_item") or {}
    lines = [
        "[現在のGoal]",
        str(goal),
        "",
        "[Q1からAI側で確定した仕様]",
    ]
    if q1_adopt.get("adopted"):
        rec_a = q1_adopt.get("decision") or {}
        lines.append(_fmt_decision(rec_a) if rec_a else str(q1_adopt))
        lines.append("判定理由: " + str((q1_adopt.get("classification") or {}).get("reason") or ""))
    else:
        lines.append("(未採用)")
        lines.append(str(q1_adopt.get("stop_reason") or q1_adopt.get("reason") or ""))
    lines += ["", "[その他の内部AI Decision]"]
    if internals:
        for d in internals:
            dec = d.get("decision") or {}
            lines.append(_fmt_decision(dec) if dec else f"- {d}")
    else:
        lines.append("(なし)")
    lines += [
        "",
        "[今回Humanへ確認する理由]",
        str(parsed.get("why_ask_human") or run.get("human_promotion_reason") or "(Q2未生成)"),
        "",
        "[Q2で決める項目]",
        str(focus.get("title") or focus.get("id") or "(なし)"),
        "",
        "[質問]",
        str(parsed.get("question") or "(なし)"),
        "",
        "[選択肢]",
    ]
    opts = parsed.get("options") or []
    if not opts:
        lines.append("(なし)")
    for opt in opts:
        oid = opt.get("id") or "?"
        lines.append(f"[{oid}] {opt.get('label') or ''}")
        desc = str(opt.get("description") or "").strip()
        if desc:
            lines.append(desc)
        lines.append("")
    conv = parsed.get("conversion_notes") or run.get("conversion_notes")
    lines += [
        "[推奨]",
        str(rec.get("id") or ""),
        "",
        "[推奨理由]",
        str(rec.get("reason") or ""),
        "",
        "[現在の仕様状態]",
        _dump_state(state),
        "",
        "[主要な未確定領域]",
        *_fmt_unresolved(list(state.get("unresolved") or [])),
        "",
    ]
    if conv:
        lines += ["[Technical→Human 変換メモ]", str(conv), ""]
    lines.append(f"[stopped] {run.get('stopped')}")
    return "\n".join(lines).rstrip() + "\n"
