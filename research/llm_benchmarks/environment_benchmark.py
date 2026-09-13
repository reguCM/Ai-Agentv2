"""
環境調査ベンチ。unittest ではない。

ユーザー要求だけを渡し、正解コマンドは教えない。
research → 要求充足の判断 → 足りなければ再調査 → 実装 → Validator、までを測る。
"""

import json
import os
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

from tools.ai.llm.adapter import (
    build_implement_messages,
    build_proposal_messages,
    build_repair_messages,
    build_research_judge_messages,
    build_web_candidate_messages,
    exploration_retry_extra,
    retry_extra,
    validation_extra,
)
from tools.ai.tool_builder.implementation import create_tool_implementation
from tools.ai.tool_builder.proposal import PROJECT_CONVENTIONS, create_tool_proposal
from tools.ai.tool_builder.repair import repair_tool
from tools.ai.tool_builder.research import research_tool
from tools.ai.tool_builder.research_judge import (
    create_research_judgment,
    items_from_missing,
    normalize_judgment,
    prepare_followup_research,
)
from tools.ai.state.decision_store import apply_judgment, extra_keys_from_proposal
from tools.ai.state.state_sync import sync_research_into_state
from tools.ai.state.rule_partial import apply_rule_partial
from tools.ai.state.global_judge_trigger import (
    evaluate_global_judge_trigger,
    execute_global_judge_round,
    finalize_observation,
    init_shadow_summary,
    record_shadow_round,
)
from tools.ai.state.task_state import TaskState
from tools.ai.tool_builder.research_result import (
    filter_rejected_candidates,
    mark_insufficient,
    merge_packed_research,
    rejected_command_list,
    research_result as pack_research_result,
)
from tools.ai.tool_builder.web import exploration_retry_needed, web_research
from tools.ai.llm.context_budget import check_context_budget
from tools.ai.llm.context_allocation import (
    BUILDER_JUDGE,
    BUILDER_WEB,
    context_alloc_live_enabled,
    finalize_context_budget_shadow,
    init_context_budget_shadow,
    prepare_context_allocation_call,
)
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.timing import Timing, stage
from tools.system.tool_builder.apply import apply_repair, has_repair_code
from tools.system.tool_builder.implementation_classify import classify_implementation
from tools.system.tool_builder.register import register_tool
from tools.system.tool_builder.research.executor import research_executor
from tools.system.tool_builder.research.local import collect_local_inventory
from tools.system.tool_builder.research.progress import (
    IMPLEMENT,
    STOP,
    evaluate_research_progress,
    finding_keys,
)
from tools.system.tool_builder.research.verify import (
    merge_research_results,
    research_verifier,
)
from tools.system.tool_builder.test import test_tool
from tools.system.tool_builder.validate.implementation import (
    validate_tool_implementation,
)
from tools.system.tool_builder.validate.research import research_result_validator
from tools.system.tool_builder.validate.result import validate_tool_result
from tools.system.tool_builder.validate.spec import validate_tool_spec
from tools.system.tool_builder.validate.warning_actions import first_pipeline_step


PROFILE = get_llm_profile()
PIPELINE = get_pipeline()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
MAX_REPAIR_ROUNDS = int(PIPELINE.get("max_repair_rounds") or 3)
MAX_RESEARCH_ROUNDS = int(PIPELINE.get("max_research_rounds") or 10)
MAX_RESEARCH_STAGNATION = int(PIPELINE.get("max_research_stagnation") or 3)

USER_REQUEST = "Windowsのメモリ使用率を取得するToolを追加してください"

FORBIDDEN_ANSWERS = (
    "Win32_OperatingSystem",
    "FreePhysicalMemory",
    "TotalVisibleMemorySize",
)

REGISTRY_PATH = "registry/tools.json"
SYSTEM_ROOT = Path("tools/system")
BENCHMARK_DIR = "research/llm_benchmarks"
RESULTS_PATH = f"{BENCHMARK_DIR}/environment_results.json"
FAILURES_PATH = f"{BENCHMARK_DIR}/environment_failures.json"


def extract_json_object(text):
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(stripped[start : end + 1])
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def contains_forbidden_answer(text):
    lowered = str(text or "")
    return any(token in lowered for token in FORBIDDEN_ANSWERS)


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def snapshot_system_tools():
    files = {}
    for path in SYSTEM_ROOT.rglob("*.py"):
        files[str(path).replace("\\", "/")] = path.read_text(encoding="utf-8")
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = f.read()
    return files, registry


