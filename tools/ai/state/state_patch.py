"""Phase 1/2: StatePatch 適用。将来 Partial Judge 出力もここへ寄せる。"""

from tools.ai.state.open_questions import (
    ensure_open_question,
    resolve_open_question,
    resolve_open_question_by_text,
)


def _ensure_banned_actions(state):
    if not hasattr(state, "banned_actions") or state.banned_actions is None:
        state.banned_actions = []
    return state.banned_actions


def _ban_key(command, args):
    return (str(command or "").strip(), tuple(str(arg) for arg in (args or [])))


def apply_state_patches(state, patches, *, history=None):
    """patch リストを順に適用する。未知 op は無視。"""
    applied = []
    for patch in patches or []:
        if not isinstance(patch, dict):
            continue
        op = str(patch.get("op") or "").strip()
        if op == "add_open_question":
            text = patch.get("text")
            event_id = patch.get("event_id")
            qid = ensure_open_question(state, text, event_id=event_id)
            if qid:
                applied.append(patch)
        elif op == "resolve_question":
            qid = patch.get("question_id")
            if qid and resolve_open_question(
                state,
                qid,
                history=history,
                reason=patch.get("reason"),
                finding_ref=patch.get("finding_ref"),
            ):
                applied.append(patch)
        elif op == "resolve_question_by_text":
            text = patch.get("text")
            if text and resolve_open_question_by_text(
                state,
                text,
                history=history,
                reason=patch.get("reason"),
                finding_ref=patch.get("finding_ref"),
            ):
                applied.append(patch)
        elif op == "add_usable":
            finding_ref = str(patch.get("finding_ref") or "").strip()
            if not finding_ref:
                continue
            selected = getattr(state, "selected_findings", None)
            if selected is None:
                state.selected_findings = []
                selected = state.selected_findings
            if any(
                isinstance(item, dict) and item.get("finding_ref") == finding_ref
                for item in selected
            ):
                applied.append(patch)
                continue
            selected.append(
                {
                    "finding_ref": finding_ref,
                    "summary": str(patch.get("summary") or "")[:200],
                    "source": patch.get("source") or "state_patch",
                }
            )
            applied.append(patch)
        elif op == "ban_action":
            command = str(patch.get("command") or "").strip()
            if not command:
                continue
            args = list(patch.get("args") or [])
            banned = _ensure_banned_actions(state)
            key = _ban_key(command, args)
            exists = any(
                _ban_key(item.get("command"), item.get("args")) == key
                for item in banned
                if isinstance(item, dict)
            )
            if not exists:
                banned.append(
                    {
                        "command": command,
                        "args": args,
                        "event_id": patch.get("event_id"),
                        "reason": patch.get("reason") or "ban_action",
                    }
                )
            applied.append(patch)
    return applied
