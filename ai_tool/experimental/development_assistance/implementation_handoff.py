"""Research → Spec → Code → Test → Result handoff. Experimental adapter.

Does not judge safe / feasible / correct / buildable.
Does not auto-edit code on version-change questions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ai_tool.experimental.development_assistance.python_version_delta import parse_python_version_delta
from ai_tool.experimental.development_assistance.spec_to_experimental_tool import (
    source_contains_spec,
    write_experimental_client,
)

_IMPL = re.compile(
    r"作ってテスト|実際に作って|実装してテスト|コードを生成してテスト|を実装して",
    re.I,
)
_TEST_WRITE = re.compile(r"テストを書いて|テストを追加", re.I)
_CHANGE_EVAL = re.compile(r"変更が必要|何か変更|直しが必要|改修が必要", re.I)

# Judgment *needs* — not verdicts. Keep the list short; do not invent Facets.
_NEED_MAP = (
    ("api", re.compile(r"api|api_availability|availability", re.I)),
    ("version", re.compile(r"^version$|python_version", re.I)),
    ("runtime", re.compile(r"runtime|python_version", re.I)),
    ("license", re.compile(r"license", re.I)),
    ("environment", re.compile(r"environment|os|docker|hardware", re.I)),
    ("input", re.compile(r"api|evidence", re.I)),
    ("output", re.compile(r"api|evidence", re.I)),
    ("error_handling", re.compile(r"api|environment|evidence", re.I)),
    ("test_method", re.compile(r"evidence|environment", re.I)),
)


def is_implementation_intent(requirement: str) -> bool:
    return bool(_IMPL.search(requirement))


def is_test_write_intent(requirement: str) -> bool:
    return bool(_TEST_WRITE.search(requirement))


def is_change_eval_intent(requirement: str) -> bool:
    return bool(_CHANGE_EVAL.search(requirement))


def list_judgment_needs(
    requirement: str,
    coverage: dict[str, Any] | None,
    spec: dict[str, Any] | None,
) -> dict[str, Any]:
    """List information needed to judge later. No feasible/safe/correct."""
    cov = coverage or {}
    ids = list(cov.get("required") or []) + list(cov.get("candidates") or [])
    blob = " ".join(ids)
    needs: list[str] = []
    for name, pat in _NEED_MAP:
        if pat.search(blob) or pat.search(requirement):
            needs.append(name)
    if spec:
        if spec.get("api_notes") and "api" not in needs:
            needs.append("api")
        if spec.get("license") and spec.get("license") != "UNKNOWN" and "license" not in needs:
            needs.append("license")
        if spec.get("runtime") and "runtime" not in needs:
            needs.append("runtime")
    # Cap: do not flood. Prefer order in _NEED_MAP.
    ordered = [n for n, _ in _NEED_MAP if n in needs]
    return {
        "needs": ordered,
        "not_a_verdict": True,
        "forbidden_keys_absent": True,
        "note": "These are inputs for a later judgment, not a Discovery verdict.",
    }


def implement_from_spec(
    spec: dict[str, Any],
    dest_dir: Path | None = None,
) -> dict[str, Any]:
    written = write_experimental_client(spec, dest_dir=dest_dir)
    source = Path(written["path"]).read_text(encoding="utf-8")
    written["handoff_fields"] = source_contains_spec(source, spec)
    written["code_generated"] = True
    return written


def run_tool_tests() -> dict[str, Any]:
    """In-process tests of the experimental client. No live network."""
    from ai_tool.experimental.liba_demo_tool.client import parse_a_payload

    passed = 0
    failed: list[str] = []
    try:
        assert parse_a_payload('{"ok": true}') == {"ok": True}
        passed += 1
    except Exception as exc:  # noqa: BLE001 — record, do not guess
        failed.append(f"valid_object: {exc}")
    try:
        parse_a_payload("[1, 2]")
        failed.append("array_should_raise")
    except TypeError:
        passed += 1
    except Exception as exc:  # noqa: BLE001
        failed.append(f"array: {exc}")
    try:
        parse_a_payload("not-json")
        failed.append("invalid_json_should_raise")
    except Exception:
        passed += 1
    return {
        "passed": passed,
        "failed": failed,
        "ok": not failed,
        "live_network": False,
        "real_hardware": False,
    }


def evaluate_tool_change(
    requirement: str,
    *,
    spec: dict[str, Any] | None,
    session: dict[str, Any],
    tool_hash_before: str,
    tool_hash_after: str,
) -> dict[str, Any]:
    """O-8: detect Python change, refer to existing Tool, do not rewrite."""
    delta = parse_python_version_delta(requirement)
    requested = delta.selected
    current = ""
    if spec:
        current = str(spec.get("runtime") or "")
    if not current:
        current = str(session.get("tool_runtime") or session.get("last_python") or "")
    m = re.search(r"3\.\d+", current)
    current_token = m.group(0) if m else ""
    changed = bool(requested and current_token and requested != current_token)
    auto = tool_hash_before != tool_hash_after and bool(tool_hash_before)
    unknowns = []
    if changed:
        unknowns.append(
            f"Python {requested} compatibility of the generated Tool is not official evidence"
        )
    return {
        "version_change_detected": changed or bool(requested),
        "from_runtime": current_token,
        "to_runtime": requested,
        "existing_tool_referred": bool(spec or session.get("tool_path")),
        "change_needed": "UNKNOWN" if changed else "none_asserted",
        "auto_modified": auto,
        "proposal": (
            f"Do not apply Python {current_token} evidence to {requested}. "
            "Re-validate runtime before editing the Tool."
            if changed
            else "No Python replacement named."
        ),
        "unknowns": unknowns,
        "code_rewrite_forbidden": True,
    }