def restore_system_tools(files, registry):
    current = {
        str(path).replace("\\", "/")
        for path in SYSTEM_ROOT.rglob("*.py")
    }
    for path, text in files.items():
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")
    for path in current:
        if path not in files:
            Path(path).unlink(missing_ok=True)
    for directory in sorted(SYSTEM_ROOT.rglob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        f.write(registry)


def ask_llm(messages, *, builder_name=None, measurement=None):
    reserve_headroom = context_alloc_live_enabled() and builder_name in (
        BUILDER_WEB,
        BUILDER_JUDGE,
    )
    overflow = check_context_budget(
        messages,
        PROFILE,
        builder_name=builder_name,
        reserve_headroom=reserve_headroom,
    )
    if overflow:
        if measurement:
            overflow["context_allocation"] = measurement
        return "", None, overflow
    try:
        response = chat(model=MODEL, messages=messages)
    except LLMTimeoutError as exc:
        return "", None, str(exc)
    text = response.message.content
    return text, extract_json_object(text), None


def _send_error_result(send_error):
    if isinstance(send_error, dict) and send_error.get("kind") == "context_overflow":
        return None, "context_overflow", "", send_error
    if send_error:
        return None, "timeout", "", send_error
    return None


def ask_json(builder, materials, extra=None, state=None):
    builder_name = getattr(builder, "__name__", None)
    measurement = None
    if builder_name in (BUILDER_WEB, BUILDER_JUDGE):
        prepared = prepare_context_allocation_call(
            builder, materials, state=state, extra=extra, profile=PROFILE
        )
        measurement = prepared.get("measurement") or {}
        messages = prepared.get("messages")
        if messages is None:
            detail = {
                "kind": "context_overflow",
                "builder": builder_name,
                "overflow_action": "defer",
                "context_allocation": measurement,
            }
            return None, "context_overflow", "", detail
    else:
        messages = builder(materials, extra=extra, state=state)
    text, payload, send_error = ask_llm(
        messages, builder_name=builder_name, measurement=measurement
    )
    blocked = _send_error_result(send_error)
    if blocked:
        return blocked
    if payload is None:
        text, payload, send_error = ask_llm(
            builder(materials, extra=retry_extra(), state=state),
            builder_name=builder_name,
            measurement=measurement,
        )
        blocked = _send_error_result(send_error)
        if blocked:
            return blocked
    if payload is None:
        return None, "no_json", text, None
    return payload, None, text, None


def verified_environment():
    import platform
    import sys

    return {
        "language": "python",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "python_full_version": sys.version.split()[0],
        "platform": platform.system().lower(),
        "architecture": platform.machine(),
    }


def load_registry_tools():
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("tools") or []


def is_usable_memory_usage(return_value):
    if not isinstance(return_value, dict):
        return False
    status = return_value.get("status")
    if status is None:
        return False
    text = str(status).strip().rstrip("%")
    if text in ("", "error", "未実装"):
        return False
    if "LoadPercentage" in text or "Memory" in text or "---" in text:
        return False
    try:
        number = float(text)
    except ValueError:
        return False
    return 0 <= number <= 100


def warning_codes(validation, key):
    return [
        item.get("code")
        for item in (validation.get("disposition") or {}).get(key) or []
    ]


def prepare_code_payload(payload, proposal):
    payload = dict(payload or {})
    payload["path"] = str(proposal.get("module") or "").replace(".", "/") + ".py"
    payload["function"] = proposal.get("function") or payload.get("function")
    unimplemented = payload.get("unimplemented")
    if unimplemented is None:
        payload["unimplemented"] = []
    elif not isinstance(unimplemented, list):
        payload["unimplemented"] = [unimplemented]
    notes = payload.get("notes")
    if notes is None:
        payload["notes"] = []
    elif not isinstance(notes, list):
        payload["notes"] = [notes]
    return payload


def slim_llm_payload(payload):
    if payload is None:
        return None
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__, "value": payload}
    code = payload.get("code")
    return {
        "keys": list(payload.keys()),
        "path": payload.get("path"),
        "function": payload.get("function"),
        "unimplemented": payload.get("unimplemented"),
        "notes": payload.get("notes"),
        "code_present": bool(code and str(code).strip()),
        "code_chars": len(str(code or "")),
        "candidates": payload.get("candidates"),
        "satisfies_request": payload.get("satisfies_request"),
        "reason": payload.get("reason"),
        "missing": payload.get("missing"),
        "proposal_names": [
            item.get("name")
            for item in payload.get("proposals") or []
            if isinstance(item, dict)
        ],
    }


def looks_like_python(text):
    if not text:
        return False
    return any(token in text for token in ("def ", "import ", "return {", "subprocess"))


def diagnose_implement(*, error, text, payload):
    parsed = isinstance(payload, dict)
    code = str(payload.get("code") or "") if parsed else ""
    alt_code = ""
    if parsed:
        for key in ("source", "implementation", "python", "content"):
            value = payload.get(key)
            if value and str(value).strip():
                alt_code = str(value)
                break
    python_in_text = looks_like_python(text)
    unimplemented = payload.get("unimplemented") if parsed else None
    notes = payload.get("notes") if parsed else None
    if error == "timeout":
        kind = "timeout"
    elif error == "no_json":
        kind = (
            "pipeline_did_not_receive_code"
            if python_in_text
            else "llm_did_not_return_json"
        )
    elif parsed and not str(code).strip():
        if alt_code:
            kind = "pipeline_did_not_receive_code"
        elif unimplemented:
            kind = "llm_marked_unimplemented"
        else:
            kind = "llm_returned_empty_code"
    elif str(code).strip():
        kind = "code_received"
    else:
        kind = "unknown"
    return {
        "kind": kind,
        "json_parsed": parsed,
        "code_present": bool(str(code).strip()),
        "python_in_llm_text": python_in_text,
        "parsed_keys": list(payload.keys()) if parsed else [],
        "unimplemented": unimplemented,
        "notes": notes,
        "error": error,
    }


