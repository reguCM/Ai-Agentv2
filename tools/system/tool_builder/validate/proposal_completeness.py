"""
Proposal の機械検証。LLM を呼ばずにプレースホルダー残留や必須フィールド欠落を検出する。

Implementation に渡す前のゲートとして使う。
"""

import re

from tools.ai.prompts.create import PROPOSAL_PLACEHOLDERS

REQUIRED_FIELDS = ("name", "category", "module", "function", "output")


def _is_placeholder(value):
    if not isinstance(value, str):
        return False
    low = value.strip().lower()
    for ph in PROPOSAL_PLACEHOLDERS:
        if low == ph.lower():
            return True
    if re.match(r"^tools\.\w+\.subcategory\.\w+$", low):
        return True
    if re.match(r"^tools\.\w+\.\w+\.filename$", low):
        return True
    return False


def _is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def validate_proposal_completeness(proposal):
    """
    proposal dict を検査し、エラーリストとヒント文字列を返す。

    Returns:
        {
            "ok": bool,
            "errors": [{"field": ..., "reason": ...}, ...],
            "hint": str,  # LLM リトライに渡せる修正指示
        }
    """
    proposal = proposal or {}
    errors = []

    for field in REQUIRED_FIELDS:
        val = proposal.get(field)
        if _is_empty(val):
            errors.append({"field": field, "reason": "empty"})
        elif isinstance(val, str) and _is_placeholder(val):
            errors.append({"field": field, "reason": "placeholder"})

    module = proposal.get("module") or ""
    if isinstance(module, str) and module.strip():
        parts = module.strip().split(".")
        if len(parts) < 4:
            errors.append({"field": "module", "reason": "too_few_segments"})
        elif parts[0] != "tools":
            errors.append({"field": "module", "reason": "must_start_with_tools"})

    for field in ("name", "function", "subcategory", "description"):
        val = proposal.get(field)
        if isinstance(val, str) and _is_placeholder(val):
            if not any(e["field"] == field for e in errors):
                errors.append({"field": field, "reason": "placeholder"})

    impl_notes = proposal.get("implementation_notes") or []
    if not impl_notes:
        errors.append({"field": "implementation_notes", "reason": "empty"})

    ok = len(errors) == 0
    hint = _build_hint(errors) if errors else ""

    return {"ok": ok, "errors": errors, "hint": hint}


def _build_hint(errors):
    lines = ["Proposal の以下のフィールドを修正してください:"]
    for err in errors:
        field = err["field"]
        reason = err["reason"]
        if reason == "empty":
            lines.append(f"- {field}: 空です。要求に合わせた具体値を入れてください。")
        elif reason == "placeholder":
            lines.append(
                f"- {field}: プレースホルダーがそのまま残っています。"
                f"要求の内容に合わせた具体値に置き換えてください。"
            )
        elif reason == "too_few_segments":
            lines.append(
                f"- {field}: tools.<category>.<subcategory>.<filename> の形式にしてください。"
            )
        elif reason == "must_start_with_tools":
            lines.append(f"- {field}: tools. で始めてください。")
        else:
            lines.append(f"- {field}: {reason}")
    return "\n".join(lines)
