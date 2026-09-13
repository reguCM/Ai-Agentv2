"""v2.2.1 — Agent/Cursor shell command bridge to safe_local_operation (pre-execution)."""
from __future__ import annotations

import importlib.util
import shlex
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

T = TypeVar("T")

_SAFE_LOCAL_MOD = None


def _load_safe_local():
    global _SAFE_LOCAL_MOD
    if _SAFE_LOCAL_MOD is not None:
        return _SAFE_LOCAL_MOD
    path = Path(__file__).resolve().parent / "safe_local_operation.py"
    spec = importlib.util.spec_from_file_location("git_guard_safe_local_operation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load safe_local_operation from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _SAFE_LOCAL_MOD = mod
    return mod


def _normalize_command(command: str) -> List[str]:
    text = (command or "").strip()
    if not text:
        return []
    if text.lower().startswith("git "):
        text = text[4:].strip()
    return shlex.split(text, posix=True)


def _paths_segment(paths: List[str]) -> str:
    return ",".join(paths) if paths else ""


def command_to_local_op_spec(command: str) -> Optional[str]:
    """
    Map a shell git command to guard --local-op pipe spec.
    Returns None if not a v2.2 destructive-local git operation (pass-through).
    """
    parts = _normalize_command(command)
    if not parts:
        return None
    verb = parts[0].lower()

    if verb in ("status", "diff", "log", "show", "fetch", "branch", "rev-parse", "merge-base"):
        return None

    if verb == "restore":
        staged = worktree = False
        source = ""
        paths: List[str] = []
        i = 1
        while i < len(parts):
            tok = parts[i]
            if tok == "--staged":
                staged = True
                i += 1
                continue
            if tok in ("--worktree", "-W"):
                worktree = True
                i += 1
                continue
            if tok.startswith("--source="):
                source = tok.split("=", 1)[1]
                i += 1
                continue
            if tok == "--source" and i + 1 < len(parts):
                source = parts[i + 1]
                i += 2
                continue
            paths.append(tok)
            i += 1
        flags = []
        if staged:
            flags.append("staged=1")
        if worktree:
            flags.append("worktree=1")
        if source:
            flags.append(f"source={source}")
        if not staged and not worktree and not source:
            worktree = True
            flags.append("worktree=1")
        return f"restore|{_paths_segment(paths)}|{'|'.join(flags) if flags else 'worktree=1'}"

    if verb == "checkout":
        if "--" in parts:
            idx = parts.index("--")
            paths = parts[idx + 1 :]
            if not paths:
                return None
            return f"checkout_path|{_paths_segment(paths)}"
        return None

    if verb == "reset":
        mode = "mixed"
        ref = "HEAD"
        paths: List[str] = []
        i = 1
        while i < len(parts):
            tok = parts[i]
            if tok in ("--soft", "--mixed", "--hard", "--merge"):
                mode = tok.lstrip("-")
                i += 1
                continue
            if tok.startswith("--"):
                i += 1
                continue
            if not paths and ref == "HEAD" and len(tok) >= 4:
                ref = tok
                i += 1
                continue
            paths.append(tok)
            i += 1
        path_seg = _paths_segment(paths) if paths else ""
        return f"reset|{path_seg}|mode={mode}|ref={ref}"

    if verb == "clean":
        dry = force = directories = ignored = False
        for tok in parts[1:]:
            if tok in ("-n", "--dry-run"):
                dry = True
            if tok in ("-f", "--force"):
                force = True
            if tok in ("-d", "--directory"):
                directories = True
            if tok in ("-x", "--ignored"):
                ignored = True
            if tok.startswith("-") and not tok.startswith("--") and len(tok) > 1:
                for ch in tok[1:]:
                    if ch == "n":
                        dry = True
                    elif ch == "f":
                        force = True
                    elif ch == "d":
                        directories = True
                    elif ch == "x":
                        ignored = True
        flags = [f"dry_run={1 if dry else 0}", f"force={1 if force else 0}"]
        if directories:
            flags.append("directories=1")
        if ignored:
            flags.append("ignored=1")
        return f"clean||{'|'.join(flags)}"

    if verb == "worktree" and len(parts) >= 3 and parts[1] == "remove":
        force = "--force" in parts
        path_candidates = [p for p in parts[2:] if p != "--force"]
        if not path_candidates:
            return "worktree_remove||force=1" if force else "worktree_remove||force=0"
        return f"worktree_remove|{path_candidates[0]}|force={1 if force else 0}"

    return None


def is_destructive_git_local_command(command: str) -> bool:
    return command_to_local_op_spec(command) is not None


def evaluate_agent_git_command(repo: str | Path, command: str) -> Dict[str, Any]:
    """Run v2.2 evaluator in-process (no subprocess guard). Fail-closed on errors."""
    repo_s = str(repo)
    spec = command_to_local_op_spec(command)
    if spec is None:
        return {
            "in_scope": False,
            "decision": "PASS_THROUGH",
            "command": command,
        }
    mod = _load_safe_local()
    try:
        op = mod.parse_local_op_spec(spec)
        decision, reason_code, detail = mod.evaluate_local_op(repo_s, op)
        explanation = mod.build_local_op_human_explanation(op, decision, reason_code, detail)
    except Exception as exc:  # noqa: BLE001 — fail-closed
        return {
            "in_scope": True,
            "decision": "NEED_HUMAN",
            "reason_code": "GATE_EVALUATOR_FAILURE",
            "detail": f"{type(exc).__name__}: {exc}",
            "command": command,
            "normalized_local_op": spec,
            "operation": "unknown",
            "operation_description": "destructive local git operation (evaluator failure)",
            "target_description": command,
            "effect_description": (
                "Safety could not be verified; execution is blocked until a human reviews."
            ),
        }
    return {
        "in_scope": True,
        "decision": decision.upper(),
        "reason_code": reason_code,
        "detail": detail,
        "command": command,
        "normalized_local_op": spec,
        "operation": op.get("operation"),
        **explanation,
    }


def format_human_gate_message(evaluation: Dict[str, Any]) -> str:
    decision = evaluation.get("decision", "")
    if decision == "PASS_THROUGH":
        return ""
    label = decision if decision in ("SAFE", "BLOCK", "NEED_HUMAN") else str(decision)
    return (
        f"判定: {label}\n\n"
        f"操作:\n{evaluation.get('operation_description', '')}\n\n"
        f"対象:\n{evaluation.get('target_description', '')}\n\n"
        f"今回の影響:\n{evaluation.get('effect_description', '')}\n"
    )


def gate_agent_shell_command(
    repo: str | Path,
    command: str,
    execute: Callable[[], T],
    *,
    human_decision_emit: Callable[[Dict[str, Any]], None] | None = None,
) -> Tuple[Optional[T], Dict[str, Any]]:
    """
    Pre-execution gate. Returns (result, gate_record).
    result is None when execution did not run (BLOCK / NEED_HUMAN / failure).
    """
    evaluation = evaluate_agent_git_command(repo, command)
    record: Dict[str, Any] = {
        "gate": "git_local_operation_v2_2_1",
        "evaluator_invocations": 1,
        "executor_invocations": 0,
        "evaluation": evaluation,
    }
    if not evaluation.get("in_scope"):
        record["executor_invocations"] = 1
        return execute(), record

    decision = str(evaluation.get("decision") or "").upper()
    if decision == "SAFE":
        record["executor_invocations"] = 1
        return execute(), record

    if decision == "BLOCK":
        record["blocked"] = True
        record["message"] = format_human_gate_message(evaluation)
        return None, record

    if decision == "NEED_HUMAN":
        record["need_human"] = True
        record["resume_connected"] = False
        record["message"] = format_human_gate_message(evaluation)
        if human_decision_emit is not None:
            human_decision_emit(evaluation)
        return None, record

    record["need_human"] = True
    record["message"] = format_human_gate_message(evaluation)
    return None, record


def block_tool_result_from_gate(
    tool_name: str,
    arguments: Any,
    gate_record: Dict[str, Any],
) -> Dict[str, Any]:
    evaluation = gate_record.get("evaluation") or {}
    return {
        "ok": False,
        "blocked_by_git_local_gate": True,
        "gate": "git_local_operation_v2_2_1",
        "tool_name": tool_name,
        "arguments": arguments if isinstance(arguments, dict) else {},
        "decision": evaluation.get("decision"),
        "reason_code": evaluation.get("reason_code"),
        "operation": evaluation.get("operation"),
        "normalized_local_op": evaluation.get("normalized_local_op"),
        "operation_description": evaluation.get("operation_description"),
        "target_description": evaluation.get("target_description"),
        "effect_description": evaluation.get("effect_description"),
        "message": gate_record.get("message"),
        "git_local_gate": gate_record,
    }


def need_human_tool_result_from_gate(
    tool_name: str,
    arguments: Any,
    gate_record: Dict[str, Any],
) -> Dict[str, Any]:
    evaluation = gate_record.get("evaluation") or {}
    return {
        "ok": False,
        "need_human_git_local_operation": True,
        "gate": "git_local_operation_v2_2_1",
        "tool_name": tool_name,
        "arguments": arguments if isinstance(arguments, dict) else {},
        "decision": "NEED_HUMAN",
        "reason_code": evaluation.get("reason_code"),
        "operation": evaluation.get("operation"),
        "normalized_local_op": evaluation.get("normalized_local_op"),
        "operation_description": evaluation.get("operation_description"),
        "target_description": evaluation.get("target_description"),
        "effect_description": evaluation.get("effect_description"),
        "message": gate_record.get("message"),
        "resume_connected": gate_record.get("resume_connected", False),
        "git_local_gate": gate_record,
    }
