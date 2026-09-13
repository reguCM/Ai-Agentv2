"""Research 結果を History / open_questions / compact unresolved へ同期する。"""

from tools.ai.state.open_questions import (
    compact_unresolved_for_state,
    ensure_open_question,
    question_text_from_finding,
    resolve_open_question,
    resolve_open_question_by_text,
)


def _normalize_missing(missing):
    return {
        str(item).strip().lower()
        for item in (missing or [])
        if str(item).strip()
    }


def sync_research_into_state(
    state,
    *,
    research,
    round_num,
    judgment=None,
    previous_missing=None,
    round_research=None,
    skip_round_findings=False,
):
    """
    Phase 1 同期:
    - 完全情報は History へ
    - State は open_questions + compact unresolved のみ
    - research / handoff 用 dict は変更しない

    skip_round_findings:
      Phase 2 rule_partial が既に finding を History / open_questions へ
      記録済みのとき True。judge 関連だけ同期する。
    """
    history = state.research_history
    round_payload = round_research if round_research is not None else research

    if not skip_round_findings:
        for item in round_payload.get("unresolved") or []:
            if not isinstance(item, dict):
                continue
            event_id = history.record_finding(
                item, event_type="verify_fail", round_num=round_num
            )
            text = question_text_from_finding(item)
            if text:
                ensure_open_question(state, text, event_id=event_id)

        for item in round_payload.get("usable_findings") or []:
            if isinstance(item, dict):
                history.record_finding(item, event_type="verify_ok", round_num=round_num)

    if judgment:
        history.record_judge(judgment, round_num=round_num)
        for missing in judgment.get("missing") or []:
            text = str(missing or "").strip()
            if text:
                ensure_open_question(state, text)

        if judgment.get("satisfies_request"):
            for question in list(state.open_questions):
                if question.get("status") == "open":
                    resolve_open_question(
                        state,
                        question["id"],
                        history=history,
                        reason="satisfies_request",
                    )
        elif previous_missing is not None:
            prev = _normalize_missing(previous_missing)
            now = _normalize_missing(judgment.get("missing"))
            for text_key in prev - now:
                for question in state.open_questions:
                    if question.get("status") != "open":
                        continue
                    if str(question.get("text") or "").strip().lower() == text_key:
                        resolve_open_question(
                            state,
                            question["id"],
                            history=history,
                            reason="missing_resolved",
                        )
                        break

    state.unresolved = compact_unresolved_for_state(state.open_questions)
    return state