def record_phase(result, phase, *, error=None, text=None, payload=None, extra=None):
    entry = {
        "phase": phase,
        "error": error,
        "parsed": slim_llm_payload(payload) if payload is not None else None,
        "llm_text_chars": len(text or ""),
        "generated_code": (
            (payload or {}).get("code") if isinstance(payload, dict) else None
        ),
    }
    if extra:
        entry.update(extra)
    result.setdefault("trace", []).append(entry)
    return entry


def compact_research(research, extra=None):
    payload = {
        "usable_findings": (research or {}).get("usable_findings") or [],
        "reference_findings": (research or {}).get("reference_findings") or [],
        "unresolved": (research or {}).get("unresolved") or [],
        "insufficient_findings": (research or {}).get("insufficient_findings") or [],
    }
    if extra:
        payload.update(extra)
    return payload


def _web_hits_for_obs(hits):
    """KSS-1.2: hit_score を観測用に付与。候補採否・実行は変えない。"""
    try:
        from tools.ai.state.web_decision_link import (
            annotate_hits_with_scores,
            kss12_obs_enabled,
        )
    except Exception:
        annotate_hits_with_scores = None
        kss12_obs_enabled = lambda: False  # noqa: E731
    scored = []
    if kss12_obs_enabled() and annotate_hits_with_scores is not None:
        scored = annotate_hits_with_scores(hits or [])
    else:
        scored = list(hits or [])
    out = []
    for hit in scored[:8]:
        if not isinstance(hit, dict):
            continue
        item = {
            "title": hit.get("title"),
            "snippet": hit.get("snippet"),
            "url": hit.get("url"),
            "backend": hit.get("backend"),
        }
        if "score" in hit and hit.get("score") is not None:
            item["score"] = hit.get("score")
        out.append(item)
    return out


def _web_decision_link_obs(candidates, hits):
    try:
        from tools.ai.state.web_decision_link import maybe_link_web_to_decisions

        return maybe_link_web_to_decisions(candidates, hits)
    except Exception:
        return {"enabled": False, "phase": "kss-1.2", "error": "observe_failed"}


def _web_hit_partition_obs(web_exec, hits, *, candidates=None, web_decision_link=None):
    """KSS-1.5: live kept/dropped 詳細保存。filter ロジックは変更しない。"""
    try:
        from tools.ai.state.web_hit_partition import (
            attach_candidate_links,
            enrich_partition_with_heuristic,
            kss15_obs_enabled,
            merge_web_exec_partitions,
        )

        if not (
            kss15_obs_enabled()
            or os.environ.get("AI_AGENT_KSS14_OBS")
            or os.environ.get("AI_AGENT_KSS15_OBS")
        ):
            # fall back to kss-1.4 compact partition
            from tools.ai.state.web_answer_presence import (
                collect_hit_partition_from_web_exec,
                kss14_answer_audit_enabled,
            )

            if not kss14_answer_audit_enabled():
                return None
            return collect_hit_partition_from_web_exec(web_exec)

        part = merge_web_exec_partitions(web_exec)
        part = attach_candidate_links(
            part, candidates=candidates, web_decision_link=web_decision_link
        )
        case_id = os.environ.get("AI_AGENT_EXPERIMENT_CASE")
        part = enrich_partition_with_heuristic(
            part, request_text="", case_id=case_id
        )
        return part
    except Exception:
        return {
            "source": "error",
            "kept_hits": "missing",
            "dropped_hits": "missing",
            "records": "missing",
        }


