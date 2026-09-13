"""
PROJECT_AGENT 専用の最小 Tool Execution Gate。

方針（V1）:
- デフォルトは人間確認（auto_allow に無い Tool は実行前に確認）
- 人間が「確認不要」と判断した Tool だけ昇格（auto_allow）
- 問題があれば降格して再び確認対象へ戻せる
- 安全分類の完成はしない。使用実績は trust ファイルとログに残す

意図的にやらないこと:
- tools.ai.state.execution_gate / Trusted Personal / apply_human_decision との統合
- RESEARCH_PIPELINE / test_tool AST Safety との共有
- 危険度の自動分類・自動昇格
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

POLICY_REQUIRE_CONFIRM = "require_confirm"
POLICY_AUTO_ALLOW = "auto_allow"

DECISION_ALLOW = "allow"
DECISION_DENY = "deny"
DECISION_PROMOTE_AND_ALLOW = "promote_and_allow"

_HISTORY_MAX = 200
_DEFAULT_RELATIVE = Path("registry") / "agent_tool_trust.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def trust_path() -> Path:
    raw = (os.environ.get("AI_AGENT_TOOL_TRUST") or "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / _DEFAULT_RELATIVE


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_trust_store() -> dict[str, Any]:
    return {
        "version": 1,
        "default_policy": POLICY_REQUIRE_CONFIRM,
        "auto_allow": [],
        "history": [],
        "note": (
            "PROJECT_AGENT only. Tools absent from auto_allow require human confirm. "
            "Not Research Pipeline Safety."
        ),
    }


def load_trust_store(path: Path | None = None) -> dict[str, Any]:
    target = path or trust_path()
    if not target.is_file():
        return empty_trust_store()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_trust_store()
    if not isinstance(data, dict):
        return empty_trust_store()
    store = empty_trust_store()
    store.update(data)
    names = store.get("auto_allow") or []
    if not isinstance(names, list):
        names = []
    store["auto_allow"] = sorted(
        {str(n).strip() for n in names if str(n).strip()}
    )
    history = store.get("history") or []
    store["history"] = history if isinstance(history, list) else []
    store["default_policy"] = POLICY_REQUIRE_CONFIRM
    return store


def save_trust_store(store: dict[str, Any], path: Path | None = None) -> Path:
    target = path or trust_path()
    payload = empty_trust_store()
    payload.update(store or {})
    payload["default_policy"] = POLICY_REQUIRE_CONFIRM
    names = payload.get("auto_allow") or []
    payload["auto_allow"] = sorted(
        {str(n).strip() for n in names if str(n).strip()}
    )
    history = list(payload.get("history") or [])
    if len(history) > _HISTORY_MAX:
        history = history[-_HISTORY_MAX:]
    payload["history"] = history
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _append_history(
    store: dict[str, Any],
    *,
    action: str,
    tool_name: str,
    note: str | None = None,
) -> None:
    entry = {
        "ts": _now_iso(),
        "action": action,
        "tool_name": tool_name,
        "note": note,
    }
    history = list(store.get("history") or [])
    history.append(entry)
    store["history"] = history[-_HISTORY_MAX:]


def gate_mode() -> str:
    """
    confirm: 通常（デフォルト）。未昇格は人間確認。
    off: Gate 無効（明示的な退避。常用しない）。
    """
    raw = (os.environ.get("AI_AGENT_TOOL_GATE") or "confirm").strip().lower()
    if raw in ("off", "0", "false", "disable", "disabled"):
        return "off"
    return "confirm"


def is_auto_allowed(tool_name: str, store: dict[str, Any] | None = None) -> bool:
    name = str(tool_name or "").strip()
    if not name:
        return False
    data = store if store is not None else load_trust_store()
    return name in set(data.get("auto_allow") or [])


def decide_policy(tool_name: str, store: dict[str, Any] | None = None) -> str:
    if gate_mode() == "off":
        return POLICY_AUTO_ALLOW
    if is_auto_allowed(tool_name, store=store):
        return POLICY_AUTO_ALLOW
    return POLICY_REQUIRE_CONFIRM


def promote_tool(
    tool_name: str,
    *,
    note: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    name = str(tool_name or "").strip()
    if not name:
        raise ValueError("tool_name が空です")
    store = load_trust_store(path)
    names = set(store.get("auto_allow") or [])
    already = name in names
    names.add(name)
    store["auto_allow"] = sorted(names)
    if not already:
        _append_history(store, action="promote", tool_name=name, note=note)
    save_trust_store(store, path)
    return {
        "ok": True,
        "action": "promote",
        "tool_name": name,
        "already": already,
        "auto_allow": list(store["auto_allow"]),
        "path": str(path or trust_path()),
    }


def demote_tool(
    tool_name: str,
    *,
    note: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    name = str(tool_name or "").strip()
    if not name:
        raise ValueError("tool_name が空です")
    store = load_trust_store(path)
    names = set(store.get("auto_allow") or [])
    existed = name in names
    names.discard(name)
    store["auto_allow"] = sorted(names)
    if existed:
        _append_history(store, action="demote", tool_name=name, note=note)
    save_trust_store(store, path)
    return {
        "ok": True,
        "action": "demote",
        "tool_name": name,
        "existed": existed,
        "auto_allow": list(store["auto_allow"]),
        "path": str(path or trust_path()),
    }


def parse_confirm_reply(reply: str | None) -> str:
    """
    人間入力を正規化。
    allow / deny / promote_and_allow
    """
    text = str(reply or "").strip().lower()
    if text in ("y", "yes", "ok", "allow", "a"):
        return DECISION_ALLOW
    if text in ("n", "no", "deny", "d"):
        return DECISION_DENY
    if text in ("always", "promote", "trust", "p"):
        return DECISION_PROMOTE_AND_ALLOW
    return DECISION_DENY


def format_confirm_prompt(tool_name: str, arguments: Any) -> str:
    try:
        args_text = json.dumps(arguments, ensure_ascii=False, indent=2, default=str)
    except Exception:
        args_text = str(arguments)
    return (
        f"\n[AGENT_TOOL_GATE] Tool実行の確認が必要です（デフォルト: 人間確認）\n"
        f"tool: {tool_name}\n"
        f"arguments:\n{args_text}\n"
        f"入力: y=今回のみ許可 / n=拒否 / always=昇格して以降確認不要\n"
    )


def default_ask_confirm(tool_name: str, arguments: Any) -> str | None:
    print(format_confirm_prompt(tool_name, arguments), end="")
    if not sys.stdin.isatty():
        print(
            "[AGENT_TOOL_GATE] 非TTYのため確認不能 → 安全側で拒否します。",
            file=sys.stderr,
        )
        return None
    try:
        return input("> ").strip()
    except EOFError:
        return None


def blocked_result(
    tool_name: str,
    *,
    reason: str,
    arguments: Any = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "blocked_by_agent_tool_gate": True,
        "gate": "project_agent_tool_gate",
        "tool_name": tool_name,
        "arguments": arguments if arguments is not None else {},
        "reason": reason,
        "message": (
            f"PROJECT_AGENT Tool Gate により実行しませんでした ({reason}). "
            "昇格は promote、または確認時に always。"
        ),
    }


AskConfirmFn = Callable[[str, Any], str | None]


def authorize_tool_execution(
    tool_name: str,
    arguments: Any = None,
    *,
    ask_confirm: AskConfirmFn | None = None,
    store_path: Path | None = None,
    bypass: bool = False,
) -> dict[str, Any]:
    """
    実行前認可。Research Pipeline の decide_execution_gate とは別物。

    戻り値:
      allowed: bool
      policy: require_confirm | auto_allow
      decision: allow | deny | promote_and_allow | bypass | gate_off
      store 操作の有無など
    """
    name = str(tool_name or "").strip()
    if bypass:
        return {
            "allowed": True,
            "policy": POLICY_AUTO_ALLOW,
            "decision": "bypass",
            "tool_name": name,
            "promoted": False,
        }

    if gate_mode() == "off":
        return {
            "allowed": True,
            "policy": POLICY_AUTO_ALLOW,
            "decision": "gate_off",
            "tool_name": name,
            "promoted": False,
        }

    store = load_trust_store(store_path)
    policy = decide_policy(name, store=store)
    if policy == POLICY_AUTO_ALLOW:
        return {
            "allowed": True,
            "policy": POLICY_AUTO_ALLOW,
            "decision": DECISION_ALLOW,
            "tool_name": name,
            "promoted": False,
            "source": "auto_allow_list",
        }

    ask = ask_confirm or default_ask_confirm
    reply = ask(name, arguments)
    decision = parse_confirm_reply(reply)
    if decision == DECISION_DENY:
        return {
            "allowed": False,
            "policy": POLICY_REQUIRE_CONFIRM,
            "decision": DECISION_DENY,
            "tool_name": name,
            "promoted": False,
            "reply": reply,
        }
    promoted = False
    if decision == DECISION_PROMOTE_AND_ALLOW:
        promote_tool(name, note="promoted_via_confirm_prompt", path=store_path)
        promoted = True
        decision = DECISION_PROMOTE_AND_ALLOW
    return {
        "allowed": True,
        "policy": POLICY_REQUIRE_CONFIRM,
        "decision": decision,
        "tool_name": name,
        "promoted": promoted,
        "reply": reply,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PROJECT_AGENT Tool Gate: promote / demote / list"
    )
    parser.add_argument(
        "action",
        choices=("list", "promote", "demote", "policy"),
        help="list | promote | demote | policy",
    )
    parser.add_argument("tool_name", nargs="?", help="Tool name")
    parser.add_argument("--note", default=None, help="history note")
    parser.add_argument(
        "--trust-file",
        default=None,
        help="override trust JSON path (or set AI_AGENT_TOOL_TRUST)",
    )
    args = parser.parse_args(argv)
    path = Path(args.trust_file) if args.trust_file else None

    if args.action == "list":
        store = load_trust_store(path)
        print(json.dumps(store, ensure_ascii=False, indent=2))
        return 0
    if args.action == "policy":
        name = str(args.tool_name or "").strip()
        if not name:
            print("policy には tool_name が必要です", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {
                    "tool_name": name,
                    "gate_mode": gate_mode(),
                    "policy": decide_policy(name, store=load_trust_store(path)),
                    "trust_path": str(path or trust_path()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not args.tool_name:
        print(f"{args.action} には tool_name が必要です", file=sys.stderr)
        return 2
    if args.action == "promote":
        print(
            json.dumps(
                promote_tool(args.tool_name, note=args.note, path=path),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(
        json.dumps(
            demote_tool(args.tool_name, note=args.note, path=path),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
