"""Provisional Goal Completion Gate v0.

When existing specifications do not uniquely determine Goal completion,
ask Human about Goal meaning / completion conditions. System maps a
connected answer to a Mission end state. Humans do not pick the 4
internal Mission states.

Canonical owner of that judgment. Observation facts stay on the orchestrator.

v0 connected ask trigger:
- Search-target conversation Grill takes precedence.
- A complete parent listing omitted a request-named path.
- No connected System rule uniquely determines achieved / ended_incomplete.

v0 connected resume case:
- named_path_omitted_from_complete_listing
- Human answers whether absence-confirmation completes the Goal, or
  whether unreported content means the Goal is not complete.
- Other answers stop as unsupported. Do not invent a Mission state.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

GOAL_COMPLETION_HUMAN_REASON = (
    "EXISTING_SPECS_DO_NOT_UNIQUELY_DETERMINE_GOAL_COMPLETION"
)
NAMED_PATH_OMITTED_CASE = "named_path_omitted_from_complete_listing"
GOAL_MEANING_ABSENCE_COMPLETES = "absence_confirmed_completes_goal"
GOAL_MEANING_CONTENT_REQUIRED = "content_report_required"

GOAL_MEANING_OPTIONS = (
    {
        "id": GOAL_MEANING_ABSENCE_COMPLETES,
        "label": "指名したファイルが無いことを確認し、それを報告できれば Goal は完了",
    },
    {
        "id": GOAL_MEANING_CONTENT_REQUIRED,
        "label": "指名したファイルの中身（先頭行など）を報告できなければ Goal は完了ではない",
    },
)

_ABSENCE_MARKERS = (
    "無いことを確認",
    "存在しないことを確認",
    "不在確認",
    "確認できれば完了",
    "確認して報告できれば完了",
    "確認できればgoalは完了",
)
_CONTENT_REQUIRED_MARKERS = (
    "中身を報告できなければ",
    "先頭行を報告できなければ",
    "内容を報告できなければ",
    "報告できなければ完了ではない",
    "報告できなければgoalは完了ではない",
)


def existing_specs_uniquely_determine_goal_completion(
    orchestrator: Any,
) -> bool:
    """True only when a connected System rule uniquely picks a Mission end state.

    v0: Goal achievement and ended_incomplete rules are NOT_CONNECTED.
    """
    del orchestrator
    return False


def omitted_request_named_paths(orchestrator: Any) -> list[str]:
    method = getattr(orchestrator, "omitted_request_named_paths", None)
    if callable(method):
        return [str(item) for item in method() if str(item)]
    return []


def needs_goal_completion_human(orchestrator: Any) -> bool:
    if orchestrator is None:
        return False
    if getattr(orchestrator, "goal_completion_consumed", False):
        return False
    if getattr(orchestrator, "needs_human_grill", lambda: False)():
        return False
    if existing_specs_uniquely_determine_goal_completion(orchestrator):
        return False
    tasks = getattr(getattr(orchestrator, "runtime", None), "tasks", None) or {}
    observation = tasks.get("T1")
    if observation is None or getattr(observation, "status", None) != "complete":
        return False
    return bool(omitted_request_named_paths(orchestrator))


def build_goal_completion_human(orchestrator: Any) -> dict[str, Any]:
    omitted = omitted_request_named_paths(orchestrator)
    facts = _confirmed_facts(orchestrator, omitted)
    original = str(getattr(orchestrator, "request", "") or "")
    return {
        "phase": "goal_completion_human",
        "status": "AWAITING_HUMAN",
        "reason": GOAL_COMPLETION_HUMAN_REASON,
        "case": NAMED_PATH_OMITTED_CASE,
        "question": (
            "既存仕様では Goal の完了条件を一意に判定できません。"
            "内部の Mission 状態名は選ばないでください。"
            "この Goal では何をもって完了としますか。"
        ),
        "undecided": (
            "Named path(s) are confirmed absent from a complete listing, "
            "but existing specifications do not say whether that completes the Goal."
        ),
        "confirmed_facts": facts,
        "goal_meaning_options": [dict(item) for item in GOAL_MEANING_OPTIONS],
        "recommended": {
            "id": None,
            "text": (
                "完了条件が「無いことの確認と報告」なら、不在確認で Goal は完了と扱う。"
                "中身の報告が必須なら、報告できない以上 Goal は完了ではない。"
                "System が Mission 状態を決める。"
            ),
        },
        "goal_canonical": {
            "original_goal": original,
            "explicit_conditions": list(
                getattr(orchestrator, "user_explicit_conditions", None) or []
            ),
            "explicit_constraints": [],
            "user_confirmed_supplements": [
                dict(item)
                for item in (getattr(orchestrator, "confirmed_clarifications", None) or [])
                if isinstance(item, dict)
            ],
        },
        "omitted_paths": omitted,
        "mission_id": str(getattr(orchestrator, "mission_id", "") or ""),
    }


def build_goal_completion_resume(orchestrator: Any) -> dict[str, Any]:
    packet = build_goal_completion_human(orchestrator)
    return {
        "case": NAMED_PATH_OMITTED_CASE,
        "original_request": str(getattr(orchestrator, "request", "") or ""),
        "mission_id": packet["mission_id"],
        "omitted_paths": list(packet.get("omitted_paths") or []),
        "confirmed_facts": list(packet.get("confirmed_facts") or []),
        "goal_canonical": dict(packet.get("goal_canonical") or {}),
        "goal_meaning_options": list(packet.get("goal_meaning_options") or []),
    }


def format_goal_completion_human(record: Mapping[str, Any]) -> str:
    facts = [str(item) for item in (record.get("confirmed_facts") or []) if str(item)]
    options = record.get("goal_meaning_options") or []
    recommended = dict(record.get("recommended") or {})
    lines = [
        str(record.get("question") or ""),
        "",
        "確認済み事実:",
    ]
    if facts:
        lines.extend(f"- {item}" for item in facts)
    else:
        lines.append("- （記録された確認済み事実はない）")
    lines.extend(
        [
            "",
            "未決の Goal 完了条件:",
            f"- {record.get('undecided') or ''}",
            "",
            "次のどちらがこの Goal の完了条件ですか。番号または同じ意味の文で答えてください。",
        ]
    )
    for index, item in enumerate(options, start=1):
        if isinstance(item, Mapping):
            lines.append(f"{index}. {item.get('label')}")
    lines.extend(
        [
            "",
            "推奨:",
            f"- {recommended.get('text') or ''}",
        ]
    )
    return "\n".join(lines).strip()


def interpret_goal_completion_answer(
    text: str,
    *,
    case: str,
) -> dict[str, Any]:
    """Map a Human Goal-meaning answer to a Mission state. Do not guess."""
    if case != NAMED_PATH_OMITTED_CASE:
        return {
            "status": "unsupported",
            "reason": "GOAL_COMPLETION_CASE_NOT_CONNECTED",
            "goal_meaning": None,
            "execution_end_state": None,
            "goal_achievement_result": None,
        }
    meaning = match_omitted_path_goal_meaning(text)
    if meaning == GOAL_MEANING_ABSENCE_COMPLETES:
        return {
            "status": "judged",
            "reason": "HUMAN_CONFIRMED_ABSENCE_COMPLETES_GOAL",
            "goal_meaning": meaning,
            "execution_end_state": "achieved",
            "goal_achievement_result": "achieved",
            "supplement_text": (
                "指名したファイルが無いことを確認し、それを報告できれば Goal は完了"
            ),
        }
    if meaning == GOAL_MEANING_CONTENT_REQUIRED:
        return {
            "status": "judged",
            "reason": "HUMAN_CONFIRMED_CONTENT_REPORT_REQUIRED",
            "goal_meaning": meaning,
            "execution_end_state": "ended_incomplete",
            "goal_achievement_result": "not_achieved",
            "supplement_text": (
                "指名したファイルの中身（先頭行など）を報告できなければ Goal は完了ではない"
            ),
        }
    return {
        "status": "unsupported",
        "reason": "GOAL_MEANING_ANSWER_NOT_CONNECTED",
        "goal_meaning": None,
        "execution_end_state": None,
        "goal_achievement_result": None,
    }


def match_omitted_path_goal_meaning(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if re.match(r"^[1１]([.\s、．)]|$)", raw):
        return GOAL_MEANING_ABSENCE_COMPLETES
    if re.match(r"^[2２]([.\s、．)]|$)", raw):
        return GOAL_MEANING_CONTENT_REQUIRED
    folded = raw.casefold()
    hit_absence = any(marker in folded for marker in _ABSENCE_MARKERS)
    hit_content = any(marker in folded for marker in _CONTENT_REQUIRED_MARKERS)
    if hit_absence and hit_content:
        return None
    if hit_absence:
        return GOAL_MEANING_ABSENCE_COMPLETES
    if hit_content:
        return GOAL_MEANING_CONTENT_REQUIRED
    return None


def format_goal_completion_judgment(judgment: Mapping[str, Any]) -> str:
    if judgment.get("status") == "judged":
        state = str(judgment.get("execution_end_state") or "")
        meaning = str(judgment.get("supplement_text") or "")
        return "\n".join(
            [
                "Human の完了条件を採用し、System が Mission 状態を決めました。",
                f"採用した完了条件: {meaning}",
                f"Mission 状態: {state}",
            ]
        ).strip()
    return "\n".join(
        [
            "この回答では Goal 完了条件を既存の接続済み解釈へ一意に落とせません。",
            "Mission 状態は確定していません。",
            "未対応として停止します。推測では判定しません。",
            f"reason: {judgment.get('reason') or 'GOAL_MEANING_ANSWER_NOT_CONNECTED'}",
        ]
    ).strip()


def _confirmed_facts(orchestrator: Any, omitted: list[str]) -> list[str]:
    facts: list[str] = []
    if omitted:
        facts.append(
            "Complete listing(s) omitted request-named path(s): " + ", ".join(omitted)
        )
    evidence = getattr(getattr(orchestrator, "runtime", None), "evidence", None) or {}
    for record in evidence.values():
        text = str(
            getattr(record, "relevant_content", None)
            or getattr(record, "summary", None)
            or ""
        ).strip()
        if text and text not in facts:
            facts.append(text[:500])
    return facts