def run_research(
    proposal,
    environment,
    *,
    items=None,
    rejected_commands=None,
    prior_failures=None,
    judge_reason=None,
    state=None,
    user_request=None,
    searched_queries=None,
    search_intent=None,
):
    from tools.system.tool_builder.research import query_intent as qi

    tool_name = proposal.get("name")
    subject = {
        "tool_name": tool_name,
        "subcategory": proposal.get("subcategory"),
    }
    followup_questions = []
    if items:
        items_payload = {
            "research_items": items,
            "subject": subject,
        }
        followup_questions = [
            str(item.get("question") or "").strip()
            for item in items
            if item.get("followup") and str(item.get("question") or "").strip()
        ]
    else:
        request = {
            "reason": "取得方法が未確認",
            "required_information": [
                f"output '{key}' の取得方法"
                for key in (proposal.get("output") or ["status"])
            ],
            "codes": ["unconfirmed_fetch"],
        }
        items_payload = research_tool(
            research_request=request, proposal=proposal, tool_name=tool_name
        )
        subject = items_payload.get("subject") or subject
    research_items = items_payload.get("research_items") or []
    request_text = qi.resolve_user_request(user_request, state=state)
    intent = search_intent
    if not isinstance(intent, dict) or not intent:
        if request_text:
            intent = qi.extract_search_intent(
                request_text,
                subject=subject,
                state=state,
                proposal=proposal,
            )
    local_exec = research_executor(
        research_items=research_items,
        subject=subject,
        source="local",
    )
    web_exec = research_executor(
        research_items=research_items,
        subject=subject,
        source="web",
        user_request=request_text,
        search_intent=intent,
        searched_queries=searched_queries,
    )
    intent = web_exec.get("search_intent") or intent
    searched_after = list(web_exec.get("searched_queries") or searched_queries or [])
    inventory = collect_local_inventory(proposal.get("subcategory"))
    hits = []
    for item in web_exec.get("results") or []:
        hits.extend(item.get("hits") or [])
    search_keywords = list(qi.intent_filter_keywords(intent))
    if followup_questions:
        for question in followup_questions:
            gap = qi.clean_missing_gap(question)
            if gap:
                search_keywords.append(gap)
    web_materials = web_research(
        items=research_items,
        search_results=hits,
        inventory=inventory,
        subject=subject,
        environment=environment,
        rejected_commands=rejected_commands or [],
        followup_questions=followup_questions,
        prior_failures=prior_failures or [],
        judge_reason=judge_reason or "",
        search_keywords=search_keywords,
        state=state,
    )
    candidates_payload, error, text, detail = ask_json(
        build_web_candidate_messages, web_materials, state=state
    )
    candidates = []
    if not error and isinstance(candidates_payload, dict):
        candidates = candidates_payload.get("candidates") or []
    if error != "context_overflow" and exploration_retry_needed(web_materials, candidates):
        candidates_payload, error, text, detail = ask_json(
            build_web_candidate_messages,
            web_materials,
            extra=exploration_retry_extra(web_materials),
            state=state,
        )
        candidates = []
        if not error and isinstance(candidates_payload, dict):
            candidates = candidates_payload.get("candidates") or []
    # KSS-1: 観測抽出後、実行経路からは observation を剥がす（行動不変）
    kss1_obs = {"enabled": False, "phase": "kss-1"}
    candidates_before_filter = list(candidates or [])
    try:
        from tools.ai.state.decision_confidence import (
            kss1_obs_enabled,
            observe_candidate_decision_payload,
            strip_observation_fields,
        )

        if kss1_obs_enabled() and isinstance(candidates_payload, dict):
            kss1_obs = observe_candidate_decision_payload(
                candidates_payload, candidates, round_num=None
            )
            candidates = strip_observation_fields(candidates)
            candidates_before_filter = list(candidates or [])
    except Exception:
        kss1_obs = {"enabled": False, "phase": "kss-1", "error": "observe_failed"}
    candidates = filter_rejected_candidates(
        candidates,
        rejected_commands,
        banned_actions=getattr(state, "banned_actions", None) if state else None,
    )
    candidate_filter_stats = {
        "before": len(candidates_before_filter),
        "after": len(candidates or []),
        "rejected": len(candidates_before_filter) - len(candidates or []),
    }
    verified = research_verifier(
        candidates=candidates,
        items=research_items,
        inventory=inventory,
    )
    merged = merge_research_results(
        local_exec.get("results") or [],
        verified.get("results") or [],
        subject=subject,
    )
    packed_validation = research_result_validator(
        merged, research_items
    )
    if packed_validation.get("result") != "OK":
        packed_validation = {"result": "OK", "status": "warning"}
    research = pack_research_result(merged, packed_validation)
    kss_obs = None
    try:
        from tools.ai.state.knowledge_source import maybe_observe_research_round

        kss_obs = maybe_observe_research_round(
            state,
            hits=hits,
            candidates=candidates,
            verified=verified,
            goal_text=str((proposal or {}).get("name") or ""),
            round_num=None,
        )
    except Exception:
        kss_obs = {"enabled": False, "error": "observe_failed"}
    # KSS-1.3: filter 前後件数の観測のみ（採否ロジックは変更しない）
    web_exec_stats = None
    try:
        from tools.ai.state.exploration_value import (
            collect_web_search_stats,
            kss13_obs_enabled,
        )

        if kss13_obs_enabled() or os.environ.get("AI_AGENT_KSS11_OBS"):
            web_exec_stats = collect_web_search_stats(
                web_exec=web_exec, web_hits=hits
            )
    except Exception:
        web_exec_stats = None
    web_link = _web_decision_link_obs(candidates, hits)
    return {
        "research": research,
        "items": research_items,
        "followup_questions": followup_questions,
        "local": local_exec,
        "candidates_error": error,
        "candidates_text": text,
        "candidates_payload": candidates_payload,
        "candidates_detail": detail,
        "candidates": candidates,
        "verified": verified,
        "web_hits": _web_hits_for_obs(hits),
        "web_decision_link": web_link,
        "web_hit_partition": _web_hit_partition_obs(
            web_exec,
            hits,
            candidates=candidates,
            web_decision_link=web_link,
        ),
        "web_exec_stats": web_exec_stats,
        "knowledge_source_observation": kss_obs,
        "decision_confidence_observation": kss1_obs,
        "candidate_filter_stats": candidate_filter_stats,
        "searched_queries": searched_after,
        "search_intent": intent,
        "user_request": request_text or None,
    }


