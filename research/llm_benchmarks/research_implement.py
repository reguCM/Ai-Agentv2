"""
④ Research → Implementation ベンチ。unittest ではない。

Clarity で「使用率です」まで得た STATE を持ったまま、
Research → Judge → Implementation まで進め、実際の Tool を作る。
Repair は呼ばない。失敗したら Research / Judge / Implementation を切り分ける。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.clarity_state_classify import inspect_user_state
from tools.ai.state.task_state import TaskState
from tools.ai.state.state_sync import sync_research_into_state
from tools.ai.state.rule_partial import apply_rule_partial
from tools.ai.state.global_judge_trigger import (
    evaluate_global_judge_trigger,
    execute_global_judge_round,
    finalize_observation,
    init_shadow_summary,
    record_shadow_round,
)
from tools.ai.llm.context_allocation import (
    finalize_context_budget_shadow,
    init_context_budget_shadow,
)
from research.llm_benchmarks.environment_benchmark import (
    IMPLEMENT,
    MAX_RESEARCH_ROUNDS,
    MAX_RESEARCH_STAGNATION,
    MODEL,
    PROFILE_ID,
    PROJECT_CONVENTIONS,
    STOP,
    ask_json,
    compact_research,
    contains_forbidden_answer,
    diagnose_implement,
    evaluate_research_progress,
    finding_keys,
    load_json_file,
    load_registry_tools,
    prepare_code_payload,
    record_phase,
    rejected_command_list,
    restore_system_tools,
    run_research,
    save_json_file,
    snapshot_system_tools,
    verified_environment,
)
from research.llm_benchmarks.research_implement_classify import (
    CREATE_REQUEST,
    PIPELINE_STAGE_LABELS,
    inspect_create_result,
    start_from_clarity_state,
    summarize_verified_round,
)
from research.llm_benchmarks.judge_verify_retry_classify import inspect_judge_verify_retry
from tools.ai.llm.adapter import (
    build_implement_messages,
    build_proposal_messages,
    build_research_judge_messages,
    validation_extra,
)
from tools.ai.state.decision_store import apply_judgment, extra_keys_from_proposal
from tools.ai.tool_builder.implementation import create_tool_implementation
from tools.ai.tool_builder.proposal import create_tool_proposal
from tools.system.tool_builder.validate.proposal_completeness import (
    validate_proposal_completeness,
)
from tools.ai.tool_builder.research_judge import (
    create_research_judgment,
    items_from_missing,
    normalize_judgment,
    prepare_followup_research,
)
from tools.ai.tool_builder.research_result import (
    mark_insufficient,
    merge_packed_research,
)
from tools.system.llm import stop_model
from tools.system.timing import Timing, stage
from tools.system.execution_identity import (
    RESEARCH_PIPELINE,
    log_run_start,
)
from tools.system.tool_builder.apply import has_repair_code
from tools.system.tool_builder.implementation_classify import classify_implementation
from tools.system.tool_builder.register import register_tool
from tools.system.tool_builder.test import test_tool
from tools.system.tool_builder.validate.implementation import (
    validate_tool_implementation,
)
from tools.system.tool_builder.validate.result import validate_tool_result
from tools.system.tool_builder.validate.spec import validate_tool_spec


REPEAT = int(os.environ.get("AI_AGENT_CREATE_REPEAT") or 1)
CASE_ENV = os.environ.get("AI_AGENT_RESEARCH_IMPLEMENT_CASE")
RESULTS_PATH = "research/llm_benchmarks/research_implement_results.json"
FAILURES_PATH = "research/llm_benchmarks/research_implement_failures.json"


def _resolve_request():
    """Case JSON が指定されていれば request/state をそこから取得し Clarity をスキップ。"""
    if not CASE_ENV:
        return None
    from tools.system.llm_failure_memory import load_environment_case
    case = load_environment_case(CASE_ENV)
    if case is None:
        raise FileNotFoundError(f"Case not found: {CASE_ENV}")
    request = case["request"]
    state_data = case.get("state") or {}
    state = TaskState(
        task=state_data.get("task", request),
        facts=state_data.get("facts"),
        decisions=state_data.get("decisions"),
        selected_findings=state_data.get("selected_findings"),
        constraints=state_data.get("constraints"),
        open_questions=state_data.get("open_questions"),
        unresolved=state_data.get("unresolved"),
    )
    return {"request": request, "state": state}


def empty_result(request, state):
    return {
        "ok": False,
        "request": request,
        "repaired": False,
        "proposal_error": None,
        "proposal_name": None,
        "proposal": None,
        "research_rounds": 0,
        "research_sufficient": False,
        "research_stagnation": 0,
        "research_stop_reason": None,
        "error": None,
        "fail_stage": None,
        "checks": {},
        "payload": None,
        "registered": None,
        "test_result": None,
        "implementation_class": None,
        "diagnosis": None,
        "trace": [],
        "state": state.snapshot() if state is not None else None,
        "user_state": inspect_user_state(state) if state is not None else None,
        "pipeline": {
            "request": request,
            "research": None,
            "judgments": [],
            "progress": [],
            "research_rounds_detail": [],
            "generated_code": None,
            "repair": "skipped",
        },
    }


def apply_checks(
    result,
    *,
    research=None,
    classified=None,
    path_exists=False,
    in_registry=False,
):
    inspected = inspect_create_result(
        research=research,
        judgments=result["pipeline"].get("judgments") or [],
        research_sufficient=result.get("research_sufficient"),
        payload=result.get("payload"),
        classified=classified or result.get("implementation_class"),
        registered=result.get("registered"),
        proposal=result.get("proposal"),
        path_exists=path_exists,
        in_registry=in_registry,
        test_result=result.get("test_result"),
        proposal_error=result.get("proposal_error"),
        repaired=result.get("repaired"),
        user_state=result.get("user_state"),
        research_rounds=result["pipeline"].get("research_rounds_detail") or [],
    )
    result["ok"] = inspected["ok"]
    result["fail_stage"] = inspected["fail_stage"]
    result["checks"] = inspected["checks"]
    result["pipeline_stages"] = inspected["pipeline"]
    result["repaired"] = inspected["repaired"]
    # KSS-1.3: final_pass を各 round observation へ後付け（行動変更なし）
    try:
        from tools.ai.state.exploration_value import attach_run_outcomes

        pipe = result.get("pipeline") or {}
        rounds = pipe.get("exploration_value_rounds") or []
        if not rounds:
            rounds = [
                (item.get("exploration_value_observation") or {})
                for item in (pipe.get("research_rounds_detail") or [])
                if (item.get("exploration_value_observation") or {}).get("enabled")
            ]
        if rounds:
            linked = attach_run_outcomes(
                rounds,
                final_pass=result.get("ok"),
                fail_stage=result.get("fail_stage"),
                fail_reason=result.get("research_stop_reason")
                or result.get("error"),
            )
            result.setdefault("pipeline", {})["exploration_value_rounds"] = linked
            by_round = {b.get("round_index"): b for b in linked}
            for item in result["pipeline"].get("research_rounds_detail") or []:
                obs = by_round.get(item.get("round"))
                if obs:
                    item["exploration_value_observation"] = obs
    except Exception:
        pass
    # KSS-1.4: trajectory finalize（pass 確定後）
    try:
        from tools.ai.state.information_loss import build_trajectory
        from tools.ai.state.web_answer_presence import audit_round_answer_presence

        pipe = result.get("pipeline") or {}
        details = pipe.get("research_rounds_detail") or []
        k13_rounds = [
            item.get("exploration_value_observation")
            for item in details
            if isinstance(item.get("exploration_value_observation"), dict)
            and item["exploration_value_observation"].get("enabled")
        ]
        traj = build_trajectory(
            case_id=os.environ.get("AI_AGENT_EXPERIMENT_CASE"),
            rounds_kss13=k13_rounds or None,
            round_details=details,
            final_pass=result.get("ok"),
            fail_stage=result.get("fail_stage"),
            fail_reason=result.get("research_stop_reason") or result.get("error"),
            stop_reason=(pipe.get("research") or {}).get("stop_reason"),
            research_run_id=os.environ.get("AI_AGENT_EXPERIMENT_ID"),
        )
        # attach answer audits already on round items if present
        for i, item in enumerate(details):
            loss = item.get("information_loss_observation")
            if isinstance(loss, dict) and loss.get("enabled"):
                if i < len(traj.get("round_observations") or []):
                    # merge run linkage into existing
                    loss["run_linkage"] = (
                        traj["round_observations"][i].get("run_linkage") or {}
                    )
                    loss["next_round_gain"] = traj["round_observations"][i].get(
                        "next_round_gain"
                    )
                    loss["eventual_success"] = traj["round_observations"][i].get(
                        "eventual_success"
                    )
            elif traj.get("round_observations"):
                # offline-style attach
                if i < len(traj["round_observations"]):
                    rob = dict(traj["round_observations"][i])
                    if not rob.get("web_answer_presence_audit"):
                        rob["web_answer_presence_audit"] = audit_round_answer_presence(
                            request_text=str(result.get("request") or ""),
                            case_id=os.environ.get("AI_AGENT_EXPERIMENT_CASE"),
                            round_item=item,
                        )
                    item["information_loss_observation"] = rob
        result.setdefault("pipeline", {})["information_loss_trajectory"] = traj
    except Exception:
        pass
    return result


def registry_has_tool(name):
    if not name:
        return False
    for item in load_registry_tools():
        if item.get("name") == name:
            return True
    return False


def run_proposal(result, state, environment, tools, request):
    registry_summary = [
        {
            "name": tool.get("name"),
            "category": tool.get("category"),
            "subcategory": tool.get("subcategory"),
            "description": tool.get("description"),
            "module": tool.get("module"),
        }
        for tool in tools
        if tool.get("name") not in (
            "create_tool_proposal",
            "create_tool_implementation",
        )
    ]
    materials = create_tool_proposal(
        request,
        project_spec=PROJECT_CONVENTIONS,
        registry=registry_summary,
        environment=environment,
    )
    materials["structure_hint"] = {
        "module_pattern": "tools.<category>.<subcategory>.<filename>",
        "return_shape": {"status": "値"},
        "note": "参考は配置と戻り値の形だけ。取得コマンドはここにない。",
    }
    payload, error, text, _detail = ask_json(
        build_proposal_messages, materials, state=state
    )
    record_phase(result, "proposal", error=error, text=text, payload=payload)
    if error:
        result["proposal_error"] = error
        result["error"] = error
        return None
    proposals = payload.get("proposals") if isinstance(payload, dict) else None
    if not isinstance(proposals, list) or not proposals:
        result["proposal_error"] = "no_proposal"
        result["error"] = "no_proposal"
        return None
    proposal = proposals[0]
    spec = validate_tool_spec(
        proposal, environment, request=request, existing_tools=tools
    )
    if spec.get("status") == "fail":
        payload, error, text, _detail = ask_json(
            build_proposal_messages,
            materials,
            extra=validation_extra(spec.get("errors")),
            state=state,
        )
        record_phase(result, "proposal_retry", error=error, text=text, payload=payload)
        if error or not payload or not payload.get("proposals"):
            result["proposal_error"] = "proposal_validation_ng"
            result["error"] = "proposal_validation_ng"
            result["spec_errors"] = spec.get("errors")
            return None
        proposal = payload["proposals"][0]
        spec = validate_tool_spec(
            proposal, environment, request=request, existing_tools=tools
        )
        if spec.get("status") == "fail":
            result["proposal_error"] = "proposal_validation_ng"
            result["error"] = "proposal_validation_ng"
            result["spec_errors"] = spec.get("errors")
            return None
    completeness = validate_proposal_completeness(proposal)
    if not completeness["ok"]:
        payload, error, text, _detail = ask_json(
            build_proposal_messages,
            materials,
            extra=completeness["hint"],
            state=state,
        )
        record_phase(result, "proposal_completeness_retry", error=error, text=text, payload=payload)
        if not error and isinstance(payload, dict) and payload.get("proposals"):
            proposal = payload["proposals"][0]

    result["proposal"] = proposal
    result["proposal_name"] = proposal.get("name")
    try:
        from tools.ai.state.decision_evidence import (
            capture_proposal_evidence,
            kss11_obs_enabled,
        )

        if kss11_obs_enabled():
            result["decision_evidence_proposal"] = capture_proposal_evidence(
                proposal_validation=spec,
                completeness=completeness,
                fail_stage=result.get("fail_stage"),
            )
    except Exception:
        pass
    return proposal


def run_research_judge(result, proposal, environment, state, request):
    research = {}
    next_items = None
    next_handoff = None
    judgments = []
    progress_log = []
    round_details = []
    last_researched = None
    seen_keys = set()
    previous_missing = None
    stagnation = 0
    global_judge_shadow = init_shadow_summary()
    context_budget_shadow = init_context_budget_shadow()
    kss13_prior_sets = None
    kss13_bundles = []
    searched_queries = []
    search_intent = None
    try:
        from tools.ai.state.exploration_value import empty_prior_sets

        kss13_prior_sets = empty_prior_sets()
    except Exception:
        kss13_prior_sets = None
    for round_num in range(1, MAX_RESEARCH_ROUNDS + 1):
        with stage("research"):
            researched = run_research(
                proposal,
                environment,
                items=next_items,
                rejected_commands=(next_handoff or {}).get("rejected_commands")
                or rejected_command_list(research),
                prior_failures=(next_handoff or {}).get("prior_failures"),
                judge_reason=(next_handoff or {}).get("judge_reason"),
                state=state,
                searched_queries=searched_queries,
                search_intent=search_intent,
            )
        searched_queries = list(researched.get("searched_queries") or searched_queries)
        search_intent = researched.get("search_intent") or search_intent
        last_researched = researched
        result["research_rounds"] = round_num
        if round_num > 1:
            research = merge_packed_research(research, researched["research"])
        else:
            research = researched["research"]
        round_keys = finding_keys(
            (researched.get("research") or {}).get("usable_findings")
        )
        research_phase_extra = {}
        candidates_detail = researched.get("candidates_detail")
        if (
            isinstance(candidates_detail, dict)
            and candidates_detail.get("kind") == "context_overflow"
        ):
            research_phase_extra["context_overflow"] = candidates_detail
        record_phase(
            result,
            f"research_{round_num}",
            error=researched["candidates_error"],
            text=researched["candidates_text"],
            payload=researched["candidates_payload"],
            extra=research_phase_extra or None,
        )
        if researched.get("candidates_error") == "context_overflow":
            result["research_stop_reason"] = "context_overflow"
            result["error"] = "context_overflow"
            result["diagnosis"] = candidates_detail
            break
        verified_summary = summarize_verified_round(researched)
        rule_partial = apply_rule_partial(
            state,
            researched.get("research") or {},
            round_num=round_num,
        )
        gj_trigger = evaluate_global_judge_trigger(
            rule_partial.get("escalation"),
            round_num=round_num,
            round_research=(researched.get("research") or {}),
            state=state,
            stagnation=stagnation,
            max_rounds=MAX_RESEARCH_ROUNDS,
            max_stagnation=MAX_RESEARCH_STAGNATION,
            candidates_error=researched.get("candidates_error"),
        )
        judge_materials = create_research_judgment(request, proposal, research, state=state)

        def _run_llm_judge():
            with stage("judge"):
                payload, error, text, detail = ask_json(
                    build_research_judge_messages, judge_materials, state=state
                )
            judgment = normalize_judgment(payload)
            if error:
                judgment["error"] = error
            judge_held = inspect_judge_verify_retry(payload, error)
            return {
                "payload": payload,
                "error": error,
                "text": text,
                "detail": detail,
                "judgment": judgment,
                "judge_held": judge_held,
            }

        gj_result = execute_global_judge_round(
            gj_trigger=gj_trigger,
            state=state,
            escalation=rule_partial.get("escalation"),
            round_num=round_num,
            run_llm_judge=_run_llm_judge,
            skip_event_index=int(global_judge_shadow.get("live_skip_count") or 0)
            + int(global_judge_shadow.get("audit_count") or 0)
            + 1,
            progress_context={
                "previous_missing": previous_missing,
                "round_finding_keys": round_keys,
                "seen_keys": seen_keys,
                "stagnation": stagnation,
                "round_num": round_num,
                "max_rounds": MAX_RESEARCH_ROUNDS,
                "max_stagnation": MAX_RESEARCH_STAGNATION,
            },
        )
        gj_trigger = gj_result["gj_trigger"]
        judgment = gj_result["judgment"]
        payload = gj_result["payload"]
        error = gj_result["error"]
        text = gj_result["text"]
        detail = gj_result["detail"]
        judge_held = gj_result["judge_held"]
        quality_compare = gj_result["quality_compare"]
        shadow_judgment = gj_result["shadow_judgment"]

        if gj_result.get("live_skipped") or gj_result.get("audit_only"):
            # 制御は live_skip judgment。audit の実 Judge は観測のみ。
            pass
        else:
            apply_judgment(
                state,
                judgment,
                extra_keys=extra_keys_from_proposal(proposal),
            )
        sync_research_into_state(
            state,
            research=research,
            round_num=round_num,
            judgment=judgment,
            previous_missing=previous_missing,
            round_research=(researched.get("research") or {}),
            skip_round_findings=bool(rule_partial.get("findings_recorded")),
        )
        kss_obs = researched.get("knowledge_source_observation")
        if isinstance(kss_obs, dict) and kss_obs.get("enabled"):
            try:
                from tools.ai.state.knowledge_source import (
                    assess_known_coverage,
                    calibrate_proposals_with_results,
                    record_observation_event,
                )

                coverage_after = assess_known_coverage(state)
                kss_obs = dict(kss_obs)
                kss_obs["round"] = round_num
                kss_obs["known_coverage_after"] = coverage_after
                kss_obs["calibration"] = calibrate_proposals_with_results(
                    kss_obs.get("proposal_observations") or [],
                    (researched.get("verified") or {}).get("results") or [],
                    coverage_before=kss_obs.get("known_coverage") or {},
                    coverage_after=coverage_after,
                )
                record_observation_event(state, kss_obs, round_num=round_num)
            except Exception:
                kss_obs = {**(kss_obs or {}), "calibration_error": True}
        researched["knowledge_source_observation"] = kss_obs
        kss1_obs = researched.get("decision_confidence_observation")
        if isinstance(kss1_obs, dict) and kss1_obs.get("enabled"):
            try:
                from tools.ai.state.decision_confidence import (
                    finalize_decision_observation,
                    record_decision_confidence_event,
                )
                from tools.ai.state.knowledge_source import assess_known_coverage

                # coverage_before は verify 前に近い値が pre_obs に無い場合の近似
                coverage_before = kss1_obs.get("known_coverage_before") or assess_known_coverage(
                    state
                )
                # 同期前に before を取りたいが、ここでは同期後。pre の no_gain は KSS-0 から
                kss0 = researched.get("knowledge_source_observation") or {}
                if isinstance(kss0, dict) and kss0.get("known_coverage"):
                    coverage_before = kss0.get("known_coverage")
                kss1_obs = finalize_decision_observation(
                    kss1_obs,
                    researched.get("verified"),
                    state,
                    round_num=round_num,
                    coverage_before=coverage_before,
                    event_ids=(rule_partial.get("event_ids") if rule_partial else None),
                )
                if isinstance(kss0, dict) and kss0.get("knowledge_source_selection"):
                    kss1_obs["kss0_preferred_source"] = (
                        kss0.get("knowledge_source_selection") or {}
                    ).get("preferred_source")
                record_decision_confidence_event(state, kss1_obs, round_num=round_num)
            except Exception:
                kss1_obs = {**(kss1_obs or {}), "finalize_error": True}
        researched["decision_confidence_observation"] = kss1_obs
        global_judge_shadow = record_shadow_round(
            global_judge_shadow,
            {
                "round": round_num,
                **gj_trigger,
                "llm_called": gj_result.get("llm_called"),
                "live_skipped": gj_result.get("live_skipped"),
                "audit_only": gj_result.get("audit_only"),
                "quality_compare": quality_compare,
                "shadow_judgment": shadow_judgment,
                "audit_judgment": gj_result.get("audit_judgment"),
            },
        )
        judge_phase_extra = {
            "judgment": judgment,
            "global_judge_trigger": gj_trigger,
            "live_skipped": gj_result.get("live_skipped"),
            "audit_only": gj_result.get("audit_only"),
            "audit_judgment": gj_result.get("audit_judgment"),
            "rule_partial": {
                "escalation": rule_partial.get("escalation"),
                "applied_ops": [
                    p.get("op") for p in (rule_partial.get("applied") or [])
                ],
                "event_ids": rule_partial.get("event_ids"),
            },
        }
        if isinstance(detail, dict) and detail.get("kind") == "context_overflow":
            judge_phase_extra["context_overflow"] = detail
        if error == "context_overflow":
            result["research_stop_reason"] = "context_overflow"
            result["error"] = "context_overflow"
            result["diagnosis"] = detail
            record_phase(
                result,
                f"research_judge_{round_num}",
                error=error,
                text=text,
                payload=payload,
                extra=judge_phase_extra,
            )
            break
        round_details.append(
            {
                "round": round_num,
                "followup": bool(next_items),
                "research_input": {
                    "followup_questions": (next_handoff or {}).get(
                        "followup_questions"
                    )
                    or researched.get("followup_questions")
                    or [],
                    "rejected_commands": (next_handoff or {}).get(
                        "rejected_commands"
                    )
                    or rejected_command_list(research),
                    "prior_failures": (next_handoff or {}).get("prior_failures")
                    or [],
                    "judge_reason": (next_handoff or {}).get("judge_reason") or "",
                },
                "candidate_count": verified_summary["candidate_count"],
                "verified_count": verified_summary["verified_count"],
                "verifier_failure": verified_summary["any_failure"],
                "verified_runs": verified_summary["runs"],
                "candidate_keys": verified_summary.get("candidate_keys") or [],
                "web_hits": researched.get("web_hits") or [],
                "web_decision_link": researched.get("web_decision_link"),
                "web_hit_partition": researched.get("web_hit_partition"),
                "satisfies_request": judgment.get("satisfies_request"),
                "judge_grade": judge_held.get("grade"),
                "judge_retry_ok": judge_held.get("retry_ok"),
                "missing": judgment.get("missing"),
                "reason": judgment.get("reason"),
                "rule_partial": {
                    "escalation": (rule_partial.get("escalation") or {}).get("reason"),
                    "routine": (rule_partial.get("escalation") or {}).get("routine"),
                    "applied_ops": [
                        p.get("op") for p in (rule_partial.get("applied") or [])
                    ],
                    "event_ids": rule_partial.get("event_ids") or [],
                },
                "global_judge_trigger": {
                    "needed": gj_trigger.get("needed"),
                    "would_skip": gj_trigger.get("would_skip"),
                    "live_skipped": gj_result.get("live_skipped"),
                    "audit_only": gj_result.get("audit_only"),
                    "mode": gj_trigger.get("mode"),
                    "triggers": gj_trigger.get("triggers"),
                    "skip_triggers": gj_trigger.get("skip_triggers"),
                    "primary_reason": gj_trigger.get("primary_reason"),
                    "llm_calls_saved_if_skip": gj_trigger.get("llm_calls_saved_if_skip"),
                    "quality_compare": quality_compare,
                },
                "knowledge_source_observation": researched.get(
                    "knowledge_source_observation"
                ),
                "decision_confidence_observation": researched.get(
                    "decision_confidence_observation"
                ),
                "decision_evidence_observation": None,
            }
        )
        judgments.append(
            {
                "round": round_num,
                "satisfies_request": judgment.get("satisfies_request"),
                "reason": judgment.get("reason"),
                "missing": judgment.get("missing"),
                "error": judgment.get("error"),
                "judge_grade": judge_held.get("grade"),
                "proposed_decisions": judgment.get("proposed_decisions") or [],
            }
        )
        record_phase(
            result,
            f"research_judge_{round_num}",
            error=error,
            text=text,
            payload=payload,
            extra=judge_phase_extra,
        )
        decision = evaluate_research_progress(
            satisfies_request=judgment.get("satisfies_request"),
            missing=judgment.get("missing"),
            previous_missing=previous_missing,
            round_finding_keys=round_keys,
            seen_keys=seen_keys,
            stagnation=stagnation,
            round_num=round_num,
            max_rounds=MAX_RESEARCH_ROUNDS,
            max_stagnation=MAX_RESEARCH_STAGNATION,
        )
        stagnation = decision["stagnation"]
        result["research_stagnation"] = stagnation
        # KSS-1.1: 既存判断根拠の観測（行動変更なし）
        kss11_bundle = {"enabled": False, "phase": "kss-1.1"}
        try:
            from tools.ai.state.decision_evidence import (
                capture_research_round_evidence,
                kss11_obs_enabled,
                record_decision_evidence_event,
            )

            if kss11_obs_enabled():
                filt = researched.get("candidate_filter_stats") or {}
                kss11_bundle = capture_research_round_evidence(
                    round_num=round_num,
                    researched=researched,
                    candidates_before_filter=[None] * int(filt.get("before") or 0)
                    if isinstance(filt.get("before"), int)
                    else None,
                    candidates_after_filter=[None] * int(filt.get("after") or 0)
                    if isinstance(filt.get("after"), int)
                    else None,
                    judgment=judgment,
                    gj_trigger=gj_trigger,
                    gj_result=gj_result,
                    progress_decision=decision,
                    rule_partial=rule_partial,
                    kss0=researched.get("knowledge_source_observation"),
                    kss1=researched.get("decision_confidence_observation"),
                    max_rounds=MAX_RESEARCH_ROUNDS,
                    max_stagnation=MAX_RESEARCH_STAGNATION,
                )
                record_decision_evidence_event(
                    state, kss11_bundle, round_num=round_num
                )
        except Exception:
            kss11_bundle = {"enabled": False, "phase": "kss-1.1", "error": "observe_failed"}
        researched["decision_evidence_observation"] = kss11_bundle
        if round_details:
            round_details[-1]["decision_evidence_observation"] = kss11_bundle
        # KSS-1.3: 探索価値観測（行動変更なし）
        kss13_bundle = {"enabled": False, "phase": "kss-1.3"}
        try:
            from tools.ai.state.exploration_value import (
                kss13_obs_enabled,
                maybe_observe_exploration_round,
            )

            if kss13_obs_enabled():
                prog_for_obs = dict(decision)
                if decision.get("new_keys") is not None:
                    prog_for_obs["new_finding_keys"] = decision.get("new_keys")
                kss13_bundle, kss13_prior_sets = maybe_observe_exploration_round(
                    round_num=round_num,
                    researched=researched,
                    progress_decision=prog_for_obs,
                    prior_sets=kss13_prior_sets,
                    decision_evidence=kss11_bundle,
                    web_exec=None,
                    case_id=os.environ.get("AI_AGENT_EXPERIMENT_CASE"),
                    research_run_id=os.environ.get("AI_AGENT_EXPERIMENT_ID"),
                    round_item=round_details[-1] if round_details else None,
                )
                # web_exec_stats は researched 経由
                if researched.get("web_exec_stats") and kss13_bundle.get("enabled"):
                    from tools.ai.state.exploration_value import collect_web_search_stats

                    stats = researched.get("web_exec_stats")
                    if isinstance(stats, dict):
                        sv = kss13_bundle.setdefault("search_volume", {})
                        for k in (
                            "search_result_count",
                            "kept_hit_count",
                            "dropped_hit_count",
                            "web_hits_saved_count",
                        ):
                            if stats.get(k) is not None:
                                sv[k] = stats.get(k)
                kss13_bundles.append(kss13_bundle)
        except Exception:
            kss13_bundle = {
                "enabled": False,
                "phase": "kss-1.3",
                "error": "observe_failed",
            }
        researched["exploration_value_observation"] = kss13_bundle
        if round_details:
            round_details[-1]["exploration_value_observation"] = kss13_bundle
        # KSS-1.4: 情報喪失点 + Web answer presence（行動変更なし）
        kss14_bundle = {"enabled": False, "phase": "kss-1.4"}
        try:
            from tools.ai.state.information_loss import (
                kss14_obs_enabled,
                maybe_observe_information_loss_round,
            )
            from tools.ai.state.web_answer_presence import audit_round_answer_presence

            if kss14_obs_enabled():
                round_item = round_details[-1] if round_details else None
                kss14_bundle = maybe_observe_information_loss_round(
                    round_num=round_num,
                    kss13_bundle=kss13_bundle,
                    round_item=round_item,
                    case_id=os.environ.get("AI_AGENT_EXPERIMENT_CASE"),
                    research_run_id=os.environ.get("AI_AGENT_EXPERIMENT_ID"),
                )
                ans = audit_round_answer_presence(
                    request_text=str(result.get("request") or ""),
                    case_id=os.environ.get("AI_AGENT_EXPERIMENT_CASE"),
                    web_hit_partition=researched.get("web_hit_partition"),
                    round_item=round_item,
                    researched=researched,
                )
                kss14_bundle["web_answer_presence_audit"] = ans
        except Exception:
            kss14_bundle = {
                "enabled": False,
                "phase": "kss-1.4",
                "error": "observe_failed",
            }
        researched["information_loss_observation"] = kss14_bundle
        if round_details:
            round_details[-1]["information_loss_observation"] = kss14_bundle
        progress_log.append(
            {
                "round": round_num,
                "action": decision["action"],
                "reason": decision["reason"],
                "stagnation": stagnation,
                "has_new_finding": decision["has_new_finding"],
                "missing_same": decision["missing_same"],
                "duplicate_only": decision["duplicate_only"],
            }
        )
        seen_keys.update(round_keys)
        if decision["action"] == IMPLEMENT:
            result["research_sufficient"] = True
            result["research_stop_reason"] = decision["reason"]
            break
        usable = list(
            (researched.get("research") or {}).get("usable_findings") or []
        )
        research = mark_insufficient(
            research, usable, reason=judgment.get("reason")
        )
        if decision["action"] == STOP:
            result["research_stop_reason"] = decision["reason"]
            break
        next_handoff = prepare_followup_research(
            judgment.get("missing"),
            research,
            reason=judgment.get("reason"),
            state=state,
        )
        next_items = next_handoff["research_items"]
        if not next_items:
            next_items = items_from_missing(previous_missing or [])
            if next_items:
                next_handoff = prepare_followup_research(
                    previous_missing,
                    research,
                    reason=judgment.get("reason"),
                    state=state,
                )
        previous_missing = judgment.get("missing")
        if not next_items:
            result["research_stop_reason"] = "research_no_next_question"
            break

    result["pipeline"]["research"] = compact_research(
        research,
        extra={
            "rounds": result["research_rounds"],
            "stagnation": result["research_stagnation"],
            "stop_reason": result["research_stop_reason"],
            "candidates_error": (last_researched or {}).get("candidates_error"),
        },
    )
    result["pipeline"]["progress"] = progress_log
    result["pipeline"]["judgments"] = judgments
    result["pipeline"]["research_rounds_detail"] = round_details
    # KSS-1.3: run 終了後に final_pass 等を各 round へ付与（後で apply_checks 前は仮）
    try:
        from tools.ai.state.exploration_value import attach_run_outcomes

        if kss13_bundles:
            linked = attach_run_outcomes(
                kss13_bundles,
                final_pass=None,  # apply_checks 前 → analyzer / finalize で埋める
                fail_stage=result.get("fail_stage"),
                fail_reason=result.get("research_stop_reason"),
            )
            by_round = {b.get("round_index"): b for b in linked}
            for item in round_details:
                obs = by_round.get(item.get("round"))
                if obs:
                    item["exploration_value_observation"] = obs
            result["pipeline"]["exploration_value_rounds"] = linked
    except Exception:
        pass
    result["pipeline"]["research_history"] = state.research_history.snapshot()
    result["pipeline"]["global_judge_shadow"] = finalize_observation(
        global_judge_shadow,
        rounds=result.get("research_rounds"),
        baseline_rounds=None,
    )
    result["pipeline"]["context_budget_shadow"] = finalize_context_budget_shadow(
        context_budget_shadow
    )
    if not result["research_sufficient"]:
        result["error"] = result.get("research_stop_reason") or "research_insufficient"
    return research


def _update_proposal_from_research(proposal, research):
    """Research 成功後に proposal の未確認マーカーを解消する。"""
    usable = (research or {}).get("usable_findings") or []
    if not usable:
        return
    notes = []
    for f in usable:
        ev = f.get("evidence") or {}
        cmd = ev.get("command") or ""
        sample = ev.get("sample")
        if cmd:
            notes.append(f"取得方法確認済み: command={cmd}, sample={sample}")
    if notes:
        proposal["implementation_notes"] = notes
    deps = set()
    for f in usable:
        ev = f.get("evidence") or {}
        cmd = str(ev.get("command") or "")
        if cmd:
            deps.add(cmd)
    if deps:
        proposal["dependencies"] = sorted(deps)


def run_implementation(result, proposal, environment, research, state, tools, request):
    compact = compact_research(research)
    materials = create_tool_implementation(
        proposal,
        environment=environment,
        research_result=compact,
        request=request,
    )
    with stage("implementation"):
        payload, error, text, _detail = ask_json(
            build_implement_messages, materials, state=state
        )
    if isinstance(payload, dict):
        payload = prepare_code_payload(payload, proposal)
    record_phase(result, "implement", error=error, text=text, payload=payload)
    result["payload"] = payload
    result["diagnosis"] = diagnose_implement(error=error, text=text, payload=payload)
    result["implementation_class"] = classify_implementation(
        payload=payload,
        error=error,
        research_result=research,
    )
    result["pipeline"]["generated_code"] = (
        None if not isinstance(payload, dict) else payload.get("code")
    )
    if error:
        result["error"] = error
        return payload
    if not has_repair_code(payload):
        result["error"] = "no_code"
        return payload
    pre_val_snapshot = {
        "proposal_notes": list((proposal or {}).get("implementation_notes") or []),
        "proposal_deps": list((proposal or {}).get("dependencies") or []),
        "proposal_id": id(proposal),
    }
    with stage("validation"):
        impl_validation = validate_tool_implementation(
            proposal, payload, registry=tools, repair_mode=False
        )
    unim_check = (impl_validation.get("checks") or {}).get("unimplemented") or {}
    result["validation_1"] = {
        "result": impl_validation.get("result"),
        "errors": impl_validation.get("errors"),
        "warnings": impl_validation.get("warnings"),
        "code_len": len(str((payload or {}).get("code") or "")),
        "pre_val_snapshot": pre_val_snapshot,
        "check_unimplemented_detail": {
            "status": unim_check.get("status"),
            "errors": unim_check.get("errors"),
            "unimplemented_field": unim_check.get("unimplemented"),
        },
        "check_unimplemented_inputs": {
            "proposal_notes_at_check": list((proposal or {}).get("implementation_notes") or []),
            "has_unconfirmed": any("未確認" in str(n) for n in (proposal or {}).get("implementation_notes") or []),
            "code_has_stub": "未実装" in str((payload or {}).get("code") or ""),
            "payload_unimplemented": (payload or {}).get("unimplemented"),
        },
    }
    if impl_validation.get("result") != "OK":
        result["error"] = "impl_validation_ng"
        result["implementation_errors"] = impl_validation.get("errors")
        return payload
    registered = register_tool(proposal, payload, validation_result=impl_validation)
    result["registered"] = registered
    if registered.get("result") != "OK":
        result["error"] = "register_ng"
        return payload
    with stage("validation"):
        result["test_result"] = test_tool(proposal.get("name"))
    result["result_validation"] = validate_tool_result(
        proposal,
        result["test_result"],
        implementation=payload,
        research_result=research,
    )
    return payload


def run_once():
    resolved = _resolve_request()
    if resolved:
        request = resolved["request"]
        state = resolved["state"]
        if contains_forbidden_answer(request):
            raise RuntimeError("request に正解コマンドが含まれている")
        with Timing() as clock:
            result = _run_once(state, request)
            result["timing"] = clock.snapshot()
            result["state"] = state.persistence_snapshot()
            result["user_state"] = inspect_user_state(state)
            return result
    else:
        started = start_from_clarity_state(CREATE_REQUEST)
        state = started["state"]
        if contains_forbidden_answer(CREATE_REQUEST):
            raise RuntimeError("CREATE_REQUEST に正解コマンドが含まれている")
        if not started["user_state"]["ok"]:
            result = empty_result(CREATE_REQUEST, state)
            result["error"] = "clarity_state_missing"
            result["user_state"] = started["user_state"]
            return apply_checks(result)
        with Timing() as clock:
            result = _run_once(state, CREATE_REQUEST)
            result["timing"] = clock.snapshot()
            result["state"] = state.persistence_snapshot()
            result["user_state"] = inspect_user_state(state)
            return result


def _run_once(state, request=CREATE_REQUEST):
    result = empty_result(request, state)
    environment = verified_environment()
    tools = load_registry_tools()
    proposal = run_proposal(result, state, environment, tools, request)
    if proposal is None:
        return apply_checks(result)
    research = run_research_judge(result, proposal, environment, state, request)
    if not result.get("research_sufficient"):
        return apply_checks(result, research=research)
    _update_proposal_from_research(proposal, research)
    run_implementation(result, proposal, environment, research, state, tools, request)
    path = (result.get("registered") or {}).get("path")
    return apply_checks(
        result,
        research=research,
        classified=result.get("implementation_class"),
        path_exists=bool(path and os.path.exists(path)),
        in_registry=registry_has_tool(proposal.get("name")),
    )


def save_run(result):
    payload = load_json_file(
        RESULTS_PATH,
        {
            "note": "④ Researchで確定した方法を Implementation が Tool にできるか。Repair は見ない。",
            "benchmark": "python -m research.llm_benchmarks.research_implement",
            "runs": [],
        },
    )
    payload.setdefault("runs", [])
    checks = result.get("checks") or {}
    experiment = {}
    for key in (
        "AI_AGENT_EXPERIMENT_ID",
        "AI_AGENT_EXPERIMENT_CONDITION",
        "AI_AGENT_EXPERIMENT_TRIAL",
        "AI_AGENT_EXPERIMENT_CASE",
        "AI_AGENT_MEMORY_RECALL",
        "AI_AGENT_MEMORY_RECALL_VERSION",
        "AI_AGENT_MEMORY_JUDGE",
        "AI_AGENT_CONTEXT_ALLOC_LIVE",
        "AI_AGENT_CONTEXT_ALLOC_SHADOW",
        "AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP",
        "AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE",
        "AI_AGENT_KNOWLEDGE_SOURCE_OBS",
        "AI_AGENT_KSS1_OBS",
        "AI_AGENT_KSS11_OBS",
        "AI_AGENT_KSS12_OBS",
        "AI_AGENT_KSS13_OBS",
        "AI_AGENT_KSS14_OBS",
        "AI_AGENT_KSS15_OBS",
    ):
        val = os.environ.get(key)
        if val is not None and str(val).strip() != "":
            experiment[key] = val
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "profile": PROFILE_ID,
        "model": MODEL,
        "request": result.get("request"),
        "pass": result.get("ok"),
        "ok": result.get("ok"),
        "fail_stage": result.get("fail_stage"),
        "repaired": False,
        "repair": "skipped",
        "error": result.get("error"),
        "proposal_name": result.get("proposal_name"),
        "proposal": result.get("proposal"),
        "experiment": experiment or None,
        "knowledge_source_obs_enabled": os.environ.get("AI_AGENT_KNOWLEDGE_SOURCE_OBS"),
        "pipeline_stages": {
            key: {
                "ok": (result.get("pipeline_stages") or {})
                .get("stages", {})
                .get(key, {})
                .get("ok"),
                "label": label,
            }
            for key, label in PIPELINE_STAGE_LABELS
        },
        "pipeline_first_fail": (result.get("pipeline_stages") or {}).get(
            "first_fail"
        ),
        "checks": {
            key: {
                "ok": (checks.get(key) or {}).get("ok"),
                **{
                    field: (checks.get(key) or {}).get(field)
                    for field in (
                        "usable_count",
                        "satisfies_request",
                        "class",
                        "finding_adopted",
                        "command_from_findings",
                        "registered",
                        "structure",
                        "path_exists",
                        "in_registry",
                        "status",
                        "error",
                        "return_value",
                    )
                    if (checks.get(key) or {}).get(field) is not None
                },
            }
            for key in (
                "research_method",
                "judge_adopted",
                "code_generated",
                "code_matches",
                "registry",
                "runs",
            )
        },
        "implementation_class": result.get("implementation_class"),
        "implementation_errors": result.get("implementation_errors"),
        "validation_1": result.get("validation_1"),
        "result_validation": result.get("result_validation"),
        "diagnosis": result.get("diagnosis"),
        "pipeline": {
            "research": result.get("pipeline", {}).get("research"),
            "judgments": result.get("pipeline", {}).get("judgments"),
            "progress": result.get("pipeline", {}).get("progress"),
            "research_rounds_detail": result.get("pipeline", {}).get(
                "research_rounds_detail"
            ),
            "research_history": result.get("pipeline", {}).get("research_history"),
            "global_judge_shadow": result.get("pipeline", {}).get("global_judge_shadow"),
            "context_budget_shadow": result.get("pipeline", {}).get(
                "context_budget_shadow"
            ),
            "generated_code": result.get("pipeline", {}).get("generated_code"),
            "repair": "skipped",
        },
        "user_state": result.get("user_state"),
        "state": result.get("state"),
        "timing": result.get("timing"),
        "trace": [
            {
                "phase": item.get("phase"),
                "error": item.get("error"),
                "parsed": item.get("parsed"),
            }
            for item in result.get("trace") or []
        ],
    }
    payload["runs"].append(entry)
    save_json_file(RESULTS_PATH, payload)
    if not result.get("ok"):
        failures = load_json_file(
            FAILURES_PATH,
            {
                "note": "④ の失敗。fail_stage は research / judge / implementation。",
                "entries": [],
            },
        )
        failures.setdefault("entries", [])
        failures["entries"].append(entry)
        save_json_file(FAILURES_PATH, failures)


def print_result(result):
    checks = result.get("checks") or {}
    stages = (result.get("pipeline_stages") or {}).get("stages") or {}
    mark = "PASS" if result.get("ok") else "FAIL"
    print(
        f"{mark}  create-tool  profile={PROFILE_ID}  model={MODEL}  "
        f"fail_stage={result.get('fail_stage')}  repair=skipped"
    )
    print("  pipeline:")
    for key, label in PIPELINE_STAGE_LABELS:
        item = stages.get(key) or {}
        stage_mark = "ok" if item.get("ok") else "--"
        print(f"    {label}: {stage_mark}")
    print(
        "  legacy: research={research}  judge={judge}  code={code}  "
        "match={match}  registry={registry}  runs={runs}".format(
            research=(checks.get("research_method") or {}).get("ok"),
            judge=(checks.get("judge_adopted") or {}).get("ok"),
            code=(checks.get("code_generated") or {}).get("ok"),
            match=(checks.get("code_matches") or {}).get("ok"),
            registry=(checks.get("registry") or {}).get("ok"),
            runs=(checks.get("runs") or {}).get("ok"),
        )
    )
    for item in result.get("pipeline", {}).get("research_rounds_detail") or []:
        print(
            "  round[{round}]: candidates={candidate_count} "
            "verified={verified_count} verify_fail={verifier_failure} "
            "judge={judge_grade} satisfies={satisfies_request}".format(**item)
        )
        research_input = item.get("research_input") or {}
        if research_input.get("followup_questions"):
            print(
                "    followup_questions: {qs}".format(
                    qs=research_input.get("followup_questions")
                )
            )
        if research_input.get("rejected_commands"):
            print(
                "    rejected_commands: {count}".format(
                    count=len(research_input.get("rejected_commands") or [])
                )
            )
        if item.get("missing"):
            print(f"    missing: {item.get('missing')}")
    for item in result.get("pipeline", {}).get("progress") or []:
        print(
            "  progress[{round}]: {action} {reason} stag={stagnation}".format(
                **item
            )
        )
    for item in result.get("pipeline", {}).get("judgments") or []:
        print(
            "  judge[{round}]: satisfies={satisfies_request} "
            "missing={missing} reason={reason}".format(**item)
        )
    impl_class = (result.get("implementation_class") or {}).get("class")
    if impl_class:
        print(f"  implementation: {impl_class}")
    if result.get("error"):
        print(f"  error: {result['error']}")
    runs = checks.get("runs") or {}
    if runs.get("return_value") is not None or runs.get("error"):
        print(f"  value={runs.get('return_value')}  run_error={runs.get('error')}")
    timing = result.get("timing") or {}
    if timing:
        print(
            "  timing: total={total_seconds}s research={research_seconds}s "
            "judge={judge_seconds}s implementation={implementation_seconds}s".format(
                total_seconds=timing.get("total_seconds"),
                research_seconds=timing.get("research_seconds"),
                judge_seconds=timing.get("judge_seconds"),
                implementation_seconds=timing.get("implementation_seconds"),
            )
        )


def main():
    # Actor Identity: Research/Judge 経路は PROJECT_AGENT とは別主体
    log_run_start(
        execution_actor=RESEARCH_PIPELINE,
        entrypoint="research.llm_benchmarks.research_implement",
        llm=MODEL,
        extra={
            "event": "pipeline_start",
            "profile": PROFILE_ID,
            "repeat": REPEAT,
        },
    )
    print(
        f"create-tool  repeat={REPEAT}  profile={PROFILE_ID}  model={MODEL}"
    )
    effective_request = (_resolve_request() or {}).get("request", CREATE_REQUEST)
    print(f"request={effective_request}")
    files, registry = snapshot_system_tools()
    passed = []
    try:
        for index in range(1, REPEAT + 1):
            result = run_once()
            save_run(result)
            print(f"trial {index}/{REPEAT}")
            print_result(result)
            passed.append(bool(result.get("ok")))
        return 0 if REPEAT == 0 else (0 if all(passed) and passed else 1)
    except Exception as exc:
        print(f"NG  {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 1
    finally:
        restore_system_tools(files, registry)
        stop_model(MODEL)


if __name__ == "__main__":
    raise SystemExit(main())
