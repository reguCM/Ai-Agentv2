"""開発 Policy の機械判定。LLM にお願いしただけでは COMPLETE にならない。"""
from __future__ import annotations

import json

from ai_tool.policy.evaluate import evaluate_development_work
from ai_tool.policy.enforce import apply_final_answer_policy, claims_specification_complete
from ai_tool.policy.loader import load_development_policy, policy_prompt_block


def test_policy_loads():
    data = load_development_policy()
    assert data["policy_id"] == "ai-agent-development-policy"
    assert "CONNECTED" in data["item_statuses"]
    assert data["version"] == "1.5"
    assert data["distribution"]["policy_version"] == "2026-09-06.1"
    assert set(data["distribution"]["consumers"]) == {
        "codex", "cursor", "local_agent",
    }
    assert data["spec_proposal_observation"]["learning_method"] == "NOT_DETERMINED"
    assert data["spec_proposal_observation"]["do_not_auto_judge_llm_correctness"] is True
    assert data["spec_proposal_observation"]["human_revision_is_not_automatically_correct"] is True
    assert data["spec_proposal_observation"]["audit_reports_are_reference_only"] is True
    assert data["spec_proposal_observation"]["problem_occurrence_is_not_llm_failure"] is True
    assert data["spec_proposal_observation"]["do_not_infer_parent_proposal_id_from_chat"] is True
    assert data["spec_proposal_observation"]["dual_id_issuance_is_not_automatically_a_bug"] is True
    assert data["completion"]["connected_requires_generate_to_next_stage"] is True
    boundary = data["definition_boundary"]
    assert boundary["clear_definition_may_proceed"] is True
    assert boundary["minor_ambiguity_may_proceed_as_provisional"] is True
    assert boundary["provisional_is_not_final_specification"] is True
    assert boundary["boundary_ambiguity_requires_human"] is True
    assert boundary["expansion_sign_alone_is_not_stop"] is True
    assert boundary["do_not_doubt_code_confirmed_facts"] is True
    assert "definition_boundary_ambiguous" in data["human_decision_required_when"]
    assert "new_id_versus_existing_id_undecidable" in data["human_decision_required_when"]
    block = policy_prompt_block()
    block_data = json.loads(block)
    assert "NOT_DETERMINED" in block
    assert "not automatic truth" in block
    assert "parent_proposal_id" in block
    assert "definition_boundary" in block
    assert "expansion signs alone are not a stop" in block
    concepts = data["concept_definition"]
    assert concepts["path"] == "docs/concepts/CONCEPT_DEFINITIONS.md"
    assert concepts["project_origin"] == "PROJECT_SPEC.md"
    assert concepts["origin_must_not_be_rewritten"] is True
    assert concepts["current_is_not_automatically_truer_than_origin"] is True
    assert concepts["origin_is_not_automatically_truer_than_current"] is True
    assert concepts["revert_toward_origin_is_allowed"] is True
    assert concepts["revert_toward_origin_is_not_automatically_regression"] is True
    assert concepts["current_code_drift_requires_human"] is True
    assert "origin_versus_current_choice" in data["human_decision_required_when"]
    assert "current_code_drift" in data["human_decision_required_when"]
    assert "revert_current_toward_origin" in data["human_decision_required_when"]
    assert "concept_definition" in block
    assert "Revert toward Origin is allowed" in block
    assert block_data["policy_distribution"]["loaded"] is True
    assert block_data["policy_distribution"]["canonical_hash"].startswith("sha256:")


def test_empty_checklist_cannot_complete():
    out = evaluate_development_work(items=[], tests_passed=True, claim_specification_complete=True, save=False)
    assert out["test_status"] == "PASS"
    assert out["specification_status"] != "COMPLETE"
    assert out["may_claim_specification_complete"] is False
    assert out["blocked_complete_claim"] is True
    assert out["tests_passed_implies_specification_complete"] is False


def test_partial_item_blocks_complete_even_if_tests_pass():
    out = evaluate_development_work(
        items=[{"id": "search", "status": "CONNECTED"}, {"id": "write", "status": "PARTIAL"}],
        tests_passed=True,
        claim_specification_complete=True,
        save=False,
    )
    assert out["test_status"] == "PASS"
    assert out["specification_status"] == "PARTIAL"
    assert out["may_claim_specification_complete"] is False
    assert any(row["id"] == "write" for row in out["decision"]["missing"])


def test_all_connected_is_complete_without_requiring_tests():
    out = evaluate_development_work(
        items=[{"id": "a", "status": "CONNECTED", "evidence": "call path"}],
        tests_passed=None,
        save=False,
    )
    assert out["specification_status"] == "COMPLETE"
    assert out["test_status"] == "NOT_OBSERVED"
    assert out["may_claim_specification_complete"] is True


def test_need_human_blocks_implementation():
    out = evaluate_development_work(
        items=[{"id": "api", "status": "NEED_HUMAN_DECISION", "reason": "互換性"}],
        save=False,
    )
    assert out["decision"]["human_decision_required"] is True
    assert out["may_proceed_implementation"] is False
    assert out["specification_status"] == "NEED_HUMAN_DECISION"


def test_provisional_without_note_requires_human():
    out = evaluate_development_work(
        items=[{"id": "x", "status": "CONNECTED", "provisional": True}],
        save=False,
    )
    assert out["may_proceed_implementation"] is False
    assert out["specification_status"] == "NEED_HUMAN_DECISION"


