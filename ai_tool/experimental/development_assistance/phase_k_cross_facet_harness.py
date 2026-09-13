"""Phase K — offline evaluation of existing TDA structures on robot control facets.

Not a Reasoning / Matrix / Relationship Core. Probes only:
1. What official dataclasses keep vs drop
2. What existing consumers emit (reuse, goals, decision factors, ideas)
3. Whether facet-value conjunction vs conflict/transition prose changes answers
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.development_assistance.decision_factors import (
    compare_candidates_for_decision,
    compute_decision_factors,
)
from ai_tool.experimental.development_assistance.goal_abstraction import (
    abstract_goals,
    discover_capabilities,
)
from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog, PreservedIdea
from ai_tool.experimental.development_assistance.phase_k_cross_facet_fixtures import (
    FACET_ONLY_POST_DISCONNECT,
    K7_REQUIREMENT_EN,
    K7_REQUIREMENT_JA,
    RELATIONSHIP_TRANSITIONS,
    facet_only_record_payload,
    question_catalog,
    relationship_record_payload,
    typed_research_record_payload,
    unknown_cycle_record_payload,
    version_mix_record_payload,
)
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import (
    assess_reuse,
    extract_requirement_facets,
    reuse_conversation_material,
)
from ai_tool.experimental.development_assistance.research_state import ResearchState
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.version_facts import version_facts_from_candidate

Verdict = Literal["YES", "NO", "UNKNOWN", "CONDITIONAL"]
Policy = Literal["facet_values", "typed_record", "unsafe_transport_proxy"]

_REPO = Path(__file__).resolve().parents[3]
_PHASE_J_JSON = (
    _REPO / "docs" / "ai_tool" / "project_audit" / "research_records" / "RR_INDUSTRIAL_ROBOT_CONTROL_MODEL.json"
)

_TYPED_FIELD_NAMES = {f.name for f in fields(ResearchRecord)}


def load_phase_j_raw() -> dict[str, Any]:
    return json.loads(_PHASE_J_JSON.read_text(encoding="utf-8"))


def research_record_from_payload(payload: dict[str, Any]) -> ResearchRecord:
    """Official dataclass load — extra keys (transitions, etc.) are still dropped."""
    filtered = {k: v for k, v in payload.items() if k in _TYPED_FIELD_NAMES}
    return ResearchRecord(**filtered)


def dropped_keys(payload: dict[str, Any]) -> list[str]:
    return sorted(k for k in payload if k not in _TYPED_FIELD_NAMES)


def existing_capability_audit() -> dict[str, Any]:
    raw = load_phase_j_raw()
    typed = research_record_from_payload(raw)
    typed_keys = set(typed.to_dict().keys())
    return {
        "modules": {
            "ResearchRecord": "typed fields include optional facet_records[]",
            "facet_records[]": "Phase J JSON + ResearchRecord field (Phase M envelope, not a Core)",
            "Evidence": "sources[] + api_observations[] prose",
            "VersionFact": "python/cuda/os/license oriented; extra applies_to keys survive only as raw dicts on ResearchRecord.version_facts",
            "ResearchState": "session unknowns/conflicts; no facet join API",
            "ResearchReuse": "tech names polars/urscript/python/cuda — not control_authority",
            "GoalAbstraction": "UR/PolyScope pattern derives API Observation, not Ownership Release",
            "DecisionFactor": "version/license/python — not authority",
            "ConflictUnknown": "opaque lists; no graph API",
            "IdeaPreservation": "token overlap on idea name / trigger",
            "StandardWorkflow": "Gate → Goals → Reuse → Decision on candidates",
        },
        "phase_j_raw_extra_keys": dropped_keys(raw),
        "typed_field_names": sorted(typed_keys),
        "facet_records_on_typed": "facet_records" in typed.to_dict(),
        "conflicts_on_typed": bool(typed.conflicts),
        "unknowns_on_typed": bool(typed.unknowns),
        "environment_facts_on_typed": dict(typed.environment_facts),
        "version_fact_dataclass_drops_does_not_apply": "does_not_apply"
        not in version_facts_from_candidate(raw["technology_candidates"][0]).to_dict(),
        "version_facts_dict_keeps_does_not_apply": any(
            "does_not_apply" in vf for vf in typed.version_facts if isinstance(vf, dict)
        ),
    }


def _blob(record: ResearchRecord) -> str:
    parts = [
        json.dumps(record.conflicts, ensure_ascii=False),
        json.dumps(record.unknowns, ensure_ascii=False),
        json.dumps(record.api_observations, ensure_ascii=False),
        json.dumps(record.version_facts, ensure_ascii=False),
        json.dumps(record.environment_facts, ensure_ascii=False),
        record.requirement,
        record.topic,
    ]
    return " ".join(parts).lower()


def _facet_map(record: ResearchRecord | None, facets: dict[str, str] | None) -> dict[str, str]:
    out = dict(facets or {})
    if record is not None:
        for k, v in record.environment_facts.items():
            out.setdefault(k, str(v))
    return {k: str(v) for k, v in out.items()}


def _has(blob: str, *needles: str) -> bool:
    return all(n.lower() in blob for n in needles)


@dataclass
class ProbeResult:
    policy: str
    probe: str
    verdict: Verdict
    rationale: str
    evidence_used: list[str]
    false_inference: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe_facet_values(probe: str, facets: dict[str, str]) -> ProbeResult:
    """Named facet values only — no conflicts, no transitions, no vendor analogy."""
    f = {k.lower(): str(v) for k, v in facets.items()}
    transport = f.get("transport", "")
    mode = f.get("operational_mode", "")
    source = f.get("operational_mode_source", "") or f.get("ownership", "")
    authority = f.get("control_authority", "")
    cycle = f.get("cycle_controller", "")
    program = f.get("program_state", "")
    remote = f.get("remote_control", "")

    def ev(*keys: str) -> list[str]:
        return [f"{k}={facets.get(k) or f.get(k, '')}" for k in keys if k in facets or k in f]

    if probe == "transport_disconnected":
        if transport == "disconnected":
            return ProbeResult("facet_values", probe, "YES", "transport facet is disconnected", ev("transport"), False)
        if transport in {"connected", "established"}:
            return ProbeResult("facet_values", probe, "NO", "transport facet is connected", ev("transport"), False)
        return ProbeResult("facet_values", probe, "UNKNOWN", "transport facet missing", [], False)

    if probe == "disconnect_clears_mode":
        if mode.upper() == "AUTOMATIC" or source.lower() == "dashboard" or authority.lower() == "dashboard":
            return ProbeResult(
                "facet_values",
                probe,
                "NO",
                "post-disconnect snapshot still has AUTOMATIC and/or Dashboard ownership; no YES from transport alone",
                ev("transport", "operational_mode", "operational_mode_source", "control_authority"),
                False,
            )
        if transport == "disconnected" and not mode and not source:
            return ProbeResult(
                "facet_values",
                probe,
                "UNKNOWN",
                "transport disconnected but mode/ownership facets absent",
                ev("transport"),
                False,
            )
        return ProbeResult("facet_values", probe, "UNKNOWN", "insufficient facets for release", [], False)

    if probe == "human_has_control":
        if authority.lower() == "dashboard" or source.lower() == "dashboard":
            return ProbeResult(
                "facet_values",
                probe,
                "NO",
                "authority/mode source still Dashboard; transport does not prove human control",
                ev("control_authority", "operational_mode_source", "transport"),
                False,
            )
        if mode.upper() == "AUTOMATIC":
            return ProbeResult(
                "facet_values",
                probe,
                "NO",
                "operational_mode still AUTOMATIC; PolyScope operability not in facets",
                ev("operational_mode", "transport"),
                False,
            )
        return ProbeResult(
            "facet_values",
            probe,
            "UNKNOWN",
            "cannot assert human control from remaining facets",
            ev("transport", "operational_mode"),
            False,
        )

    if probe == "mode_after_disconnect":
        if mode.upper() == "AUTOMATIC":
            return ProbeResult(
                "facet_values",
                probe,
                "NO",
                "stored operational_mode is still AUTOMATIC — do not conclude NONE",
                ev("operational_mode", "transport"),
                False,
            )
        if not mode:
            return ProbeResult("facet_values", probe, "UNKNOWN", "operational_mode facet missing", ev("transport"), False)
        return ProbeResult("facet_values", probe, "UNKNOWN", f"mode={mode}", ev("operational_mode"), False)

    if probe == "clear_implies_full_human_ready":
        return ProbeResult(
            "facet_values",
            probe,
            "UNKNOWN",
            "facet snapshot has no clear-command result; power/safety/program/UI not shown as normalized",
            ev("power_state", "program_state", "safety_state"),
            False,
        )

    if probe == "no_error_means_executed":
        if program.upper() in {"STOPPED", "UNKNOWN", ""}:
            return ProbeResult(
                "facet_values",
                probe,
                "NO" if program.upper() == "STOPPED" else "UNKNOWN",
                "program_state does not show PLAYING; absence of error string is not a facet here",
                ev("program_state"),
                False,
            )
        if program.upper() == "PLAYING":
            return ProbeResult("facet_values", probe, "UNKNOWN", "PLAYING stored but not proof of motion observation", ev("program_state"), False)
        return ProbeResult("facet_values", probe, "UNKNOWN", "no execution observation facet", [], False)

    if probe == "vendors_same_implementation":
        return ProbeResult(
            "facet_values",
            probe,
            "UNKNOWN",
            "facet map has no UR implementation identity for FANUC/KUKA/Yaskawa features",
            [],
            False,
        )

    if probe == "cycle_controller_exists_ur":
        if cycle.upper() == "UNKNOWN" or cycle == "":
            return ProbeResult(
                "facet_values",
                probe,
                "UNKNOWN",
                "cycle_controller is UNKNOWN or absent; do not infer from other vendors",
                ev("cycle_controller"),
                False,
            )
        return ProbeResult("facet_values", probe, "YES", f"cycle_controller={cycle}", ev("cycle_controller"), False)

    if probe == "v517_applies_to_v515":
        ver = f.get("ursim_version", "")
        if ver.startswith("5.15"):
            return ProbeResult(
                "facet_values",
                probe,
                "UNKNOWN",
                "ursim_version is 5.15.2 but 5.17 applicability is not a facet value — no YES",
                ev("ursim_version"),
                False,
            )
        return ProbeResult("facet_values", probe, "UNKNOWN", "version facet missing", [], False)

    if probe == "no_tcp_means_not_remote":
        if remote == "false":
            return ProbeResult("facet_values", probe, "UNKNOWN", "remote_control false is stored independently of TCP; TCP absence is not Remote definition", ev("remote_control", "transport"), False)
        if transport == "disconnected" and not remote:
            return ProbeResult("facet_values", probe, "UNKNOWN", "disconnected TCP does not encode Remote vs Local", ev("transport"), False)
        return ProbeResult("facet_values", probe, "UNKNOWN", "cannot equate TCP with Remote", [], False)

    if probe == "not_remote_means_human_owns":
        if remote == "false" and (authority.lower() == "dashboard" or source.lower() == "dashboard"):
            return ProbeResult(
                "facet_values",
                probe,
                "NO",
                "not Remote and Dashboard still owns operational mode can co-exist (J-1 shape)",
                ev("remote_control", "control_authority", "operational_mode_source"),
                False,
            )
        if remote == "false":
            return ProbeResult("facet_values", probe, "UNKNOWN", "not Remote does not prove human ownership", ev("remote_control"), False)
        return ProbeResult("facet_values", probe, "UNKNOWN", "remote_control facet missing", [], False)

    if probe == "simulation_skips_state_check":
        return ProbeResult("facet_values", probe, "NO", "no facet says simulation implies safe or skips checks", ev("safety_state"), False)

    if probe == "validator_pass_means_ursim_pass":
        return ProbeResult("facet_values", probe, "NO", "validator and URSim are not a stored identity", [], False)

    if probe == "program_stop_releases_ownership":
        if program.upper() == "STOPPED" and (source.lower() == "dashboard" or mode.upper() == "AUTOMATIC"):
            return ProbeResult(
                "facet_values",
                probe,
                "NO",
                "program STOPPED coexists with Dashboard AUTOMATIC in the snapshot",
                ev("program_state", "operational_mode", "operational_mode_source"),
                False,
            )
        return ProbeResult("facet_values", probe, "UNKNOWN", "stop vs ownership relationship not in facets", ev("program_state"), False)

    return ProbeResult("facet_values", probe, "UNKNOWN", f"unmapped probe {probe}", [], False)


def probe_unsafe_transport_proxy(probe: str, facets: dict[str, str]) -> ProbeResult:
    """Documents the failure mode: treat TCP disconnect as human handoff. Not a product policy."""
    transport = str(facets.get("transport") or "").lower()
    if transport == "disconnected" and probe in {
        "disconnect_clears_mode",
        "human_has_control",
        "not_remote_means_human_owns",
    }:
        return ProbeResult(
            "unsafe_transport_proxy",
            probe,
            "YES",
            "proxy: disconnected TCP ⇒ human control / mode released",
            [f"transport={facets.get('transport')}"],
            True,
        )
    return probe_facet_values(probe, facets)


def probe_typed_record(probe: str, record: ResearchRecord) -> ProbeResult:
    """Uses official ResearchRecord fields including conflict/unknown/api prose."""
    facets = _facet_map(record, None)
    base = probe_facet_values(probe, facets)
    blob = _blob(record)
    evidence = list(base.evidence_used)

    if probe in {"disconnect_clears_mode", "human_has_control", "mode_after_disconnect"}:
        if _has(blob, "tcp") and ("does not clear" in blob or "does not automatically clear" in blob or "survives tcp" in blob):
            evidence.append("conflicts/api_observations: TCP disconnect does not clear operational mode")
            return ProbeResult(
                "typed_record",
                probe,
                "NO",
                "typed conflicts/api notes state AUTOMATIC remains after TCP close (J-1)",
                evidence,
                False,
            )

    if probe == "clear_implies_full_human_ready":
        if "clear operational mode" in blob:
            evidence.append("api_observations: clear → NONE")
            if any(u for u in record.unknowns if "polyscope" in u.lower() or "safety" in u.lower()):
                evidence.append("unknowns retain other facets")
            return ProbeResult(
                "typed_record",
                probe,
                "CONDITIONAL",
                "clear operational mode is evidence for mode-source release only; unknowns remain for UI/safety/power/program",
                evidence,
                False,
            )
        return ProbeResult("typed_record", probe, "UNKNOWN", "no clear-command evidence on typed record", evidence, False)

    if probe == "no_error_means_executed":
        if "not program execution" in blob or "accepted is not" in blob:
            evidence.append("conflict accept-vs-execute")
            return ProbeResult("typed_record", probe, "NO", "conflict: command accepted ≠ executed", evidence, False)
        return ProbeResult("typed_record", probe, base.verdict, base.rationale, evidence, False)

    if probe == "vendors_same_implementation":
        if "not the same" in blob or "splits automatic" in blob or "vendor-not-identical" in blob:
            evidence.append("conflict vendor mapping")
            return ProbeResult("typed_record", probe, "NO", "common concept ≠ identical UR implementation", evidence, False)
        return ProbeResult("typed_record", probe, "UNKNOWN", "no vendor-identity conflict text", evidence, False)

    if probe == "cycle_controller_exists_ur":
        if any("cycle" in u.lower() for u in record.unknowns) or facets.get("cycle_controller", "").upper() == "UNKNOWN":
            evidence.append("unknowns or cycle_controller=UNKNOWN")
            return ProbeResult("typed_record", probe, "UNKNOWN", "UR cycle controller listed unknown; other vendors not used as proof", evidence, False)
        return ProbeResult("typed_record", probe, "UNKNOWN", "no cycle existence claim", evidence, False)

    if probe == "v517_applies_to_v515":
        if any(
            "5.17" in json.dumps(vf) and "does_not_apply" in json.dumps(vf)
            for vf in record.version_facts
        ) or "5.17" in blob and "5.15.2" in blob and "not" in blob:
            evidence.append("version_facts.does_not_apply or conflict ISO/version")
            return ProbeResult("typed_record", probe, "NO", "5.17 restrictions recorded as not applying to 5.15.2", evidence, False)
        return ProbeResult("typed_record", probe, "UNKNOWN", "no version isolation text on typed record", evidence, False)

    if probe == "simulation_skips_state_check":
        return ProbeResult("typed_record", probe, "NO", "no evidence that simulation skips state checks", evidence, False)

    if probe == "validator_pass_means_ursim_pass":
        return ProbeResult("typed_record", probe, "NO", "no evidence equating Validator PASS with URSim PASS", evidence, False)

    if probe == "program_stop_releases_ownership":
        if "survives tcp" in blob or "does not clear" in blob:
            evidence.append("mode lock independent of program stop/tcp")
            return ProbeResult("typed_record", probe, "NO", "ownership is operational mode source, not program_state STOPPED", evidence, False)
        return ProbeResult("typed_record", probe, base.verdict, base.rationale, evidence, False)

    if probe == "no_tcp_means_not_remote":
        if "is in remote control" in blob and "false" in blob and "survives tcp" in blob:
            return ProbeResult("typed_record", probe, "UNKNOWN", "Remote is a distinct facet from TCP; J-1 had remote false while TCP already closed per command", evidence, False)
        return ProbeResult("typed_record", probe, "UNKNOWN", "TCP ≠ Remote encoding", evidence, False)

    if probe == "not_remote_means_human_owns":
        if "distinct from operational mode" in blob or "is in remote control" in blob:
            evidence.append("api note: remote false distinct from mode lock")
            return ProbeResult("typed_record", probe, "NO", "J-1: remote false while Dashboard owned AUTOMATIC", evidence, False)
        return ProbeResult("typed_record", probe, base.verdict, base.rationale, evidence, False)

    if probe == "transport_disconnected":
        return ProbeResult("typed_record", probe, base.verdict, base.rationale, evidence, False)

    return ProbeResult("typed_record", probe, base.verdict, f"typed fallback: {base.rationale}", evidence, False)


def _matches_expected(got: Verdict, expected: str, also_accept: list[str] | None) -> bool:
    allowed = {expected, *(also_accept or [])}
    return got in allowed


def score_case(item: dict[str, Any], result: ProbeResult) -> dict[str, Any]:
    ok = _matches_expected(result.verdict, str(item["expected"]), list(item.get("also_accept") or []))
    return {
        "id": item["id"],
        "kind": item["kind"],
        "question": item["question"],
        "expected": item["expected"],
        "also_accept": item.get("also_accept") or [],
        "got": result.verdict,
        "pass": ok,
        "policy": result.policy,
        "rationale": result.rationale,
        "evidence_used": result.evidence_used,
        "false_inference": result.false_inference,
        "evidence_aware": bool(result.evidence_used) and not result.false_inference,
    }


def seed_phase_j_idea_catalog() -> IdeaCatalog:
    catalog = IdeaCatalog()
    catalog.add(
        PreservedIdea(
            idea="HUMAN_CONTROL_OWNERSHIP",
            why_it_appeared="J-1 Dashboard operational mode lock",
            higher_level_goal="Human Review must not overlap Agent controller ownership",
            why_not_implemented="Recorded as spec; no new Core",
            existing_alternative="Dashboard clear operational mode + ResearchRecord conflicts",
            potential_future_trigger="TCP disconnect human PolyScope handoff",
            decision="RECORD",
        )
    )
    catalog.add(
        PreservedIdea(
            idea="Ownership Release",
            why_it_appeared="Process stop did not restore PolyScope",
            higher_level_goal="Explicit controller state release after Agent session",
            why_not_implemented="Official command exists; not wired as workflow",
            existing_alternative="clear operational mode",
            potential_future_trigger="disconnect Dashboard then human resume",
            decision="DEFER",
        )
    )
    catalog.add(
        PreservedIdea(
            idea="Controller Ownership Guard",
            why_it_appeared="Agent may start while human holds pendant",
            higher_level_goal="Check control authority before Agent motion",
            why_not_implemented="Queryable via existing Dashboard manager",
            existing_alternative="get operational mode / is in remote control",
            potential_future_trigger="Agent operates URSim",
            decision="DEFER",
        )
    )
    return catalog


def run_k7_consumers(store: ResearchStore) -> dict[str, Any]:
    """Existing TDA consumers only — no robot-specific reasoner."""
    out: dict[str, Any] = {}
    for label, req in (("ja", K7_REQUIREMENT_JA), ("en", K7_REQUIREMENT_EN)):
        gate = assess_research_requirement(req)
        goals = abstract_goals(req)
        discovery = discover_capabilities(req)
        facets = extract_requirement_facets(req)
        reuse = assess_reuse(facets, store)
        material = reuse_conversation_material(reuse, store)
        catalog = seed_phase_j_idea_catalog()
        re_eval = catalog.re_evaluate_for_requirement(req)
        workflow = run_standard_workflow(req, store=store, idea_catalog=seed_phase_j_idea_catalog(), llm_enabled=False)
        reeval_blob = json.dumps([i.to_dict() for i in re_eval], ensure_ascii=False).lower()
        mentions_clear = "clear operational mode" in material.lower() or "clear operational mode" in reeval_blob
        discovery_blob = json.dumps(discovery.to_dict(), ensure_ascii=False).lower()
        mentions_handoff = any(
            tok in material.lower() + discovery_blob + reeval_blob
            for tok in ("handoff", "ownership", "control authority", "操作権")
        )
        derived_names = [d.name for d in discovery.derived_capabilities]
        out[label] = {
            "requirement": req,
            "gate": gate.to_dict(),
            "requirement_facets": facets.to_dict(),
            "goals": goals.to_dict(),
            "derived_capabilities": [d.to_dict() for d in discovery.derived_capabilities],
            "derived_names": derived_names,
            "reuse": reuse.to_dict(),
            "llm_material": material,
            "idea_reeval": [i.to_dict() for i in re_eval],
            "idea_reeval_names": [i.idea for i in re_eval],
            "workflow_stop": workflow.stop_reason,
            "workflow_early_exit": workflow.early_exit_at,
            "mentions_clear_operational_mode": mentions_clear,
            "mentions_clear_in_reuse_material": "clear operational mode" in material.lower(),
            "mentions_handoff_or_authority": mentions_handoff,
            "proposes_disconnect_as_sufficient": (
                reuse.mode == "no_reuse"
                and not mentions_clear
                and "Mechanical API Validator" in derived_names
            ),
        }
    # Decision factors on UR candidate from store
    rec = store.records[0] if store.records else None
    if rec and rec.technology_candidates:
        c0 = dict(rec.technology_candidates[0])
        c0.setdefault("candidate_id", "UR-DASH")
        out["decision_factors"] = [f.to_dict() for f in compute_decision_factors(c0)]
        out["decision_comparison"] = compare_candidates_for_decision(rec.technology_candidates)
    return out


def run_k8_observation(k7: dict[str, Any]) -> dict[str, Any]:
    """Observe capability names that appeared — do not implement."""
    observed: list[str] = []
    for label in ("ja", "en"):
        block = k7.get(label) or {}
        observed.extend(block.get("derived_names") or [])
        observed.extend(block.get("idea_reeval_names") or [])
    unique = list(dict.fromkeys(observed))
    catalog_hits = {
        "Controller Ownership Guard": any("ownership" in x.lower() or "guard" in x.lower() for x in unique),
        "Ownership Release": any("release" in x.lower() or "clear operational" in x.lower() for x in unique),
        "Human Handoff": any("handoff" in x.lower() for x in unique),
        "State Snapshot": any("snapshot" in x.lower() for x in unique),
        "Cycle Abstraction": any("cycle" in x.lower() for x in unique),
        "API Existence Observation": "API Existence Observation" in unique,
        "Research Reuse": "Research Reuse" in unique,
        "Mechanical API Validator": "Mechanical API Validator" in unique,
    }
    return {
        "names_seen": unique,
        "phase_j_candidates_surfaced": catalog_hits,
        "decisions": [
            {
                "idea": "Controller Ownership Guard",
                "observation": catalog_hits["Controller Ownership Guard"],
                "decision": "DEFER",
                "reason": "Existing Dashboard queries suffice; not implemented this phase",
            },
            {
                "idea": "Ownership Release",
                "observation": catalog_hits["Ownership Release"] or bool((k7.get("en") or {}).get("mentions_clear_operational_mode")),
                "decision": "DEFER",
                "reason": "Official clear operational mode already recorded",
            },
            {
                "idea": "Human Handoff",
                "observation": catalog_hits["Human Handoff"] or bool((k7.get("en") or {}).get("mentions_handoff_or_authority")),
                "decision": "DEFER",
                "reason": "Workflow, not a Core",
            },
            {
                "idea": "API Existence Observation",
                "observation": catalog_hits["API Existence Observation"],
                "decision": "REUSE",
                "reason": "Existing goal_abstraction UR pattern",
            },
            {
                "idea": "Mechanical API Validator as Core",
                "observation": catalog_hits["Mechanical API Validator"],
                "decision": "REJECT",
                "reason": "Existing discovery already REJECT",
            },
            {
                "idea": "Cross-Facet Reasoning Core",
                "observation": False,
                "decision": "DEFER",
                "reason": "See core_creation_gate; not created this phase",
            },
        ],
    }


def _kind_accuracy(rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    subset = [r for r in rows if r["kind"] == kind]
    if not subset:
        return {"kind": kind, "n": 0, "passed": 0, "rate": None}
    passed = sum(1 for r in subset if r["pass"])
    return {"kind": kind, "n": len(subset), "passed": passed, "rate": passed / len(subset)}


def run_phase_k() -> dict[str, Any]:
    audit = existing_capability_audit()
    questions = question_catalog()

    facet_payload = facet_only_record_payload()
    rel_payload = relationship_record_payload()
    unknown_payload = unknown_cycle_record_payload()
    version_payload = version_mix_record_payload()

    facet_record = research_record_from_payload(facet_payload)
    rel_record = research_record_from_payload(rel_payload)
    unknown_record = research_record_from_payload(unknown_payload)
    version_record = research_record_from_payload(version_payload)

    rel_dropped = dropped_keys(rel_payload)

    def record_for(item: dict[str, Any], relationship: bool) -> ResearchRecord:
        if item["id"] == "K4-1":
            return unknown_record
        if item["id"] in {"K5-1", "K9-7"}:
            return version_record
        return rel_record if relationship else facet_record

    def facets_for(item: dict[str, Any]) -> dict[str, str]:
        if item["id"] == "K4-1":
            return dict(unknown_record.environment_facts)
        if item["id"] in {"K5-1", "K9-7"}:
            return dict(version_record.environment_facts)
        return dict(FACET_ONLY_POST_DISCONNECT)

    rows_facet: list[dict[str, Any]] = []
    rows_typed_on_facet_record: list[dict[str, Any]] = []
    rows_typed_on_rel_record: list[dict[str, Any]] = []
    rows_unsafe: list[dict[str, Any]] = []

    for item in questions:
        if item["id"] == "K6":
            continue
        pr_f = probe_facet_values(item["probe"], facets_for(item))
        rows_facet.append(score_case(item, pr_f))
        pr_t_a = probe_typed_record(item["probe"], record_for(item, False))
        rows_typed_on_facet_record.append(score_case(item, pr_t_a))
        pr_t_b = probe_typed_record(item["probe"], record_for(item, True))
        rows_typed_on_rel_record.append(score_case(item, pr_t_b))
        rows_unsafe.append(score_case(item, probe_unsafe_transport_proxy(item["probe"], facets_for(item))))

    k6_item = next(x for x in questions if x["id"] == "K6")
    k6_a = score_case(k6_item, probe_facet_values(k6_item["probe"], dict(FACET_ONLY_POST_DISCONNECT)))
    k6_b_facet = score_case(k6_item, probe_facet_values(k6_item["probe"], dict(FACET_ONLY_POST_DISCONNECT)))
    k6_b_typed = score_case(k6_item, probe_typed_record(k6_item["probe"], rel_record))
    k6_a_typed = score_case(k6_item, probe_typed_record(k6_item["probe"], facet_record))

    # ResearchStore reuse against Phase J-shaped relationship record
    store = ResearchStore()
    store.add(rel_record)
    k7 = run_k7_consumers(store)
    k8 = run_k8_observation(k7)

    state = ResearchState(requirement=rel_record.requirement)
    state.merge_run(
        {
            "queries": rel_record.queries,
            "candidates": rel_record.technology_candidates,
            "proposal": {"unknown": rel_record.unknowns, "conflicts": rel_record.conflicts},
        }
    )

    all_typed_b = rows_typed_on_rel_record + [k6_b_typed]
    all_facet = rows_facet + [k6_a]
    false_inf_unsafe = sum(1 for r in rows_unsafe if r["false_inference"])
    false_inf_facet = sum(1 for r in all_facet if r["false_inference"] or (not r["pass"] and r["got"] == "YES"))
    false_inf_typed = sum(1 for r in all_typed_b if r["false_inference"] or (not r["pass"] and r["got"] == "YES"))

    metrics = {
        "facet_accuracy": _kind_accuracy(all_facet, "facet"),
        "cross_facet_accuracy_facet_policy": _kind_accuracy(all_facet, "cross_facet"),
        "cross_facet_accuracy_typed_relationship": _kind_accuracy(all_typed_b, "cross_facet"),
        "unknown_preservation_facet": _kind_accuracy(all_facet, "unknown"),
        "unknown_preservation_typed": _kind_accuracy(all_typed_b, "unknown"),
        "version_isolation_facet": _kind_accuracy(all_facet, "version"),
        "version_isolation_typed": _kind_accuracy(all_typed_b, "version"),
        "false_reasoning_facet": _kind_accuracy(all_facet, "false_reasoning"),
        "false_reasoning_typed": _kind_accuracy(all_typed_b, "false_reasoning"),
        "false_inference_count": {
            "unsafe_transport_proxy": false_inf_unsafe,
            "facet_values": false_inf_facet,
            "typed_relationship": false_inf_typed,
        },
        "evidence_awareness_typed_relationship": {
            "n": len(all_typed_b),
            "passed": sum(1 for r in all_typed_b if r["evidence_aware"]),
            "rate": sum(1 for r in all_typed_b if r["evidence_aware"]) / len(all_typed_b) if all_typed_b else None,
        },
        "k6": {
            "facet_only_policy_on_A": k6_a,
            "typed_policy_on_A_no_conflicts": k6_a_typed,
            "facet_only_policy_on_B_values": k6_b_facet,
            "typed_policy_on_B_with_conflicts": k6_b_typed,
            "verdict_changed_A_to_B_typed": k6_a_typed["got"] != k6_b_typed["got"]
            or k6_a_typed["rationale"] != k6_b_typed["rationale"],
        },
    }

    reach = {
        "can_store": True,
        "can_search_typed_fields": bool(rel_record.conflicts) or bool(rel_record.environment_facts),
        "can_reuse_for_k7_ja": k7["ja"]["reuse"]["mode"],
        "can_reuse_for_k7_en": k7["en"]["reuse"]["mode"],
        "can_refer_multiple_environment_facts": len(rel_record.environment_facts) > 1,
        "understands_relationships_as_first_class": False,
        "understands_relationships_as_conflict_prose": bool(rel_record.conflicts),
        "preserves_unknowns_list": bool(unknown_record.unknowns),
        "version_boundary_in_version_facts_dict": any("does_not_apply" in json.dumps(vf) for vf in version_record.version_facts),
        "version_boundary_in_VersionFact_dataclass": False,
        "decision_reflects_authority": k7["en"]["mentions_clear_operational_mode"] or k7["en"]["mentions_handoff_or_authority"],
        "discovers_new_higher_concepts_beyond_ur_pattern": k8["phase_j_candidates_surfaced"]["Human Handoff"]
        or k8["phase_j_candidates_surfaced"]["Controller Ownership Guard"],
    }

    core_gate = {
        "ResearchRecord_plus_conflicts": "REUSE",
        "facet_records_extension": "REUSE",
        "RequirementFacets_robot_keys": "DEFER",
        "reuse_conversation_material_robot_fields": "DEFER",
        "CrossFacetReasoningCore": "DEFER",
        "RelationshipGraphCore": "REJECT",
        "MatrixMemoryCore": "REJECT",
        "rationale": (
            "Facet conjunction of remaining AUTOMATIC/Dashboard already answers the center case NO "
            "without a graph. Conflict prose makes the same NO evidence-aware. K-7 consumers do not "
            "surface clear operational mode. That is a consumption gap, not a measured need for a new C3."
        ),
    }

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "audit": audit,
        "relationship_extra_keys_dropped_by_dataclass": rel_dropped,
        "relationship_transitions_not_on_typed": RELATIONSHIP_TRANSITIONS,
        "research_state_unknowns": state.known_unknowns,
        "results": {
            "facet_values": rows_facet,
            "typed_on_facet_only_record": rows_typed_on_facet_record,
            "typed_on_relationship_record": rows_typed_on_rel_record,
            "unsafe_transport_proxy": rows_unsafe,
        },
        "k6": metrics["k6"],
        "k7_existing_consumers": k7,
        "k8_idea_discovery": k8,
        "metrics": metrics,
        "reach": reach,
        "core_creation_gate": core_gate,
        "center_case": {
            "claim": "TCP disconnect = human regained control",
            "unsafe_proxy": next(r for r in rows_unsafe if r["id"] == "K2-B"),
            "facet_values": next(r for r in rows_facet if r["id"] == "K2-B"),
            "typed_without_conflicts": next(r for r in rows_typed_on_facet_record if r["id"] == "K2-B"),
            "typed_with_conflicts": next(r for r in rows_typed_on_rel_record if r["id"] == "K2-B"),
        },
    }
