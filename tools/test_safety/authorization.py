"""S5a — Authoritative Test Safety Authorization binding (no pytest execution)."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from test_safety.plan_fingerprint import (
    compute_plan_fingerprint,
    fingerprint_from_evaluation_packet,
)
from test_safety.shadow_gate import (
    INVALID_GATE_REASON,
    SUPPORTED_EVALUATION_SCHEMA_VERSIONS,
    validate_shadow_gate_schema,
)
from test_safety.validator import validate_packet_schema

BINDER_ID = "test_safety_authorization_binder_s5a_v1"
AUTH_AUTHORIZED = "AUTHORIZED"
AUTH_DENIED = "DENIED"

DENY_GATE_BLOCKED = "GATE_BLOCKED"
DENY_MISSING_EVALUATION = "MISSING_EVALUATION"
DENY_INVALID_EVALUATION = "INVALID_EVALUATION"
DENY_INVALID_GATE_PACKET = "INVALID_GATE_PACKET"
DENY_UNKNOWN_SCHEMA_VERSION = "UNKNOWN_SCHEMA_VERSION"
DENY_ACTION_ID_MISMATCH = "ACTION_ID_MISMATCH"
DENY_PLAN_FINGERPRINT_MISMATCH = "PLAN_FINGERPRINT_MISMATCH"
DENY_EVALUATION_REF_MISMATCH = "EVALUATION_REF_MISMATCH"
DENY_STALE_EVALUATION = "STALE_EVALUATION"
DENY_HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"


def normalize_evaluation_ref(ref: Mapping[str, Any] | None) -> dict[str, str]:
    if not ref:
        return {}
    out: dict[str, str] = {}
    for key in ("schema_version", "packet_type", "validator_id", "generated_at", "reference_case_id"):
        if ref.get(key) is not None and str(ref.get(key)).strip():
            out[key] = str(ref[key])
    return out


def evaluation_ref_from_packet(packet: Mapping[str, Any]) -> dict[str, str]:
    ref: dict[str, str] = {
        "schema_version": str(packet.get("schema_version") or ""),
        "packet_type": str(packet.get("packet_type") or ""),
        "validator_id": str(packet.get("validator_id") or ""),
        "generated_at": str(packet.get("generated_at") or ""),
    }
    if packet.get("reference_case_id"):
        ref["reference_case_id"] = str(packet["reference_case_id"])
    return ref


def evaluation_refs_match(a: Mapping[str, Any] | None, b: Mapping[str, Any] | None) -> bool:
    return normalize_evaluation_ref(a) == normalize_evaluation_ref(b)


def authorization_binding_key(
    action_id: str,
    plan_fingerprint: str,
    evaluation_ref: Mapping[str, Any],
) -> str:
    ref_json = json.dumps(normalize_evaluation_ref(evaluation_ref), sort_keys=True, separators=(",", ":"))
    payload = f"{action_id}\n{plan_fingerprint}\n{ref_json}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verify_gate_packet(
    gate_packet: Mapping[str, Any] | None,
    *,
    gate_schema_path: Path | None,
) -> str | None:
    if not gate_packet:
        return DENY_INVALID_GATE_PACKET
    if gate_packet.get("packet_type") != "TEST_SAFETY_SHADOW_GATE":
        return DENY_INVALID_GATE_PACKET
    if str(gate_packet.get("schema_version")) not in SUPPORTED_EVALUATION_SCHEMA_VERSIONS:
        return DENY_UNKNOWN_SCHEMA_VERSION
    if gate_schema_path is not None and gate_schema_path.is_file():
        try:
            validate_shadow_gate_schema(dict(gate_packet), gate_schema_path)
        except Exception:
            return DENY_INVALID_GATE_PACKET
    if gate_packet.get("gate_reason") == INVALID_GATE_REASON:
        return DENY_INVALID_GATE_PACKET
    return None


def _verify_evaluation_packet(
    evaluation_packet: Mapping[str, Any] | None,
    *,
    eval_schema_path: Path | None,
) -> str | None:
    if not evaluation_packet:
        return DENY_MISSING_EVALUATION
    if evaluation_packet.get("packet_type") != "TEST_SAFETY_EVALUATION":
        return DENY_INVALID_EVALUATION
    if str(evaluation_packet.get("schema_version")) not in SUPPORTED_EVALUATION_SCHEMA_VERSIONS:
        return DENY_UNKNOWN_SCHEMA_VERSION
    if eval_schema_path is not None and eval_schema_path.is_file():
        try:
            validate_packet_schema(dict(evaluation_packet), eval_schema_path)
        except Exception:
            return DENY_INVALID_EVALUATION
    if not isinstance(evaluation_packet.get("test_plan"), Mapping):
        return DENY_INVALID_EVALUATION
    return None


def bind_test_safety_authorization(
    *,
    action_id: str,
    current_plan: Mapping[str, Any],
    evaluation_packet: Mapping[str, Any] | None,
    gate_packet: Mapping[str, Any] | None,
    eval_schema_path: Path | None = None,
    gate_schema_path: Path | None = None,
    expected_action_id: str | None = None,
    expected_evaluation_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Bind gate decision to action + plan fingerprint. Does not execute tests.

    expected_action_id / expected_evaluation_ref support verify-style negative tests.
    """
    issued_at = datetime.now(timezone.utc).isoformat()
    action_token = str(action_id or "").strip()
    reasons: list[str] = []

    def denied(
        reason: str,
        extra: dict[str, Any] | None = None,
        *,
        evaluation_ref: Mapping[str, str] | None = None,
        plan_fp: str = "",
        postflight: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        ref = dict(evaluation_ref or _empty_evaluation_ref())
        row = _build_packet(
            authorization=AUTH_DENIED,
            action_id=action_token,
            plan_fingerprint=plan_fp,
            evaluation_ref=ref,
            gate_decision=str((gate_packet or {}).get("gate_decision") or "BLOCKED"),
            reasons=[reason],
            required_postflight=postflight or {"postflight_git_check_required": False},
            issued_at=issued_at,
            binding_key="",
        )
        if extra:
            row.update(extra)
        return row

    if not action_token:
        return denied(DENY_ACTION_ID_MISMATCH)

    if expected_action_id is not None and str(expected_action_id).strip() != action_token:
        return denied(DENY_ACTION_ID_MISMATCH)

    eval_err = _verify_evaluation_packet(evaluation_packet, eval_schema_path=eval_schema_path)
    if eval_err:
        return denied(eval_err)

    gate_err = _verify_gate_packet(gate_packet, gate_schema_path=gate_schema_path)
    if gate_err:
        return denied(gate_err)

    evaluation_packet = evaluation_packet  # type: ignore[assignment]
    gate_packet = gate_packet  # type: ignore[assignment]

    eval_ref = evaluation_ref_from_packet(evaluation_packet)
    gate_ref = normalize_evaluation_ref(gate_packet.get("evaluation_ref"))

    if expected_evaluation_ref is not None and not evaluation_refs_match(
        expected_evaluation_ref, eval_ref
    ):
        return denied(DENY_EVALUATION_REF_MISMATCH)

    if not evaluation_refs_match(eval_ref, gate_ref):
        return denied(DENY_EVALUATION_REF_MISMATCH, evaluation_ref=eval_ref)

    gate_decision = str(gate_packet.get("gate_decision") or "BLOCKED")
    if gate_decision != "PASS":
        return denied(
            DENY_GATE_BLOCKED,
            evaluation_ref=eval_ref,
            postflight=gate_packet.get("required_postflight"),
        )

    if gate_packet.get("human_approval_required"):
        return denied(
            DENY_HUMAN_APPROVAL_REQUIRED,
            evaluation_ref=eval_ref,
            postflight=gate_packet.get("required_postflight"),
        )

    try:
        current_fp = compute_plan_fingerprint(current_plan)
        evaluated_fp = fingerprint_from_evaluation_packet(evaluation_packet)
    except (ValueError, TypeError):
        return denied(DENY_INVALID_EVALUATION)

    if current_fp != evaluated_fp:
        return denied(
            DENY_PLAN_FINGERPRINT_MISMATCH,
            extra={"evaluated_plan_fingerprint": evaluated_fp},
            evaluation_ref=eval_ref,
            plan_fp=current_fp,
            postflight=gate_packet.get("required_postflight"),
        )

    postflight = dict(gate_packet.get("required_postflight") or {"postflight_git_check_required": False})

    binding_key = authorization_binding_key(action_token, current_fp, eval_ref)
    return _build_packet(
        authorization=AUTH_AUTHORIZED,
        action_id=action_token,
        plan_fingerprint=current_fp,
        evaluation_ref=eval_ref,
        gate_decision=gate_decision,
        reasons=[],
        required_postflight=postflight,
        issued_at=issued_at,
        binding_key=binding_key,
    )


def verify_authorization_for_execution(
    authorization_packet: Mapping[str, Any],
    *,
    action_id: str,
    current_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-check binding at execution time (S5b+); S5a tests use this for stale/action negatives."""
    if authorization_packet.get("authorization") != AUTH_AUTHORIZED:
        return dict(authorization_packet)

    token = str(action_id or "").strip()
    if token != str(authorization_packet.get("action_id") or ""):
        return _deny_from_auth(authorization_packet, DENY_ACTION_ID_MISMATCH)

    try:
        current_fp = compute_plan_fingerprint(current_plan)
    except ValueError:
        return _deny_from_auth(authorization_packet, DENY_INVALID_EVALUATION)

    if current_fp != str(authorization_packet.get("plan_fingerprint") or ""):
        return _deny_from_auth(authorization_packet, DENY_STALE_EVALUATION)

    return dict(authorization_packet)


def _empty_evaluation_ref() -> dict[str, str]:
    return {
        "schema_version": "",
        "packet_type": "",
        "validator_id": "",
        "generated_at": "",
    }


def _deny_from_auth(auth: Mapping[str, Any], reason: str) -> dict[str, Any]:
    out = dict(auth)
    out["authorization"] = AUTH_DENIED
    out["reason"] = reason
    out["reasons"] = [reason]
    return out


def _build_packet(
    *,
    authorization: str,
    action_id: str,
    plan_fingerprint: str,
    evaluation_ref: Mapping[str, str],
    gate_decision: str,
    reasons: list[str],
    required_postflight: Mapping[str, Any],
    issued_at: str,
    binding_key: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "packet_type": "TEST_SAFETY_AUTHORIZATION",
        "binder_id": BINDER_ID,
        "authorization_id": str(uuid.uuid4()),
        "authorization_binding_key": binding_key,
        "execution_authoritative": True,
        "execution_connected": False,
        "action_id": action_id,
        "plan_fingerprint": plan_fingerprint,
        "evaluation_ref": dict(evaluation_ref),
        "gate_decision": gate_decision,
        "authorization": authorization,
        "issued_at": issued_at,
        "reasons": reasons,
        "reason": reasons[0] if reasons else None,
        "required_postflight": dict(required_postflight),
    }


def validate_authorization_schema(packet: Mapping[str, Any], schema_path: Path) -> None:
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(packet)