def test_provisional_with_note_is_not_complete():
    out = evaluate_development_work(
        items=[
            {
                "id": "x",
                "status": "CONNECTED",
                "provisional": True,
                "provisional_note": "仮: 検索省略TTLは未確定",
            }
        ],
        save=False,
    )
    assert out["may_proceed_implementation"] is True
    assert out["specification_status"] == "PARTIAL"
    assert out["may_claim_specification_complete"] is False


def test_not_connected_is_incomplete():
    out = evaluate_development_work(
        items=[{"id": "chat", "status": "NOT_CONNECTED"}],
        tests_passed=True,
        save=False,
    )
    assert out["specification_status"] == "INCOMPLETE"


def test_enforce_rewrites_false_complete_claim():
    out = apply_final_answer_policy("実装完了しました。すべて仕様完成です。")
    assert out["applied"] is True
    assert "may_claim_specification_complete=false" in (out["notice"] or "")
    assert out["evaluation"]["specification_status"] != "COMPLETE"
    assert "DEVELOPMENT_POLICY" in out["answer"]


def test_enforce_does_not_rewrite_ordinary_answer():
    text = "GPU 温度は Tool 結果の 62 です。"
    out = apply_final_answer_policy(text)
    assert out["applied"] is False
    assert out["answer"] == text
    assert claims_specification_complete(text) is False


def test_load_failure_forbids_complete(tmp_path):
    missing = tmp_path / "nope.json"
    out = evaluate_development_work(
        items=[{"id": "a", "status": "CONNECTED"}],
        policy_path=missing,
        save=False,
    )
    assert out["policy_loaded"] is False
    assert out["specification_status"] == "NOT_OBSERVED"
    assert out["may_claim_specification_complete"] is False


def test_definition_boundary_three_modes_do_not_change_complete_semantics():
    """明確は進行、仮仕様は進行だが未完成、境界は人間確認。膨張フラグ自体は COMPLETE を変えない。"""
    clear = evaluate_development_work(
        items=[{"id": "cid_pass", "status": "CONNECTED", "evidence": "run_chat_turn argument"}],
        save=False,
    )
    assert clear["may_proceed_implementation"] is True
    assert clear["specification_status"] == "COMPLETE"

    provisional = evaluate_development_work(
        items=[
            {
                "id": "ttl",
                "status": "CONNECTED",
                "provisional": True,
                "provisional_note": "仮: 省略TTLは未確定。最終仕様ではない。",
            }
        ],
        tests_passed=True,
        save=False,
    )
    assert provisional["may_proceed_implementation"] is True
    assert provisional["specification_status"] == "PARTIAL"
    assert provisional["may_claim_specification_complete"] is False
    assert provisional["tests_passed_implies_specification_complete"] is False

    boundary = evaluate_development_work(
        items=[
            {
                "id": "work_unit",
                "status": "NEED_HUMAN_DECISION",
                "needs_human": True,
                "reason": "correlation_id の単位が複数解釈",
            }
        ],
        save=False,
    )
    assert boundary["may_proceed_implementation"] is False
    assert boundary["decision"]["human_decision_required"] is True
    assert boundary["specification_status"] == "NEED_HUMAN_DECISION"


def test_missing_definition_boundary_forbids_complete(tmp_path):
    from ai_tool.policy.loader import PolicyLoadError, load_development_policy

    payload = {
        "policy_id": "ai-agent-development-policy",
        "version": "1.4",
        "item_statuses": ["CONNECTED"],
        "completion": {},
        "human_decision_required_when": ["NEED_HUMAN_DECISION"],
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        load_development_policy(path=path)
        raise AssertionError("definition_boundary 欠落でも load できた")
    except PolicyLoadError as exc:
        assert "definition_boundary" in str(exc)
    out = evaluate_development_work(
        items=[{"id": "a", "status": "CONNECTED"}],
        policy_path=path,
        save=False,
    )
    assert out["policy_loaded"] is False
    assert out["may_claim_specification_complete"] is False


def test_concept_definitions_keep_origin_and_undetermined_separate():
    from ai_tool.policy.paths import concept_definitions_path

    text = concept_definitions_path().read_text(encoding="utf-8")
    spec = (concept_definitions_path().parents[2] / "PROJECT_SPEC.md").read_text(encoding="utf-8")
    assert "This project is a local AI Agent running on a Windows PC." in spec
    assert "This project is a local AI Agent running on a Windows PC." not in text
    assert "Origin: PROJECT_SPEC.md" in text
    assert "## correlation_id" in text
    assert "Chat ターンという作業単位" in text
    assert "human_revision" in text
    assert "変更理由" in text
    assert "Origin へ回帰" in text or "Origin 側" in text
    assert "## implementation_id" in text
    assert "## test_run_id" in text
    impl = text.split("## implementation_id", 1)[1].split("## test_run_id", 1)[0]
    assert "Status: NOT_DETERMINED" in impl
    assert "Current: NONE" in impl
    assert "CURRENT / CODE DRIFT" in text
    complete = evaluate_development_work(
        items=[{"id": "a", "status": "CONNECTED", "evidence": "policy load"}],
        save=False,
    )
    assert complete["specification_status"] == "COMPLETE"
    assert complete["policy_version"] == "1.5"