def command_used_from_findings(source, research):
    if not source or not research:
        return False
    for item in research.get("usable_findings") or []:
        evidence = item.get("evidence") or {}
        command = str(evidence.get("command") or "")
        args = evidence.get("args") or []
        if command and command in source:
            return True
        for arg in args:
            if str(arg) and str(arg) in source:
                return True
    return False


def run_once():
    with Timing() as clock:
        state = TaskState(task=USER_REQUEST)
        result = _run_once(state)
        result["state"] = state.snapshot()
        result["timing"] = clock.snapshot()
        return result


def _run_once(state):
    result = {
        "ok": False,
        "request": USER_REQUEST,
        "did_research": False,
        "did_research_again": False,
        "research_rounds": 0,
        "research_sufficient": False,
        "research_stagnation": 0,
        "research_stop_reason": None,
        "usable_findings": False,
        "command_from_findings": False,
        "structure_ok": False,
        "formatted_ok": False,
        "validator_pass": False,
        "repaired": False,
        "step_after": None,
        "codes_after": [],
        "return_value": None,
        "proposal_name": None,
        "error": None,
        "diagnosis": None,
        "implementation_class": None,
        "trace": [],
        "pipeline": {
            "request": USER_REQUEST,
            "research": None,
            "judgments": [],
            "progress": [],
            "implement_decision": None,
            "generated_code": None,
            "llm_text": None,
            "diagnosis": None,
            "implementation_class": None,
        },
    }
    environment = verified_environment()
    tools = load_registry_tools()
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

    proposal_materials = create_tool_proposal(
        USER_REQUEST,
        project_spec=PROJECT_CONVENTIONS,
        registry=registry_summary,
        environment=environment,
    )
    proposal_materials["structure_hint"] = {
        "module_pattern": "tools.<category>.<subcategory>.<filename>",
        "return_shape": {"status": "値"},
        "note": "参考は配置と戻り値の形だけ。取得コマンドはここにない。",
    }
    payload, error, text, detail = ask_json(
        build_proposal_messages, proposal_materials, state=state
    )
    record_phase(result, "proposal", error=error, text=text, payload=payload)
    if error:
        result["error"] = error
        return result

    proposals = payload.get("proposals") if isinstance(payload, dict) else None
    if not isinstance(proposals, list) or not proposals:
        result["error"] = "no_proposal"
        result["llm_text"] = text
        return result
    proposal = proposals[0]
    spec = validate_tool_spec(proposal, environment, request=USER_REQUEST, existing_tools=tools)
    if spec.get("status") == "fail":
        payload, error, text, detail = ask_json(
            build_proposal_messages,
            proposal_materials,
            extra=validation_extra(spec.get("errors")),
            state=state,
        )
        record_phase(result, "proposal_retry", error=error, text=text, payload=payload)
        if error or not payload or not payload.get("proposals"):
            result["error"] = "proposal_validation_ng"
            result["spec_errors"] = spec.get("errors")
            return result
        proposal = payload["proposals"][0]
        spec = validate_tool_spec(
            proposal, environment, request=USER_REQUEST, existing_tools=tools
        )
        if spec.get("status") == "fail":
            result["error"] = "proposal_validation_ng"
            result["spec_errors"] = spec.get("errors")
            return result

    result["proposal_name"] = proposal.get("name")
    result["structure_ok"] = bool(
        str(proposal.get("module") or "").startswith("tools.system.")
        and proposal.get("output") == ["status"]
    )

    research = {}
    next_items = None
    next_handoff = None
    judgments = []
    progress_log = []
    last_researched = None
    seen_keys = set()
    previous_missing = None
    stagnation = 0
    searched_queries = []
    search_intent = None
    global_judge_shadow = init_shadow_summary()
    context_budget_shadow = init_context_budget_shadow()
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
        result["did_research"] = True
        result["research_rounds"] = round_num
        if round_num > 1:
            result["did_research_again"] = True
            research = merge_packed_research(research, researched["research"])
        else:
            research = researched["research"]
        round_keys = finding_keys(
            (researched.get("research") or {}).get("usable_findings")
        )
        record_phase(
            result,
            f"research_{round_num}",
            error=researched["candidates_error"],
            text=researched["candidates_text"],
            payload=researched["candidates_payload"],
            extra={"web_hit_count": len(researched["web_hits"] or [])},
        )
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
        judge_materials = create_research_judgment(
            USER_REQUEST, proposal, research, state=state
        )

        def _run_llm_judge():
            with stage("judge"):
                payload, error, text, detail = ask_json(
                    build_research_judge_messages, judge_materials, state=state
                )
            judgment = normalize_judgment(payload)
            if error:
                judgment["error"] = error
            return {
                "payload": payload,
                "error": error,
                "text": text,
                "detail": detail,
                "judgment": judgment,
                "judge_held": {},
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

        if gj_result.get("live_skipped") or gj_result.get("audit_only"):
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
        global_judge_shadow = record_shadow_round(
            global_judge_shadow,
            {
                "round": round_num,
                **gj_trigger,
                "llm_called": gj_result.get("llm_called"),
                "live_skipped": gj_result.get("live_skipped"),
                "audit_only": gj_result.get("audit_only"),
                "quality_compare": gj_result.get("quality_compare"),
                "shadow_judgment": gj_result.get("shadow_judgment"),
                "audit_judgment": gj_result.get("audit_judgment"),
            },
        )
        judgments.append(
            {
                "round": round_num,
                **judgment,
                "llm_text": text,
            }
        )
        record_phase(
            result,
            f"research_judge_{round_num}",
            error=error,
            text=text,
            payload=payload,
            extra={
                "judgment": judgment,
                "global_judge_trigger": gj_trigger,
                "live_skipped": gj_result.get("live_skipped"),
                "audit_only": gj_result.get("audit_only"),
                "rule_partial": {
                    "escalation": rule_partial.get("escalation"),
                    "applied_ops": [
                        p.get("op") for p in (rule_partial.get("applied") or [])
                    ],
                },
            },
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
        record_phase(
            result,
            f"research_progress_{round_num}",
            extra={"progress": progress_log[-1]},
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

    result["usable_findings"] = bool(research.get("usable_findings"))
    result["pipeline"]["research"] = compact_research(
        research,
        extra={
            "items": (last_researched or {}).get("items") or [],
            "web_hit_count": len((last_researched or {}).get("web_hits") or []),
            "web_hits": (last_researched or {}).get("web_hits") or [],
            "candidates": (last_researched or {}).get("candidates") or [],
            "candidates_error": (last_researched or {}).get("candidates_error"),
            "verified": ((last_researched or {}).get("verified") or {}).get(
                "results"
            )
            or [],
            "rounds": result["research_rounds"],
            "stagnation": result["research_stagnation"],
            "stop_reason": result["research_stop_reason"],
        },
    )
    result["pipeline"]["progress"] = progress_log
    result["pipeline"]["judgments"] = [
        {
            "round": item.get("round"),
            "satisfies_request": item.get("satisfies_request"),
            "reason": item.get("reason"),
            "missing": item.get("missing"),
            "error": item.get("error"),
            "proposed_decisions": item.get("proposed_decisions") or [],
        }
        for item in judgments
    ]
    result["pipeline"]["global_judge_shadow"] = finalize_observation(
        global_judge_shadow,
        rounds=result.get("research_rounds"),
        baseline_rounds=None,
    )
    result["pipeline"]["context_budget_shadow"] = finalize_context_budget_shadow(
        context_budget_shadow
    )

    if not result["research_sufficient"]:
        result["usable_findings"] = bool(research.get("usable_findings"))
        result["error"] = result.get("research_stop_reason") or "research_insufficient"
        result["diagnosis"] = {
            "kind": "research_stopped",
            "reason": result["error"],
            "stagnation": result["research_stagnation"],
            "rounds": result["research_rounds"],
        }
        result["pipeline"]["diagnosis"] = result["diagnosis"]
        return result

    impl_materials = create_tool_implementation(
        proposal,
        environment=environment,
        research_result=research,
    )
    with stage("implementation"):
        payload, error, text, detail = ask_json(
            build_implement_messages, impl_materials, state=state
        )
    if isinstance(payload, dict):
        payload = prepare_code_payload(payload, proposal)
    record_phase(result, "implement", error=error, text=text, payload=payload)
    result["diagnosis"] = diagnose_implement(error=error, text=text, payload=payload)
    result["implementation_class"] = classify_implementation(
        payload=payload,
        error=error,
        research_result=research,
    )
    result["pipeline"]["implement_decision"] = slim_llm_payload(payload)
    result["pipeline"]["generated_code"] = (
        (payload or {}).get("code") if isinstance(payload, dict) else None
    )
    result["pipeline"]["llm_text"] = text
    result["pipeline"]["diagnosis"] = result["diagnosis"]
    result["pipeline"]["implementation_class"] = result["implementation_class"]
    if error:
        result["error"] = error
        return result
    if not has_repair_code(payload):
        result["error"] = "no_code"
        return result
    with stage("validation"):
        impl_validation = validate_tool_implementation(
            proposal, payload, registry=tools, repair_mode=False
        )
    if impl_validation.get("result") != "OK":
        with stage("implementation"):
            payload, error, text, detail = ask_json(
                build_implement_messages,
                impl_materials,
                extra=validation_extra(impl_validation.get("errors")),
                state=state,
            )
        if isinstance(payload, dict):
            payload = prepare_code_payload(payload, proposal)
        record_phase(
            result, "implement_retry", error=error, text=text, payload=payload
        )
        result["diagnosis"] = diagnose_implement(
            error=error, text=text, payload=payload
        )
        result["implementation_class"] = classify_implementation(
            payload=payload,
            error=error,
            research_result=research,
        )
        result["pipeline"]["implement_decision"] = slim_llm_payload(payload)
        result["pipeline"]["generated_code"] = (
            (payload or {}).get("code") if isinstance(payload, dict) else None
        )
        result["pipeline"]["llm_text"] = text
        result["pipeline"]["diagnosis"] = result["diagnosis"]
        result["pipeline"]["implementation_class"] = result["implementation_class"]
        if error:
            result["error"] = error
            return result
        with stage("validation"):
            impl_validation = validate_tool_implementation(
                proposal, payload, registry=tools, repair_mode=False
            )
        if impl_validation.get("result") != "OK":
            result["error"] = "impl_validation_ng"
            result["implementation_errors"] = impl_validation.get("errors")
            return result

    registered = register_tool(proposal, payload, validation_result=impl_validation)
    if registered.get("result") != "OK":
        result["error"] = "register_ng"
        result["register_errors"] = registered.get("errors")
        return result

    tool_name = proposal.get("name")
    source_path = payload.get("path")
    current_source = Path(source_path).read_text(encoding="utf-8") if source_path else ""
    with stage("validation"):
        test_result = test_tool(tool_name)
        validation = validate_tool_result(
            proposal, test_result, research_result=research, source=current_source
        )
        step = first_pipeline_step(validation)

    for round_num in range(1, MAX_REPAIR_ROUNDS + 1):
        if step == "pass":
            break
        if step not in ("repair", "research_repair"):
            break
        result["repaired"] = True
        with stage("repair"):
            materials = repair_tool(
                tool_name,
                proposal,
                {},
                test_result,
                validation,
                research_result=research,
            )
            payload, error, text, detail = ask_json(
                build_repair_messages, materials, state=state
            )
        record_phase(result, f"repair_{round_num}", error=error, text=text, payload=payload)
        if error:
            result["error"] = error
            break
        payload = prepare_code_payload(payload, proposal)
        if not has_repair_code(payload):
            continue
        with stage("validation"):
            impl_validation = validate_tool_implementation(
                proposal, payload, registry=load_registry_tools(), repair_mode=True
            )
        if impl_validation.get("result") != "OK":
            continue
        with stage("repair"):
            apply_repair(tool_name, proposal, payload, impl_validation)
        with stage("validation"):
            test_result = test_tool(tool_name)
            current_source = Path(source_path).read_text(encoding="utf-8")
            validation = validate_tool_result(
                proposal, test_result, research_result=research, source=current_source
            )
            step = first_pipeline_step(validation)

    current_source = Path(source_path).read_text(encoding="utf-8") if source_path and os.path.exists(source_path) else ""
    result["step_after"] = step
    result["codes_after"] = warning_codes(validation, "repairable") + warning_codes(
        validation, "blocked"
    )
    result["return_value"] = test_result.get("return_value")
    result["formatted_ok"] = is_usable_memory_usage(test_result.get("return_value"))
    result["validator_pass"] = step == "pass"
    result["command_from_findings"] = command_used_from_findings(
        current_source, research
    )
    result["final_source"] = current_source
    result["ok"] = (
        result["validator_pass"]
        and result["formatted_ok"]
        and result["structure_ok"]
    )
    if not result["ok"] and not result["error"]:
        result["error"] = (
            f"not ok: step={step}, value={test_result.get('return_value')}"
        )
    return result


def benchmark_conditions():
    return {
        "model": MODEL,
        "profile": PROFILE_ID,
        "temperature": PROFILE.get("temperature"),
        "num_predict": PROFILE.get("num_predict"),
        "timeout_seconds": PROFILE.get("timeout_seconds"),
        "context_limit": PROFILE.get("context_limit"),
        "prompt_style": PROFILE.get("prompt_style"),
        "keep_alive": PROFILE.get("keep_alive"),
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
        "max_research_rounds": MAX_RESEARCH_ROUNDS,
        "max_research_stagnation": MAX_RESEARCH_STAGNATION,
        "request": USER_REQUEST,
        "seeded_command": False,
    }


def save_run(result):
    payload = load_json_file(
        RESULTS_PATH,
        {
            "note": "環境調査ベンチ。正解コマンドは渡さない。unittest ではない。",
            "benchmark": "python -m research.llm_benchmarks.environment_benchmark",
            "runs": [],
        },
    )
    payload.setdefault("runs", [])
    payload["runs"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conditions": benchmark_conditions(),
            "summary": {
                "ok": result.get("ok"),
                "timing": result.get("timing"),
                "state": result.get("state"),
                "did_research": result.get("did_research"),
                "did_research_again": result.get("did_research_again"),
                "research_rounds": result.get("research_rounds"),
                "research_sufficient": result.get("research_sufficient"),
                "research_stagnation": result.get("research_stagnation"),
                "research_stop_reason": result.get("research_stop_reason"),
                "usable_findings": result.get("usable_findings"),
                "command_from_findings": result.get("command_from_findings"),
                "structure_ok": result.get("structure_ok"),
                "formatted_ok": result.get("formatted_ok"),
                "validator_pass": result.get("validator_pass"),
                "repaired": result.get("repaired"),
                "diagnosis": (result.get("diagnosis") or {}).get("kind"),
                "implementation_class": (
                    (result.get("implementation_class") or {}).get("class")
                ),
            },
            "pipeline": result.get("pipeline"),
            "result": {
                key: result.get(key)
                for key in (
                    "ok",
                    "proposal_name",
                    "step_after",
                    "codes_after",
                    "return_value",
                    "did_research_again",
                    "research_rounds",
                    "research_sufficient",
                    "research_stagnation",
                    "research_stop_reason",
                    "error",
                    "diagnosis",
                    "implementation_class",
                    "trace",
                    "timing",
                    "state",
                )
            },
        }
    )
    save_json_file(RESULTS_PATH, payload)
    if not result.get("ok"):
        failures = load_json_file(
            FAILURES_PATH,
            {
                "note": "環境調査ベンチの失敗詳細。",
                "entries": [],
            },
        )
        failures.setdefault("entries", [])
        failures["entries"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "profile": PROFILE_ID,
                "model": MODEL,
                "diagnosis": result.get("diagnosis"),
                "pipeline": result.get("pipeline"),
                "result": {
                    key: result.get(key)
                    for key in (
                        "ok",
                        "proposal_name",
                        "error",
                        "did_research",
                        "did_research_again",
                        "research_rounds",
                        "research_sufficient",
                        "research_stagnation",
                        "research_stop_reason",
                        "usable_findings",
                        "command_from_findings",
                        "structure_ok",
                        "formatted_ok",
                        "validator_pass",
                        "step_after",
                        "codes_after",
                        "return_value",
                        "diagnosis",
                        "implementation_class",
                        "trace",
                        "timing",
                        "state",
                    )
                },
                "conditions": benchmark_conditions(),
            }
        )
        save_json_file(FAILURES_PATH, failures)


def main():
    if contains_forbidden_answer(USER_REQUEST):
        raise SystemExit("USER_REQUEST に正解コマンドが含まれている")
    files, registry = snapshot_system_tools()
    try:
        result = run_once()
        save_run(result)
        mark = "OK" if result.get("ok") else "NG"
        print(f"{mark}  環境調査: {USER_REQUEST}")
        diagnosis = (result.get("diagnosis") or {}).get("kind")
        print(
            "  research={did_research} again={did_research_again} "
            "rounds={research_rounds} sufficient={research_sufficient} "
            "stagnation={research_stagnation} stop={research_stop_reason} "
            "findings={usable_findings} from_findings={command_from_findings} "
            "structure={structure_ok} formatted={formatted_ok} "
            "validator={validator_pass} repaired={repaired}".format(**result)
        )
        for item in result.get("pipeline", {}).get("progress") or []:
            print(
                "  progress[{round}]: {action} {reason} "
                "stag={stagnation} new={has_new_finding}".format(**item)
            )
        for item in result.get("pipeline", {}).get("judgments") or []:
            print(
                "  judge[{round}]: satisfies={satisfies_request} "
                "missing={missing} reason={reason}".format(**item)
            )
        if diagnosis:
            print(f"  diagnosis: {diagnosis}")
        impl_class = (result.get("implementation_class") or {}).get("class")
        if impl_class:
            print(f"  implementation: {impl_class}")
        if result.get("error"):
            print(f"  error: {result['error']}")
        print(f"  value={result.get('return_value')}")
        decisions = ((result.get("state") or {}).get("decisions") or [])
        if decisions:
            print(
                "  state: "
                + "; ".join(
                    f"{item.get('key')}={item.get('value')}" for item in decisions
                )
            )
        timing = result.get("timing") or {}
        if timing:
            print(
                "  timing: total={total_seconds}s llm={llm_seconds}s "
                "machine={machine_seconds}s research={research_seconds}s "
                "judge={judge_seconds}s implementation={implementation_seconds}s "
                "repair={repair_seconds}s validation={validation_seconds}s".format(
                    **timing
                )
            )
        return 0 if result.get("ok") else 1
    except Exception as exc:
        print(f"NG  {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        return 1
    finally:
        restore_system_tools(files, registry)
        stop_model(MODEL)


if __name__ == "__main__":
    raise SystemExit(main())
