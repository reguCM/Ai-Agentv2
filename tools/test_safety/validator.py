"""S2 — READ-ONLY Test Safety Validator (no execution Gate)."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALIDATOR_ID = "test_safety_validator_s2_prototype_v1"

DIMENSION_KEYS = (
    "llm",
    "gpu",
    "network",
    "subprocess",
    "long_running_process",
    "tool_execution",
    "filesystem_write",
    "repository_outside_write",
    "git_operation",
    "external_service",
    "credentials",
    "shared_resource",
)

DEFAULT_DIMENSIONS: dict[str, str] = {k: "NONE" for k in DIMENSION_KEYS}


def _merge_dimensions(base: dict[str, str], overrides: dict[str, Any] | None) -> dict[str, str]:
    out = dict(base)
    if not overrides:
        return out
    for key, value in overrides.items():
        if key in out and value in ("NONE", "CONTROLLED", "PRESENT", "UNKNOWN"):
            out[key] = value
    return out


def _infer_from_commands(commands: list[str]) -> tuple[str, list[str], dict[str, str], list[str]]:
    """Return primary level, also levels, dimensions, warnings."""
    text = " ".join(commands).casefold()
    dims = dict(DEFAULT_DIMENSIONS)
    warnings: list[str] = []
    also: list[str] = []

    if "pytest" in text:
        dims["subprocess"] = "CONTROLLED"

    if any(tok in text for tok in ("ollama", "openai", "anthropic", "live llm", "real llm")):
        dims["llm"] = "PRESENT"
    if "fake_chat" in text or "monkeypatch" in text or "mock" in text:
        if dims["llm"] == "NONE":
            dims["llm"] = "NONE"
        else:
            warnings.append("llm_keywords_mixed_with_mock_declarations_review_plan")

    if "127.0.0.1" in text or "localhost" in text:
        dims["network"] = "CONTROLLED"
    elif any(tok in text for tok in ("http://", "https://", "curl ", "wget ")):
        if "127.0.0.1" not in text and "localhost" not in text:
            dims["network"] = "PRESENT"

    if any(tok in text for tok in ("gpu", "cuda", "nvidia-smi")):
        dims["gpu"] = "PRESENT"

    if "git commit" in text or "git push" in text or "git reset" in text:
        dims["git_operation"] = "PRESENT"

    if "tmp_path" in text or "monkeypatch.chdir(tmp_path)" in text:
        dims["filesystem_write"] = "CONTROLLED"
    elif "runs/chat_ui" in text or "repository write" in text:
        dims["filesystem_write"] = "PRESENT"
        warnings.append("repository_filesystem_write_declared_or_inferred")

    if "stage7" in text or "spawn_production" in text:
        dims["tool_execution"] = "PRESENT"
        dims["long_running_process"] = "PRESENT"

    primary = "LEVEL_1"
    if dims["llm"] == "PRESENT" or dims["gpu"] == "PRESENT" or dims["network"] == "PRESENT":
        primary = "LEVEL_3"
        also = []
    elif (
        dims["subprocess"] == "CONTROLLED"
        and (dims["network"] == "CONTROLLED" or "integration" in text or "httpconnection" in text)
    ) or dims["filesystem_write"] == "PRESENT":
        primary = "LEVEL_2"
        also = ["LEVEL_1"]

    if dims["tool_execution"] == "PRESENT" and primary != "LEVEL_3":
        also = list(dict.fromkeys([*also, "LEVEL_2"]))

    return primary, also, dims, warnings


def _apply_declared_write_scope(
    write_scope: list[str],
    dims: dict[str, str],
    warnings: list[str],
) -> None:
    if not write_scope:
        return
    for entry in write_scope:
        low = entry.casefold()
        if "tmp" in low or "pytest" in low or "conftest" in low:
            if dims["filesystem_write"] == "NONE":
                dims["filesystem_write"] = "CONTROLLED"
        elif "repo" in low or "repository" in low or "runs/" in entry:
            dims["filesystem_write"] = "PRESENT"
            warnings.append(f"declared_write_scope:{entry}")
        else:
            warnings.append(f"undeclared_write_scope_pattern:{entry}")


def _evaluate_unknowns(
    dims: dict[str, str],
    plan: dict[str, Any],
    host_notes: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    primary = str(plan.get("_primary") or "LEVEL_1")

    def add(dim: str, observation: str, relevant: bool, verifiable: bool) -> None:
        block = relevant and not verifiable
        rows.append(
            {
                "dimension": dim,
                "observation": observation,
                "relevant_to_plan": relevant,
                "safety_verifiable": verifiable,
                "would_block_if_gate_connected": block,
            }
        )

    if dims.get("long_running_process") == "UNKNOWN" or host_notes:
        for note in host_notes:
            relevant = dims.get("llm") == "PRESENT" or dims.get("subprocess") == "PRESENT"
            if primary == "LEVEL_1" and dims.get("llm") == "NONE":
                relevant = False
            add("long_running_process", note, relevant, False if note else True)

    if dims.get("shared_resource") == "UNKNOWN":
        add("shared_resource", "not assessed", False, True)

    for dim, state in dims.items():
        if state == "UNKNOWN":
            relevant = dim in ("llm", "gpu", "network", "subprocess") and primary != "LEVEL_1"
            add(dim, f"dimension_state=UNKNOWN", relevant, False)

    return rows


def _advisory_gate_mirror(
    evaluation: dict[str, Any],
    warnings: list[str],
) -> tuple[str, list[str], bool, bool, str]:
    """Mirror Shadow Gate for S2 advisory fields only; authoritative gate is separate."""
    from test_safety.shadow_gate import _postflight_required, decide_gate_from_evaluation

    decision, blocked, _, human, human_reason = decide_gate_from_evaluation(
        evaluation, validator_warnings=warnings
    )
    postflight_git = _postflight_required(evaluation)
    return decision, blocked, postflight_git, human, human_reason


def evaluate_test_plan(
    plan: dict[str, Any],
    *,
    repo_root: Path | None = None,
    host_process_notes: list[str] | None = None,
    reference_case_id: str | None = None,
) -> dict[str, Any]:
    """Build TEST_SAFETY_EVALUATION packet (advisory; does not run tests)."""
    commands = [str(c) for c in (plan.get("commands") or []) if str(c).strip()]
    if not commands:
        raise ValueError("test_plan.commands required")

    primary, also, dims, warnings = _infer_from_commands(commands)
    declared_level = plan.get("declared_primary_risk_level")
    if declared_level in ("LEVEL_1", "LEVEL_2", "LEVEL_3"):
        primary = declared_level

    dims = _merge_dimensions(dims, plan.get("declared_dimensions"))
    _apply_declared_write_scope(
        [str(x) for x in (plan.get("declared_write_scope") or [])],
        dims,
        warnings,
    )

    plan_copy = {
        "plan_id": str(plan.get("plan_id") or "unnamed"),
        "description": str(plan.get("description") or ""),
        "commands": commands,
        "declared_write_scope": list(plan.get("declared_write_scope") or []),
        "notes": str(plan.get("notes") or ""),
    }
    if declared_level:
        plan_copy["declared_primary_risk_level"] = declared_level
    if plan.get("declared_dimensions"):
        plan_copy["declared_dimensions"] = dict(plan["declared_dimensions"])

    plan_copy["_primary"] = primary  # internal for unknown relevance
    unknowns = _evaluate_unknowns(dims, plan_copy, list(host_process_notes or []))
    del plan_copy["_primary"]

    evaluation_stub: dict[str, Any] = {
        "primary_risk_level": primary,
        "also_applies_risk_levels": also,
        "safety_dimensions": dims,
        "relevant_unknowns": unknowns,
        "warnings": warnings,
    }
    decision, blocked, postflight_git, human, human_reason = _advisory_gate_mirror(
        evaluation_stub, warnings
    )

    obs: dict[str, Any] = {}
    if repo_root is not None:
        obs["git"] = _git_readonly_snapshot(repo_root)
    if host_process_notes:
        obs["host_process_note"] = "; ".join(host_process_notes)

    evaluation: dict[str, Any] = {
        "primary_risk_level": primary,
        "also_applies_risk_levels": also,
        "safety_dimensions": dims,
        "relevant_unknowns": unknowns,
        "warnings": warnings,
        "recommended_gate_decision": decision,
        "gate_blocked_reasons": blocked,
        "postflight_git_check_required": postflight_git,
        "human_approval_required": human,
    }
    if human_reason:
        evaluation["human_approval_reason"] = human_reason

    packet: dict[str, Any] = {
        "schema_version": "1",
        "packet_type": "TEST_SAFETY_EVALUATION",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validator_id": VALIDATOR_ID,
        "test_plan": plan_copy,
        "evaluation": evaluation,
    }
    if reference_case_id:
        packet["reference_case_id"] = reference_case_id
    if obs:
        packet["readonly_observations"] = obs
    return packet


def _git_readonly_snapshot(repo_root: Path) -> dict[str, Any]:
    from test_safety.git_snapshot import git_worktree_snapshot

    snap = git_worktree_snapshot(repo_root)
    return {
        "branch": snap.get("branch"),
        "head": snap.get("head"),
        "status_short": snap.get("status_short"),
    }


def load_reference_case(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "test_plan" not in data:
        raise ValueError("reference case must contain test_plan")
    return data


def validate_packet_schema(packet: dict[str, Any], schema_path: Path) -> None:
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(packet)
