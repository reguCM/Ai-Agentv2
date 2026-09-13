"""Human-facing view for one Grill turn."""
from __future__ import annotations

from typing import Any


def _lines_for_list(items: list[Any], empty: str = "(なし)") -> list[str]:
    if not items:
        return [empty]
    out: list[str] = []
    for it in items:
        if isinstance(it, dict):
            title = it.get("title") or it.get("id") or ""
            text = it.get("text") or it.get("value") or it.get("note") or ""
            if title and text:
                out.append(f"- {title}: {text}")
            else:
                out.append(f"- {text or title or it}")
        else:
            out.append(f"- {it}")
    return out


def render_turn(turn: dict[str, Any], spec: dict[str, Any]) -> str:
    focus = turn.get("focus_item") or {}
    rec = turn.get("recommendation") or {}
    lines = [
        "[現在のGoal]",
        str(spec.get("goal") or ""),
        "",
        "[今回決める項目]",
        str(focus.get("title") or focus.get("id") or "(未解析)"),
        "",
        "[なぜ今]",
        str(focus.get("why_now") or ""),
        "",
        "[質問]",
        str(turn.get("question") or ""),
        "",
    ]
    for opt in turn.get("options") or []:
        oid = opt.get("id") or "?"
        lines.append(f"[{oid}]")
        lines.append(str(opt.get("label") or ""))
        desc = str(opt.get("description") or "").strip()
        if desc:
            lines.append(desc)
        lines.append("")
    lines += [
        "[推奨]",
        str(rec.get("id") or ""),
        "理由: " + str(rec.get("reason") or ""),
        "",
        "[現在の確定仕様]",
        *_lines_for_list(list(spec.get("confirmed") or [])),
        "",
        "[想定（未確定）]",
        *_lines_for_list(list(spec.get("assumptions") or [])),
        "",
        "[主な未確定仕様]",
        *_lines_for_list(list(spec.get("unresolved") or [])),
        "",
        "[委任（具体値は未確定）]",
        *_lines_for_list(list(spec.get("delegated") or [])),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"
