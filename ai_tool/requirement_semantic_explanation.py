"""Human-facing natural language layer for Requirement Semantic Revalidation v0."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_tool.requirement_semantic_revalidation import SemanticRevalidationResult


def _quote(text: str) -> str:
    token = str(text or "").strip()
    if not token:
        return "（記載なし）"
    return f"「{token}」"


def _primary_reason_codes(result: "SemanticRevalidationResult") -> set[str]:
    return set(result.reason_codes or [])


def _evidence_fields(expl: dict[str, str]) -> tuple[str, str, str, str]:
    human_req = str(expl.get("human_requirement") or expl.get("human_requirement_text") or "").strip()
    derived = str(expl.get("ai_spec") or expl.get("derived_spec_text") or "").strip()
    difference = str(expl.get("difference") or expl.get("difference_explanation") or "").strip()
    question = str(expl.get("question") or "").strip()
    return human_req, derived, difference, question


def _merge_clarification_fields(
    expl: dict[str, str],
    clarification: dict[str, Any] | None,
) -> dict[str, str]:
    if not clarification:
        return expl
    merged = {**expl}
    if clarification.get("clarification_reason_explanation"):
        merged["clarification_reason_explanation"] = str(
            clarification["clarification_reason_explanation"]
        )
    if clarification.get("leading_interpretation"):
        merged["leading_interpretation"] = str(clarification["leading_interpretation"])
    choices = clarification.get("choices") or []
    if choices:
        merged["clarification_choices"] = "\n".join(
            f"{c.get('id', '?')}. {c.get('label', '')}" for c in choices if isinstance(c, dict)
        )
    return merged


def build_natural_language_explanation(result: "SemanticRevalidationResult") -> dict[str, str]:
    """Build NL fields from an already-finalized decision and evidence. No re-decision."""
    expl = dict(result.human_explanation or {})
    clar = dict(getattr(result, "clarification", None) or {})
    human_req, derived, difference, question = _evidence_fields(expl)
    codes = _primary_reason_codes(result)
    decision = result.decision

    if clar.get("clarification_needed") and decision == "PASS":
        leading = str(clar.get("leading_interpretation") or "").strip()
        summary = "実装前に、解釈の確認が必要です。"
        diff_nl = str(clar.get("clarification_reason_explanation") or "").strip()
        if leading:
            diff_nl = (
                f"{leading} という理解で進めようとしています。\n{diff_nl}"
                if diff_nl
                else f"{leading} という理解で進めようとしています。"
            )
        choice_lines = expl.get("clarification_choices") or ""
        next_action = choice_lines or question
        return _merge_clarification_fields(
            {
                **expl,
                "human_summary": summary,
                "human_requirement_text": human_req or expl.get("human_requirement", ""),
                "derived_spec_text": derived,
                "difference_explanation": diff_nl,
                "next_action_explanation": next_action,
            },
            clar,
        )

    if decision == "PASS":
        summary = "元の要求と仕様に重要な意味のずれは見つかりませんでした。"
        return {
            **expl,
            "human_summary": summary,
            "human_requirement_text": human_req,
            "derived_spec_text": derived,
            "difference_explanation": "",
            "next_action_explanation": "",
        }

    if decision == "NEED_HUMAN":
        summary = "参照先や意図を、あなたに確認する必要があります。"
        diff_nl = difference or "どの対象を指すか、システムだけでは確定できません。"
        if clar.get("clarification_reason_explanation"):
            diff_nl = f"{diff_nl}\n{clar['clarification_reason_explanation']}"
        next_action = question or "再開または参照したい対象を教えてください。"
        if clar.get("choices"):
            next_action = expl.get("clarification_choices") or next_action
        return _merge_clarification_fields(
            {
                **expl,
                "human_summary": summary,
                "human_requirement_text": human_req or expl.get("human_requirement", ""),
                "derived_spec_text": derived if derived and derived != "(ambiguous reference)" else "（未確定）",
                "difference_explanation": diff_nl,
                "next_action_explanation": next_action,
            },
            clar,
        )

    if decision == "REVALIDATION_ERROR":
        summary = "意味の再確認を完了できませんでした。実装は開始しません。"
        return {
            **expl,
            "human_summary": summary,
            "human_requirement_text": human_req,
            "derived_spec_text": derived,
            "difference_explanation": difference or "評価処理でエラーが発生しました。",
            "next_action_explanation": question or "しばらくしてから再試行するか、仕様を手動で確認してください。",
        }

    if decision == "POSSIBLE_DRIFT":
        summary = "元の要求と仕様の間に、意味のずれの可能性があります。"
        next_action = (
            question
            or "この差分を許容するか、仕様を修正するか判断してください。"
        )
        return {
            **expl,
            "human_summary": summary,
            "human_requirement_text": human_req,
            "derived_spec_text": derived,
            "difference_explanation": _difference_paragraph(codes, human_req, derived, difference),
            "next_action_explanation": next_action,
        }

    # CONTRADICTION (default block path)
    summary = "元の要求と作成された仕様に違いがあります。"
    next_action = (
        question
        or "このまま実装を開始せず、仕様を再確認します。"
    )
    return {
        **expl,
        "human_summary": summary,
        "human_requirement_text": human_req,
        "derived_spec_text": derived,
        "difference_explanation": _difference_paragraph(codes, human_req, derived, difference),
        "next_action_explanation": next_action,
    }


def _difference_paragraph(
    codes: set[str],
    human_req: str,
    derived: str,
    difference: str,
) -> str:
    if (
        "CONTINUATION_STATE_MISMATCH" in codes
        or "CONTEXT_REFERENCE_DRIFT" in codes
    ) and human_req and derived:
        return (
            "再開対象が元の要求と異なっています。"
            f"要求では {_quote(human_req)} の指定ですが、"
            f"仕様では {_quote(derived)} を対象にしています。"
        )
    if (
        "INTENT_DIRECTION_MISMATCH" in codes
        or "AI_GOAL_SUBSTITUTION" in codes
    ) and human_req and derived:
        return (
            "要求の方向と作成された仕様が一致していません。"
            f"あなたの要求は {_quote(human_req)} ですが、"
            f"仕様では {_quote(derived)} となっています。"
        )
    if "PREFERENCE_HARDENING" in codes or "CONSTRAINT_STRENGTH_DRIFT" in codes:
        if human_req and derived:
            return (
                "条件の強さが変わっています。"
                f"元の要求では {_quote(human_req)} ですが、"
                f"作成された仕様では {_quote(derived)} となっています。"
            )
    if "SCOPE_OR_QUANTIFIER_DRIFT" in codes and human_req and derived:
        return (
            "対象の範囲が元の要求より広がっています。"
            f"要求: {_quote(human_req)} / 仕様: {_quote(derived)}"
        )
    if "REQUIREMENT_OMISSION" in codes and human_req:
        return (
            "要求に含まれる項目が、作成された仕様に反映されていません。"
            f"不足している要求: {_quote(human_req)}"
        )
    if difference:
        return difference
    if human_req and derived:
        return f"要求 {_quote(human_req)} と仕様 {_quote(derived)} の間に意味の差があります。"
    return "確認された evidence に基づき、意味の差があります。"


def with_human_facing_explanation(result: "SemanticRevalidationResult") -> "SemanticRevalidationResult":
    """Attach NL explanation fields; decision and reason_codes are unchanged."""
    result.human_explanation = build_natural_language_explanation(result)
    return result


def format_human_facing_message(
    result: "SemanticRevalidationResult",
    *,
    include_debug: bool = False,
) -> str:
    """Primary Human chat text — natural language, not reason_code labels."""
    clar = dict(getattr(result, "clarification", None) or {})
    if result.decision == "PASS" and not clar.get("clarification_needed"):
        expl = result.human_explanation or {}
        return str(
            expl.get("human_summary")
            or "元の要求と仕様に重要な意味のずれは見つかりませんでした。"
        )

    expl = dict(result.human_explanation or {})
    if not expl.get("human_summary"):
        expl = build_natural_language_explanation(result)

    sections: list[str] = []
    summary = str(expl.get("human_summary") or "").strip()
    if summary:
        sections.append(summary)

    human_req = str(expl.get("human_requirement_text") or "").strip()
    if human_req:
        sections.append(f"あなたの要求:\n{_quote(human_req)}")

    derived = str(expl.get("derived_spec_text") or expl.get("ai_spec") or "").strip()
    if derived and derived not in ("(ambiguous reference)", "(evaluator failure)"):
        if derived.startswith("(not found"):
            sections.append("AIが作った仕様:\n（要求の一部が仕様に見当たりません）")
        else:
            sections.append(f"AIが作った仕様:\n{_quote(derived)}")
    elif derived:
        sections.append(f"AIが作った仕様:\n{derived}")

    diff = str(expl.get("difference_explanation") or "").strip()
    if diff:
        sections.append(f"違っている点:\n{diff}")

    clar_reason = str(expl.get("clarification_reason_explanation") or "").strip()
    if clar_reason and clar_reason not in (diff or ""):
        sections.append(f"確認理由:\n{clar_reason}")

    leading = str(expl.get("leading_interpretation") or clar.get("leading_interpretation") or "").strip()
    if leading and result.decision == "PASS" and clar.get("clarification_needed"):
        sections.insert(1, f"現在の理解:\n{_quote(leading)}")

    choice_block = str(expl.get("clarification_choices") or "").strip()
    if choice_block:
        sections.append(f"選択:\n{choice_block}")

    nxt = str(expl.get("next_action_explanation") or "").strip()
    if nxt and nxt != choice_block:
        sections.append(f"対応:\n{nxt}")

    body = "\n\n".join(sections)
    if include_debug and result.reason_codes:
        body = f"{body}\n\n[debug] reason_codes={','.join(result.reason_codes)}"
    return body


def explanation_grounded_in_evidence(result: "SemanticRevalidationResult") -> bool:
    """True when NL fields only restate stored evidence (no extra requirements)."""
    expl = result.human_explanation or {}
    if result.decision == "PASS":
        return True
    human_req = str(expl.get("human_requirement_text") or expl.get("human_requirement") or "")
    derived = str(expl.get("derived_spec_text") or expl.get("ai_spec") or "")
    if not human_req and result.decision in ("CONTRADICTION", "NEED_HUMAN", "POSSIBLE_DRIFT"):
        return False
    if result.decision == "CONTRADICTION" and not derived and derived != "(not found in derived spec)":
        if "(not found" not in str(expl.get("ai_spec") or ""):
            pass
    return bool(human_req or result.decision == "REVALIDATION_ERROR")
