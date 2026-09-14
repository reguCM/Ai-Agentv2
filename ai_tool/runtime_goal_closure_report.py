"""Read-only readiness report for one saved Production Handoff Runtime Goal."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from ai_tool.acceptance_meaning_completion import (
    assess_acceptance_meaning_completion_eligibility,
)
from ai_tool.dev_skill_pipeline import validate_handoff_packet
from ai_tool.goal_handoff_source_binding import validate_handoff_source_binding
from ai_tool.production_run_contract import validate_production_run_contract


def canonical_handoff_hash(handoff: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(handoff), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _check(name: str, status: str, **fields: Any) -> dict[str, Any]:
    return {"name": name, "status": status, **fields}


def build_runtime_goal_closure_report(
    session: Mapping[str, Any],
    *,
    mission: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Derive closure readiness without persisting, re-running, or changing a judgment.

    ``CLOSURE_READY`` means the existing saved facts jointly establish Runtime Goal
    completion. ``NOT_READY`` means a current fact explicitly blocks completion;
    ``INCONCLUSIVE`` means an identity or required source cannot be trusted.
    """
    checks: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    inconclusive = False

    handoff = session.get("production_handoff_packet")
    if not isinstance(handoff, Mapping):
        return {
            "status": "INCONCLUSIVE",
            "checks": [_check("handoff", "UNKNOWN", reason="missing_handoff")],
            "blockers": [{"code": "missing_handoff"}],
        }
    handoff = dict(handoff)
    mission_row = mission if isinstance(mission, Mapping) else None
    handoff_errors = [
        *validate_handoff_packet(handoff),
        *validate_handoff_source_binding(handoff, mission_row),
    ]
    if handoff_errors:
        checks.append(_check("handoff", "UNKNOWN", errors=sorted(set(handoff_errors))))
        blockers.append({"code": "invalid_handoff_identity", "errors": sorted(set(handoff_errors))})
        inconclusive = True
    else:
        checks.append(_check("handoff", "PASS", handoff_id=handoff.get("handoff_id")))

    handoff_hash = canonical_handoff_hash(handoff)
    runtime = session.get("production_runtime_snapshot")
    meaning_context = session.get("production_meaning_context")
    run_contract = session.get("production_run_contract")
    if not isinstance(run_contract, Mapping) or not isinstance(meaning_context, Mapping):
        checks.append(_check("run_contract", "UNKNOWN", reason="missing_run_contract_or_meaning_context"))
        blockers.append({"code": "missing_run_contract_or_meaning_context"})
        inconclusive = True
    elif mission_row is None:
        checks.append(_check("run_contract", "UNKNOWN", reason="missing_mission"))
        blockers.append({"code": "missing_mission"})
        inconclusive = True
    else:
        contract_errors = validate_production_run_contract(
            run_contract,
            mission=mission_row,
            handoff=handoff,
            meaning_context=meaning_context,
            handoff_canonical_hash=handoff_hash,
            runtime_snapshot=runtime if isinstance(runtime, Mapping) else None,
        )
        if contract_errors:
            checks.append(_check("run_contract", "UNKNOWN", errors=contract_errors))
            blockers.append({"code": "run_contract_mismatch", "errors": contract_errors})
            inconclusive = True
        else:
            checks.append(_check("run_contract", "PASS", execution_id=run_contract.get("started_execution_id")))

    integrity = session.get("production_runtime_handoff_integrity")
    if not isinstance(integrity, Mapping) or (
        str(integrity.get("handoff_id") or "") != str(handoff.get("handoff_id") or "")
        or str(integrity.get("canonical_hash") or "") != handoff_hash
    ):
        checks.append(_check("runtime_handoff_integrity", "UNKNOWN"))
        blockers.append({"code": "runtime_handoff_identity_mismatch"})
        inconclusive = True
    else:
        checks.append(_check("runtime_handoff_integrity", "PASS"))

    readiness = session.get("production_acceptance_readiness")
    if not isinstance(readiness, Mapping):
        checks.append(_check("acceptance_readiness", "UNKNOWN", reason="missing_acceptance_readiness"))
        blockers.append({"code": "missing_acceptance_readiness"})
        inconclusive = True
    elif not bool(readiness.get("acceptance_ready")):
        details = {
            key: list(readiness.get(key) or [])
            for key in ("incomplete_task_ids", "unresolved_failure_ids", "missing_evidence")
        }
        checks.append(_check("acceptance_readiness", "FAIL", **details))
        blockers.append({"code": "acceptance_not_ready", **details})
    else:
        checks.append(_check("acceptance_readiness", "PASS"))

    acceptance_row = session.get("production_acceptance_evaluation")
    acceptance = acceptance_row.get("result") if isinstance(acceptance_row, Mapping) else None
    if not isinstance(acceptance_row, Mapping) or not isinstance(acceptance, Mapping):
        checks.append(_check("acceptance", "UNKNOWN", reason="missing_acceptance_evaluation"))
        blockers.append({"code": "missing_acceptance_evaluation"})
        inconclusive = True
    elif (
        str(acceptance_row.get("handoff_id") or "") != str(handoff.get("handoff_id") or "")
        or str(acceptance_row.get("canonical_hash") or "") != handoff_hash
    ):
        checks.append(_check("acceptance", "UNKNOWN", reason="acceptance_handoff_identity_mismatch"))
        blockers.append({"code": "acceptance_handoff_identity_mismatch"})
        inconclusive = True
    else:
        acceptance_status = str(acceptance.get("status") or "")
        checks.append(_check("acceptance", "PASS" if acceptance_status == "PASS" else "FAIL", acceptance_status=acceptance_status))
        if acceptance_status != "PASS":
            blockers.append({"code": "acceptance_not_pass", "status": acceptance_status})

    eligibility = assess_acceptance_meaning_completion_eligibility(acceptance)
    if not bool(eligibility.get("completion_eligible")):
        checks.append(_check("meaning_completion_eligibility", "FAIL", blocking_criteria=eligibility.get("blocking_criteria") or []))
        blockers.append({"code": "meaning_not_completion_eligible", "blocking_criteria": eligibility.get("blocking_criteria") or []})
    else:
        checks.append(_check("meaning_completion_eligibility", "PASS"))

    judgment = session.get("production_goal_acceptance_judgment")
    if not isinstance(judgment, Mapping):
        checks.append(_check("goal_judgment", "UNKNOWN", reason="missing_goal_judgment"))
        blockers.append({"code": "missing_goal_judgment"})
        inconclusive = True
    elif (
        str(judgment.get("handoff_id") or "") != str(handoff.get("handoff_id") or "")
        or str(judgment.get("canonical_hash") or "") != handoff_hash
    ):
        checks.append(_check("goal_judgment", "UNKNOWN", reason="goal_judgment_handoff_identity_mismatch"))
        blockers.append({"code": "goal_judgment_handoff_identity_mismatch"})
        inconclusive = True
    elif not bool(judgment.get("goal_completed")):
        checks.append(_check("goal_judgment", "FAIL", goal_completed=False))
        blockers.append({"code": "goal_not_completed"})
    elif dict(judgment.get("completion_eligibility") or {}) != eligibility:
        checks.append(_check("goal_judgment", "UNKNOWN", reason="goal_judgment_eligibility_mismatch"))
        blockers.append({"code": "goal_judgment_eligibility_mismatch"})
        inconclusive = True
    else:
        checks.append(_check("goal_judgment", "PASS", goal_completed=True))

    goal_status = next(
        (
            str(row.get("status") or "")
            for row in ((runtime or {}).get("goals") or [])
            if isinstance(row, Mapping) and str(row.get("goal_id") or "") == "G1"
        ),
        "",
    )
    if goal_status != "complete":
        checks.append(
            _check(
                "runtime_goal",
                "UNKNOWN" if not goal_status else "FAIL",
                runtime_goal_status=goal_status or None,
            )
        )
        blockers.append({"code": "runtime_goal_not_complete", "status": goal_status or None})
        inconclusive = inconclusive or not goal_status
    else:
        checks.append(_check("runtime_goal", "PASS", runtime_goal_status=goal_status))

    status = "INCONCLUSIVE" if inconclusive else "CLOSURE_READY" if not blockers else "NOT_READY"
    return {
        "status": status,
        "handoff_id": handoff.get("handoff_id"),
        "run_execution_id": (run_contract or {}).get("started_execution_id") if isinstance(run_contract, Mapping) else None,
        "checks": checks,
        "blockers": blockers,
    }


__all__ = ["build_runtime_goal_closure_report", "canonical_handoff_hash"]
