"""Persist Cognitive State sessions for human review (Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.ai.state.cognitive_fingerprint import build_fingerprint_candidate
from tools.ai.state.cognitive_state import render_cognitive_markdown, snapshot_cognitive

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "cognitive_sessions"


def session_dir(session_id: str, *, root: Path | None = None) -> Path:
    base = root or DEFAULT_ROOT
    path = base / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_session(
    state: dict[str, Any],
    *,
    root: Path | None = None,
    feature_overrides: dict[str, Any] | None = None,
    problem_id: str | None = None,
    tool: str | None = None,
) -> Path:
    """Write state.json, COGNITIVE_STATE.md, fingerprint_candidate.json, append audit.jsonl."""
    sid = state["session_id"]
    path = session_dir(sid, root=root)
    (path / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (path / "COGNITIVE_STATE.md").write_text(
        render_cognitive_markdown(state),
        encoding="utf-8",
    )
    fp = build_fingerprint_candidate(
        state,
        feature_overrides=feature_overrides,
        problem_id=problem_id,
        tool=tool,
    )
    (path / "fingerprint_candidate.json").write_text(
        json.dumps(fp, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (path / "audit_full.json").write_text(
        json.dumps(state.get("audit") or [], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # before/after helper for last change
    audits = state.get("audit") or []
    if audits:
        last = audits[-1]
        (path / "LAST_CHANGE.md").write_text(
            "\n".join(
                [
                    "# Last Cognitive Change",
                    "",
                    f"- at: {last.get('at')}",
                    f"- action: `{last.get('action')}`",
                    f"- reason_code: `{last.get('reason_code')}`",
                    f"- note: {last.get('note')}",
                    "",
                    "## before_excerpt",
                    "",
                    "```json",
                    json.dumps(last.get("before_excerpt"), ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "## after_excerpt",
                    "",
                    "```json",
                    json.dumps(last.get("after_excerpt"), ensure_ascii=False, indent=2),
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    (path / "README.md").write_text(
        "\n".join(
            [
                "# Cognitive session (Phase 1)",
                "",
                "Human-reviewable Cognitive State. Selector and Tools are **not** invoked.",
                "",
                "| File | Role |",
                "|------|------|",
                "| `COGNITIVE_STATE.md` | visualization |",
                "| `state.json` | machine snapshot |",
                "| `fingerprint_candidate.json` | future Selector input candidate (not executed) |",
                "| `audit_full.json` | change log |",
                "| `LAST_CHANGE.md` | latest update diff excerpt |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def load_session(session_id: str, *, root: Path | None = None) -> dict[str, Any]:
    path = (root or DEFAULT_ROOT) / session_id / "state.json"
    return json.loads(path.read_text(encoding="utf-8"))


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Lightweight structural compare for tests / CLI."""
    keys = ("goal", "intent", "claims", "hypotheses", "evidence", "unresolved_questions", "human_review")
    return {
        "before": {k: snapshot_cognitive(before).get(k) for k in keys},
        "after": {k: snapshot_cognitive(after).get(k) for k in keys},
        "changed_keys": [k for k in keys if before.get(k) != after.get(k)],
    }
