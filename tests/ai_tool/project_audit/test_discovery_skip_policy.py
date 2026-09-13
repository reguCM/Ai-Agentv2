"""Phase N+1b — Facet Discovery skip policy (no new Core)."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.discovery_skip_policy import (
    classify_discovery,
    environment_switch,
)
from ai_tool.experimental.development_assistance.facet_discovery import (
    asserts_not_a_decision,
    discover_facets,
)
from ai_tool.experimental.development_assistance.phase_n1b_discovery_skip_policy_harness import (
    _store,
    run_phase_n1b,
)
from ai_tool.experimental.development_assistance.research_record import ResearchStore


def test_s1_s2_skip_under_c_and_d():
    store = _store()
    for req in (
        "JSONとは何ですか？",
        "Pythonのfor文を教えて",
        "PythonでCSVを読み込むコードを書いて",
        "PythonでJSONを読むコードを書いて",
    ):
        for policy in ("C", "D"):
            d = classify_discovery(req, policy=policy, store=store)
            assert d.invoked is False, req
            assert d.mode == "DISCOVERY_SKIP"


def test_research_required_invokes():
    store = _store()
    for req in (
        "Aの最新Versionで使えるAPIを調べて",
        "AをWindows + RTX 3060 + Python 3.12で動かせるか調べて",
        "AとBのどちらを今の環境で使うべきか比較して",
        "Aを自作Toolに組み込みたい。ライセンス上の注意点を調べて",
        "AをPython 3.12で動かせるか調べて",
    ):
        d = classify_discovery(req, policy="D", store=store)
        assert d.invoked is True, req
        assert d.mode == "DISCOVERY_REQUIRED"


def test_policy_a_false_start_on_json_does_not_flood():
    store = _store()
    req = "PythonでJSONを読むコードを書いて"
    d = classify_discovery(req, policy="A", store=store)
    assert d.invoked is True
    disc = discover_facets(req, store)
    ids = disc.catalog_ids()
    assert "license" not in ids
    assert "cuda" not in ids
    assert "docker" not in ids
    assert asserts_not_a_decision(disc)


def test_unknown_domain_does_not_invent_oss_facets():
    store = ResearchStore()
    req = "FooBarという特殊な装置をTool化したい"
    d = classify_discovery(req, policy="D", store=store)
    assert d.mode == "DISCOVERY_OPTIONAL"
    assert d.unknown_domain is True
    disc = discover_facets(req, store)
    ids = set(disc.catalog_ids())
    assert not ids & {"python_version", "cuda", "docker", "license"}


def test_ambiguous_clarification_not_skip_not_guess():
    store = _store()
    d = classify_discovery("その環境ならどう？", policy="D", store=store)
    assert d.mode == "DISCOVERY_OPTIONAL"
    assert d.clarification_required is True


def test_docker_not_applied_to_virtualbox():
    sw = environment_switch("docker", "VirtualBoxなら？")
    assert sw["do_not_apply_prior_env"] is True
    assert "docker" in sw["drop_facets"]
    assert "gpu_passthrough" in sw["drop_facets"]


def test_phase_n1b_offline_no_new_core():
    result = run_phase_n1b()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_changed"] is False
    assert result["core_creation_gate"]["Cross_Facet_Reasoning"] == "REJECT"
    assert result["core_creation_gate"]["RAG_Vector_DB"] == "REJECT"
    assert result["adoption"]["decision"] in {
        "ADOPT_CONDITIONAL",
        "EXPERIMENTAL_RETAIN",
        "MANUAL_ONLY",
        "REJECT",
    }
    d = result["policies"]["D"]
    assert d["false_discovery_count"] == 0
    assert d["missed_discovery_count"] == 0
    assert d["unnecessary_invocation_count"] == 0
    assert result["policies"]["A"]["unnecessary_invocation_count"] > 0
    assert result["policies"]["B"]["missed_discovery_count"] + result["policies"]["B"]["missed_clarification_count"] > 0
    assert result["version_unknown_conflict"]["version_isolation"] is True
    assert result["version_unknown_conflict"]["python_313_unknown"] is True
    assert result["version_unknown_conflict"]["did_not_infer_from_cuda"] is True
    assert result["version_unknown_conflict"]["conflict_preserved"] is True
    assert result["env_switch"]["misapplied"] is False
    assert result["python_condition_change"]["only_python_changed"] is True
    assert result["followup_chain"]["continuity"] is True
    assert result["followup_chain"]["all_invoked"] is True
    assert result["ambiguous_handling"]["no_guess_on_unresolved"] is True
