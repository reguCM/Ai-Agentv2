"""Phase 1 Task Fingerprint *candidate* builder.

Logs a Selector-compatible features sketch. Does NOT import or call
diagnostic_framework.selector. selector_invoked is always false.
"""

from __future__ import annotations

from typing import Any

# Keys aligned with diagnostic_framework/selector/rules.json (contract for Phase 2+)
KNOWN_FEATURE_KEYS = (
    "has_runtime_logs",
    "code_available",
    "path_unknown_or_untrusted",
    "suspect_ranking_vs_filter",
    "suspect_stdout_vs_llm_handoff",
    "suspect_off_path_causes",
    "needs_path_integration",
    "needs_local_analysis",
    "intent_map_needed",
    "caller_complex",
    "long_logs_small_ctx",
    "optional_short_edge_probe",
)


def build_fingerprint_candidate(
    cognitive: dict[str, Any],
    *,
    feature_overrides: dict[str, Any] | None = None,
    problem_id: str | None = None,
    tool: str | None = None,
) -> dict[str, Any]:
    """Derive a *candidate* fingerprint from Cognitive State + optional human overrides.

    Heuristics are conservative and marked as such. Phase 1 does not run Selector.
    """
    overrides = dict(feature_overrides or {})
    text_blob = " ".join(
        [
            str(cognitive.get("goal") or ""),
            str(cognitive.get("intent") or ""),
            " ".join(c.get("text") or "" for c in cognitive.get("claims") or []),
            " ".join(h.get("text") or "" for h in cognitive.get("hypotheses") or []),
            " ".join(u.get("text") or "" for u in cognitive.get("unresolved_questions") or [] if u.get("status") == "open"),
        ]
    ).lower()

    features: dict[str, Any] = {k: False for k in KNOWN_FEATURE_KEYS}
    # Weak keyword hints only — must not be treated as ground truth
    hints: list[str] = []
    if any(w in text_blob for w in ("log", "ログ", "観測", "runtime", "snippet")):
        features["has_runtime_logs"] = True
        hints.append("keyword:logs")
    if any(w in text_blob for w in ("code", "コード", "実装", "source")):
        features["code_available"] = True
        hints.append("keyword:code")
    if any(w in text_blob for w in ("ranking", "filter", "collect", "収集")):
        features["suspect_ranking_vs_filter"] = True
        hints.append("keyword:ranking_filter")
    if any(w in text_blob for w in ("handoff", "stdout", "json.dumps", "受け渡", "llmへ")):
        features["suspect_stdout_vs_llm_handoff"] = True
        features["needs_path_integration"] = True
        hints.append("keyword:handoff")
    if any(w in text_blob for w in ("経路", "caller", "複数ファイル", "multi")):
        features["path_unknown_or_untrusted"] = True
        features["caller_complex"] = True
        features["needs_path_integration"] = True
        hints.append("keyword:path")
    if cognitive.get("hypotheses") or cognitive.get("unresolved_questions"):
        features["needs_local_analysis"] = True
        hints.append("has_hypotheses_or_unresolved")

    for key, value in overrides.items():
        if key in KNOWN_FEATURE_KEYS:
            features[key] = value

    open_n = sum(1 for u in cognitive.get("unresolved_questions") or [] if u.get("status") == "open")
    uncertainty = "high" if open_n >= 3 else ("medium" if open_n >= 1 else "low")

    return {
        "schema_version": "0.1",
        "kind": "task_fingerprint_candidate",
        "phase": "cognitive_phase1",
        "problem_id": problem_id or f"candidate_{cognitive.get('session_id')}",
        "tool": tool,
        "task_type": "code_diagnosis_or_understanding",
        "from_cognitive_session_id": cognitive.get("session_id"),
        "features": features,
        "feature_source": {
            "keyword_hints": hints,
            "overrides": sorted(overrides.keys()),
            "note": "Phase 1 candidate only. Not ground truth. Not fed to Selector.",
        },
        "uncertainty": {
            "level": uncertainty,
            "open_unresolved_count": open_n,
            "do_not_use_self_reported_llm_confidence": True,
        },
        "selector": {
            "invoked": False,
            "invokable_later": True,
            "contract": "features keys align with diagnostic_framework/selector/rules.json",
        },
        "auto_fix_allowed": False,
    }
