"""CLI for Cognitive Layer Phase 1: create / update / visualize sessions.

Does not call Selector or Tools.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.ai.state.cognitive_session import DEFAULT_ROOT, load_session, save_session
from tools.ai.state.cognitive_state import (
    add_claim,
    add_evidence,
    add_hypothesis,
    add_unresolved,
    confirm_human_review,
    init_from_user_request,
    set_intent,
    sync_unresolved_from_task_state,
)
from tools.ai.state.task_state import TaskState


def _add_root(p: argparse.ArgumentParser) -> None:
    p.add_argument("--root", type=Path, default=None, help="Session root (default: cognitive_sessions/)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cognitive State Phase 1 (no Selector/Tools)")
    _add_root(parser)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Create a new cognitive session from a goal/request")
    _add_root(p_init)
    p_init.add_argument("--goal", required=True)
    p_init.add_argument("--intent", default="")
    p_init.add_argument("--hypothesis", action="append", default=[])
    p_init.add_argument("--unresolved", action="append", default=[])
    p_init.add_argument("--claim", action="append", default=[])

    p_show = sub.add_parser("show", help="Print COGNITIVE_STATE.md path and summary")
    _add_root(p_show)
    p_show.add_argument("--session-id", required=True)

    p_update = sub.add_parser("update", help="Apply updates and re-save")
    _add_root(p_update)
    p_update.add_argument("--session-id", required=True)
    p_update.add_argument("--intent", default=None)
    p_update.add_argument("--hypothesis", action="append", default=[])
    p_update.add_argument("--unresolved", action="append", default=[])
    p_update.add_argument("--claim", action="append", default=[])
    p_update.add_argument("--evidence", action="append", default=[])
    p_update.add_argument("--sync-task-json", type=Path, default=None, help="TaskState snapshot JSON")

    p_confirm = sub.add_parser("confirm", help="Mark human review confirmed")
    _add_root(p_confirm)
    p_confirm.add_argument("--session-id", required=True)
    p_confirm.add_argument("--reviewer", default="human")
    p_confirm.add_argument("--note", default="")

    args = parser.parse_args()
    root = args.root or DEFAULT_ROOT

    if args.cmd == "init":
        state = init_from_user_request(args.goal, source="cli")
        if args.intent:
            set_intent(state, args.intent, reason_code="cli_intent")
        for h in args.hypothesis:
            add_hypothesis(state, h, reason_code="cli_hypothesis")
        for u in args.unresolved:
            add_unresolved(state, u, reason_code="cli_unresolved")
        for c in args.claim:
            add_claim(state, c, reason_code="cli_claim")
        path = save_session(state, root=root)
        print(path)
        print("session_id=", state["session_id"])
        return

    if args.cmd == "show":
        state = load_session(args.session_id, root=root)
        path = root / args.session_id / "COGNITIVE_STATE.md"
        print(path.read_text(encoding="utf-8"))
        print("---")
        print("fingerprint:", root / args.session_id / "fingerprint_candidate.json")
        print("human_review:", (state.get("human_review") or {}).get("status"))
        return

    if args.cmd == "update":
        state = load_session(args.session_id, root=root)
        if args.intent is not None:
            set_intent(state, args.intent, reason_code="cli_intent")
        for h in args.hypothesis:
            add_hypothesis(state, h, reason_code="cli_hypothesis")
        for u in args.unresolved:
            add_unresolved(state, u, reason_code="cli_unresolved")
        for c in args.claim:
            add_claim(state, c, reason_code="cli_claim")
        for e in args.evidence:
            add_evidence(state, e, reason_code="cli_evidence")
        if args.sync_task_json:
            payload = json.loads(args.sync_task_json.read_text(encoding="utf-8"))
            sync_unresolved_from_task_state(state, TaskState.from_payload(payload))
        path = save_session(state, root=root)
        print(path)
        return

    if args.cmd == "confirm":
        state = load_session(args.session_id, root=root)
        confirm_human_review(state, reviewer=args.reviewer, note=args.note)
        path = save_session(state, root=root)
        print(path)
        print("human_review=confirmed")
        return


if __name__ == "__main__":
    main()
