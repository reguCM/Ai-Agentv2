"""Phase K — Cross-Facet Reasoning Evaluation (offline, no new Core)."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.phase_k_cross_facet_fixtures import (
    FACET_ONLY_POST_DISCONNECT,
    facet_only_record_payload,
    relationship_record_payload,
)
from ai_tool.experimental.development_assistance.phase_k_cross_facet_harness import (
    dropped_keys,
    load_phase_j_raw,
    probe_facet_values,
    probe_typed_record,
    probe_unsafe_transport_proxy,
    research_record_from_payload,
    run_phase_k,
)


def test_facet_records_kept_by_official_dataclass():
    raw = load_phase_j_raw()
    assert "facet_records" in raw
    assert "facet_records" not in dropped_keys(raw)
    typed = research_record_from_payload(raw)
    assert "facet_records" in typed.to_dict()
    assert typed.conflicts


def test_k2_a_facet_memory_yes():
    r = probe_facet_values("transport_disconnected", dict(FACET_ONLY_POST_DISCONNECT))
    assert r.verdict == "YES"


def test_k2_b_facet_conjunction_not_yes():
    r = probe_facet_values("disconnect_clears_mode", dict(FACET_ONLY_POST_DISCONNECT))
    assert r.verdict == "NO"
    assert r.false_inference is False


def test_unsafe_proxy_false_inference_on_center_case():
    r = probe_unsafe_transport_proxy("disconnect_clears_mode", dict(FACET_ONLY_POST_DISCONNECT))
    assert r.verdict == "YES"
    assert r.false_inference is True


def test_k4_unknown_not_inferred_from_other_vendors():
    rec = research_record_from_payload(
        {
            **facet_only_record_payload(),
            "environment_facts": {
                "control_authority": "Dashboard",
                "transport": "disconnected",
                "cycle_controller": "UNKNOWN",
            },
            "unknowns": ["Whether UR 5.15.2 exposes a first-class counted controller cycle"],
            "conflicts": [],
            "api_observations": [],
        }
    )
    r = probe_typed_record("cycle_controller_exists_ur", rec)
    assert r.verdict == "UNKNOWN"


def test_k6_relationship_prose_makes_no_evidence_aware():
    a = research_record_from_payload(facet_only_record_payload())
    b = research_record_from_payload(relationship_record_payload())
    ra = probe_typed_record("human_has_control", a)
    rb = probe_typed_record("human_has_control", b)
    assert ra.verdict in {"NO", "UNKNOWN"}
    assert rb.verdict == "NO"
    assert any("conflict" in e.lower() or "tcp disconnect" in e.lower() for e in rb.evidence_used)
    assert not any("tcp disconnect does not clear" in e.lower() for e in ra.evidence_used)


def test_phase_k_offline_no_new_core():
    result = run_phase_k()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["core_creation_gate"]["CrossFacetReasoningCore"] in {"DEFER", "REJECT", "RECORD"}
    assert result["center_case"]["unsafe_proxy"]["got"] == "YES"
    assert result["center_case"]["facet_values"]["got"] == "NO"
    assert result["k7_existing_consumers"]["ja"]["reuse"]["mode"] == "no_reuse"
    assert result["k7_existing_consumers"]["en"]["mentions_clear_operational_mode"] is False
