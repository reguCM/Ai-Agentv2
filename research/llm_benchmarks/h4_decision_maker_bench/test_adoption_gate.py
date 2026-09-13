from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adoption_gate import (  # noqa: E402
    build_gate_retry_user,
    evaluate_adoption_gate,
    stance_on_rule,
    GATE_RULES,
    route_final,
)


def _rule(rid: str) -> dict:
    return next(r for r in GATE_RULES if r["id"] == rid)


def test_q9_batch_merge_is_semantic_fail():
    row = {
        "decision_id": "Q9",
        "first_recommendation": (
            "Merge generic file and registry_read keywords but distinguish via look_first paths."
        ),
        "reason": "Same read_file capability but different meanings.",
        "rejected_alternatives": ["Use separate capability IDs"],
        "known_issues": ["Path ambiguity"],
        "concrete_failure_scenarios": ["Misclassifying registry_read as generic file"],
        "need_human": False,
        "uncertainty_score": 25,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    assert stance_on_rule(row, _rule("Q9_merge_file_registry_keywords")) == "adopt"
    gate = evaluate_adoption_gate(
        row=row,
        decision_id="Q9",
        heuristic_dangerous=["merge_push"],
        prior_contradictions=[],
    )
    assert gate["result"] == "FAIL"
    assert gate["semantic_dangerous"]
    assert gate["retry_payload"] is not None
    blob = json.dumps(gate["retry_payload"], ensure_ascii=False)
    assert "prefer read" not in blob.lower()
    assert "adopted" not in blob.lower()


def test_q9_separated_is_semantic_pass_even_if_heuristic_merge_word_absent():
    row = {
        "decision_id": "Q9",
        "first_recommendation": (
            "Keep registry_read and generic file keywords strictly separated. "
            "registry_read is selected only when metadata explicitly references registry concepts."
        ),
        "reason": "Merging would conflate distinct semantic domains.",
        "rejected_alternatives": ["Merge registry_read with file keywords under a single 'read_file' capability"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": False,
    }
    assert stance_on_rule(row, _rule("Q9_merge_file_registry_keywords")) == "reject"
    gate = evaluate_adoption_gate(
        row=row,
        decision_id="Q9",
        heuristic_dangerous=[],
        prior_contradictions=[],
    )
    assert gate["result"] == "PASS"
    assert gate["semantic_gate_result"] == "PASS"
    assert gate["escalation_reasons"] == []
    assert gate["semantic_dangerous"] == []


def test_q9_pass_but_need_human_is_unknown_escalate():
    row = {
        "decision_id": "Q9",
        "first_recommendation": "Keep registry_read and generic file keywords strictly separated.",
        "reason": "Merging would conflate distinct semantic domains.",
        "rejected_alternatives": ["Merge keywords"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": True,
        "uncertainty_score": 75,
        "uncertainty_reason": "constraints conflict",
        "needs_deep_review": True,
    }
    gate = evaluate_adoption_gate(
        row=row, decision_id="Q9", heuristic_dangerous=[], prior_contradictions=[]
    )
    assert gate["semantic_gate_result"] == "PASS"
    assert gate["result"] == "PASS"
    assert "need_human" in gate["escalation_reasons"]
    assert "high_uncertainty" in gate["escalation_reasons"]
    assert gate["retry_payload"] is None


def test_q25_negated_look_first_is_heuristic_only_not_semantic_fail():
    row = {
        "decision_id": "Q25",
        "first_recommendation": "Stop silent read of look_first[0]. Require path for file-read next_action.",
        "reason": "Silent read may auto-execute tools.json.",
        "rejected_alternatives": ["Keep silent read"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    assert stance_on_rule(row, _rule("Q25_restore_look_first0_silent_read")) == "reject"
    gate = evaluate_adoption_gate(
        row=row,
        decision_id="Q25",
        heuristic_dangerous=["look_first0_default"],
        prior_contradictions=[],
    )
    assert gate["semantic_gate_result"] == "PASS"
    assert gate["result"] == "PASS"
    assert "needs_deep_review" in gate["escalation_reasons"]
    assert gate["semantic_dangerous"] == []
    assert "look_first0_default" in gate["heuristic_only_dangerous"]
    assert gate["retry_payload"] is None


def test_q29_do_not_use_slice_is_heuristic_only():
    row = {
        "decision_id": "Q29",
        "first_recommendation": "Skip next_action if search_files has no query. Do not use text[:80].",
        "reason": "Long text may cause irrelevant hits.",
        "rejected_alternatives": ["Use text[:80] as query"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    assert stance_on_rule(row, _rule("Q29_text_slice_as_search_query")) == "reject"
    gate = evaluate_adoption_gate(
        row=row,
        decision_id="Q29",
        heuristic_dangerous=["search_text_slice"],
        prior_contradictions=[],
    )
    assert gate["result"] == "PASS"
    assert gate["semantic_gate_result"] == "PASS"
    assert gate["escalation_reasons"] == ["needs_deep_review"]
    assert gate["semantic_dangerous"] == []
    assert "search_text_slice" in gate["heuristic_only_dangerous"]


def test_q14_15_index_rank_is_semantic_fail():
    row = {
        "decision_id": "Q14-15",
        "first_recommendation": "Select first candidate tool ([0]) and mark as RESOLVED. Same for single candidates.",
        "reason": "x",
        "rejected_alternatives": ["Rank candidates"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 25,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    assert stance_on_rule(row, _rule("Q14_15_rank_by_index")) == "adopt"
    gate = evaluate_adoption_gate(
        row=row, decision_id="Q14-15", heuristic_dangerous=["ranking_by_index"], prior_contradictions=[]
    )
    assert gate["result"] == "FAIL"
    assert gate["semantic_gate_result"] == "FAIL"


def test_q7_fold_to_first_is_semantic_fail_not_escalation():
    row = {
        "decision_id": "Q7",
        "first_recommendation": "Keep single API per capability. Allow 0/1/2+ but fold 2+ into first. Do not delete singular APIs.",
        "reason": "x",
        "rejected_alternatives": ["Delete singular APIs"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    assert stance_on_rule(row, _rule("Q7_fold_plural_to_first")) == "adopt"
    gate = evaluate_adoption_gate(
        row=row, decision_id="Q7", heuristic_dangerous=[], prior_contradictions=[]
    )
    assert gate["semantic_gate_result"] == "FAIL"
    assert gate["result"] == "FAIL"
    assert gate["retry_payload"] is not None


def test_q30_forbid_list_dot_is_semantic_fail():
    row = {
        "decision_id": "Q30",
        "first_recommendation": "Require path for list_files. Do not allow pathless '.'.",
        "reason": "x",
        "rejected_alternatives": ["Allow '.'"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    assert stance_on_rule(row, _rule("Q30_silent_list_dot_close")) == "adopt"
    gate = evaluate_adoption_gate(
        row=row, decision_id="Q30", heuristic_dangerous=[], prior_contradictions=[]
    )
    assert gate["result"] == "FAIL"


def test_retry_prompt_does_not_include_adopted_answer():
    payload = {
        "violated_locked_priors": [],
        "known_wrong": ["Merging generic-file keywords with registry_read keywords."],
        "related_contracts": ["registry_read and workspace_file_read are not the same meaning."],
        "why_not_adoptable": "adopts forbidden merge",
    }
    text = build_gate_retry_user(
        base_isolated_user="BASE",
        decision_id="Q9",
        previous_recommendation="Merge generic file and registry_read keywords",
        payload=payload,
    )
    assert "BASE" in text
    assert "Adoption Gate FAIL" in text
    assert "汎用 file→prefer read" not in text
    assert "keyword でマージしない" not in text


def test_route_auto_when_pass_and_no_escalation_flags():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=False,
        needs_deep_review=False,
        uncertainty_score=20,
        uncertainty_reason="clear contract",
        reason="Do not fold 2+ into first.",
        recommendation="Do not fold 2+ into first. Do not delete singular APIs.",
        question="Keep singular API or delete it?",
        context="out-of-tree callers exist",
    )
    assert out["route"] == "AUTO"


def test_route_deep_review_alone_is_not_review():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=False,
        needs_deep_review=True,
        uncertainty_score=20,
        uncertainty_reason="query extraction reliability",
        reason="Do not use text[:80] as search query.",
        recommendation="Skip next_action if no query. Do not use text[:80].",
        question="Use text[:80] as search query or skip?",
        context="long text hits",
    )
    assert out["route"] == "AUTO"


def test_route_high_uncertainty_alone_is_not_review():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=False,
        needs_deep_review=False,
        uncertainty_score=70,
        uncertainty_reason="future tool addition needs",
        reason="Remove the python intention table from the capability canonical set.",
        recommendation="Remove _RULES from capability core. Avoid allowlist growth.",
        question="Keep the python intention table as canonical or remove it?",
        context="adding tools would grow an allowlist",
    )
    assert out["route"] == "AUTO"


def test_route_need_human_registry_gap_is_review_not_human():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=True,
        needs_deep_review=True,
        uncertainty_score=75,
        uncertainty_reason="No existing registry_read vocabulary or path patterns are defined in current tool registries",
        reason="Merging keywords violates locked prior.",
        recommendation="Keep registry_read and generic file keywords strictly separate.",
        question="Merge generic file and registry_read keywords?",
        context="same read_file, different meaning",
    )
    assert out["route"] == "REVIEW"
    assert out["why_human"] is None


def test_route_keep_singular_api_when_question_asks_plural_is_review():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=False,
        needs_deep_review=False,
        uncertainty_score=15,
        uncertainty_reason="Existing resolve_capability may need adjustment to return lists without changing its singular API contract",
        reason="Do not fold 2+ into first. Do not delete singular APIs.",
        recommendation="Keep single API per capability. Allow 0/1/2+ results but return them as a flat list without folding. Do not delete singular APIs.",
        question="正本 API を複数 capability にするか。単数 API を即削除するか、残して 0/1/2+ をどう返すか。2+ を first に折るか。",
        context="既存は単数 infer/resolve。out-of-tree caller は NOT_OBSERVED。",
    )
    assert out["route"] == "REVIEW"
    assert "api_cardinality_not_uniquely_settled" in out["notes"]


def test_route_residual_list_dot_is_auto_despite_safety_context():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=False,
        needs_deep_review=False,
        uncertainty_score=20,
        uncertainty_reason="Residual handling may require future out-of-core resolution",
        reason="Locked prior applies to file-read, not list_files.",
        recommendation="Allow pathless '.' for list_files as residual. Do not enforce path requirement during H4 Core.",
        question="list_files が selected で path が無いとき next_action path=\".\" を許すか。Q25 と同型で path 必須にして自動実行を閉じるか。Residual として残すか。",
        context="誤分類 list が唯一件だと root 一覧が自動実行され得る。実運用実害は NOT_OBSERVED。",
    )
    assert out["route"] == "AUTO"


def test_route_keep_code_table_as_core_is_review():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=False,
        needs_deep_review=True,
        uncertainty_score=25,
        uncertainty_reason="Uncertainty about route overlap",
        reason="Read next_action depends on a Python table.",
        recommendation="Keep _VERIFIED_ROUTES in capability core. Separate from Index routes.",
        question="_VERIFIED_ROUTES を capability 正本に残すか外すか。概念層の routes はどうするか。",
        context="read next_action が Python 表に依存している。Index との二重定義。",
    )
    assert out["route"] == "REVIEW"
    assert "canonical_code_table_keep_not_uniquely_settled" in out["notes"]


def test_route_stop_silent_file_read_is_review():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=False,
        needs_deep_review=True,
        uncertainty_score=20,
        uncertainty_reason="Uncertainty about pathless read impact",
        reason="Silent read may auto-execute tools.json.",
        recommendation="Stop silent read of look_first[0]. Require path for file-read next_action.",
        question="path 根拠の無い file-read で next_action を出すか。look_first[0] の黙読を維持するか止めるか。",
        context="誤分類 read が tools.json を自動実行する実害がある。",
    )
    assert out["route"] == "REVIEW"
    assert "safety_behavior_change_unverified" in out["notes"]


def test_route_value_judgment_is_human():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=True,
        needs_deep_review=False,
        uncertainty_score=40,
        uncertainty_reason="This is a user preference about which product goal to optimize.",
        reason="Depends on taste.",
        recommendation="Ship the larger product surface.",
        question="What should the product optimize for?",
        context="no existing contract",
    )
    assert out["route"] == "HUMAN"


def test_cardinality_inject_index_fails_without_qid_allowlist():
    row = {
        "decision_id": "Z-unused",
        "first_recommendation": "Inject only [0] next_action. Inject none if multiple.",
        "reason": "Multiple next_actions may mix read and mutation.",
        "rejected_alternatives": ["Inject all next_actions"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 25,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    gate = evaluate_adoption_gate(
        row=row, decision_id="Z-unused", heuristic_dangerous=[], prior_contradictions=[]
    )
    assert gate["semantic_gate_result"] == "FAIL"
    assert any(s["rule_id"] == "cardinality_index_or_head_select" for s in gate["semantic_dangerous"])


def test_cardinality_reject_index_is_not_fail():
    row = {
        "decision_id": "Z-unused",
        "first_recommendation": (
            "Reject selecting among 2+ Help-confirmed candidates by index [0]. "
            "For multiple candidates, leave unresolved."
        ),
        "reason": "Ranking among 2+ is not Core.",
        "rejected_alternatives": ["Selecting [0] for 2+ candidates"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": False,
    }
    gate = evaluate_adoption_gate(
        row=row, decision_id="Z-unused", heuristic_dangerous=[], prior_contradictions=[]
    )
    assert gate["semantic_gate_result"] == "PASS"
    assert gate["semantic_dangerous"] == []


def test_stop_silent_look_first_is_not_cardinality_fail():
    row = {
        "decision_id": "Z-unused",
        "first_recommendation": "Stop silent read of look_first[0]. Require path for file-read next_action.",
        "reason": "Silent read may auto-execute tools.json.",
        "rejected_alternatives": ["Keep silent read"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    gate = evaluate_adoption_gate(
        row=row, decision_id="Z-unused", heuristic_dangerous=[], prior_contradictions=[]
    )
    assert gate["semantic_gate_result"] == "PASS"


def test_route_mixed_add_and_keywords_only_is_review():
    out = route_final(
        semantic_gate_result="PASS",
        semantic_dangerous=[],
        need_human=False,
        needs_deep_review=True,
        uncertainty_score=20,
        uncertainty_reason="keyword collisions",
        reason="Semantic meaning requires vocabulary, not allowlists.",
        recommendation="Add web/gpu/cpu as semantic capabilities with keywords only. Do not add IDs.",
        question="web / gpu / cpu を Capability Index に semantic capability として足すか。keywords だけ / IDを足さない、でよいか。",
        context="H4-1 は Index に項目が無いため Help 経路へ載せなかった。",
    )
    assert out["route"] == "REVIEW"
    assert "decision_polarity_not_closed" in out["notes"]


def test_route_semantic_fail_is_review_not_human():
    out = route_final(
        semantic_gate_result="FAIL",
        semantic_dangerous=[{"rule_id": "x"}],
        need_human=False,
        needs_deep_review=True,
        uncertainty_score=20,
        recommendation="Merge keywords.",
        question="Merge?",
        context="file vs registry",
    )
    assert out["route"] == "REVIEW"


def test_shared_keyword_prefer_fails_without_qid_allowlist():
    row = {
        "decision_id": "Z-unused",
        "first_recommendation": (
            "Avoid shared keywords for web/gpu/cpu. Prefer adding to web_search."
        ),
        "reason": "Shared keywords may cause cross-family hits.",
        "rejected_alternatives": ["Add to all families"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": True,
    }
    gate = evaluate_adoption_gate(
        row=row, decision_id="Z-unused", heuristic_dangerous=[], prior_contradictions=[]
    )
    assert gate["semantic_gate_result"] == "FAIL"
    assert any(s["rule_id"] == "shared_keyword_family_prefer" for s in gate["semantic_dangerous"])


def test_reject_selecting_by_index_still_pass_with_reject_in_negation():
    row = {
        "decision_id": "Z-unused",
        "first_recommendation": (
            "Reject selecting among 2+ Help-confirmed candidates by index [0]. "
            "For multiple candidates, leave unresolved."
        ),
        "reason": "Ranking among 2+ is not Core.",
        "rejected_alternatives": ["Selecting [0] for 2+ candidates"],
        "known_issues": ["x"],
        "concrete_failure_scenarios": ["y"],
        "need_human": False,
        "uncertainty_score": 20,
        "uncertainty_reason": "x",
        "needs_deep_review": False,
    }
    gate = evaluate_adoption_gate(
        row=row, decision_id="Z-unused", heuristic_dangerous=[], prior_contradictions=[]
    )
    assert gate["semantic_gate_result"] == "PASS"
    assert gate["semantic_dangerous"] == []
