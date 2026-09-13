"""
④ Research → Implementation の機械検査。LLM は呼ばない。

Clarity 問答で得た STATE を持ったまま、
Research が選んだ方法を Implementation が実際の Tool にできるかを見る。
Repair は見ない。失敗したときだけ工程を切り分ける。
"""

import json

from research.llm_benchmarks.clarity_state_classify import (
    inspect_user_state,
    run_scripted_handoff,
)
from research.llm_benchmarks.judge_verify_retry_classify import (
    inspect_judge_verify_retry,
)
from tools.system.tool_builder.implementation_classify import classify_implementation


CREATE_REQUEST = "Windowsのメモリ使用率を取得するToolを作ってください。"

STAGES = ("research", "judge", "implementation")

PIPELINE_STAGE_LABELS = (
    ("state_held", "STATE維持"),
    ("candidates_generated", "Research候補生成"),
    ("verifier_ran", "Verifier実行"),
    ("verifier_failure_detected", "Verifier失敗検出"),
    ("judge_a_quality", "Judge A品質"),
    ("research_retried", "Research再調査"),
    ("usable_finding", "usable finding"),
    ("judge_adopted", "Judge採用"),
    ("implementation_code", "Implementation code"),
    ("tool_runs", "Tool実行"),
)

CHECK_ORDER = (
    ("research", "research_method"),
    ("judge", "judge_adopted"),
    ("implementation", "code_generated"),
    ("implementation", "code_matches"),
    ("implementation", "registry"),
    ("implementation", "runs"),
)


def start_from_clarity_state(request=CREATE_REQUEST):
    """
    「使用率です」まで終わった STATE から始める。
    Clarity 自体は測らない。task だけ作成要求に合わせる。
    """
    handoff = run_scripted_handoff()
    state = handoff["state"]
    state.task = request
    return {
        "handoff": handoff,
        "state": state,
        "user_state": inspect_user_state(state),
        "request": request,
    }


def evidence_of(finding):
    item = finding or {}
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    command = evidence.get("command") or item.get("command")
    args = evidence.get("args") if evidence.get("args") is not None else item.get("args")
    sample = evidence.get("sample") if evidence.get("sample") is not None else item.get("sample")
    return {
        "command": command,
        "args": list(args or []),
        "sample": sample,
    }


def usable_method_findings(research, *, include_insufficient=False):
    found = []
    seen = set()
    buckets = list((research or {}).get("usable_findings") or [])
    if include_insufficient:
        buckets.extend((research or {}).get("insufficient_findings") or [])
    for item in buckets:
        evidence = evidence_of(item)
        if not (evidence["command"] and evidence["sample"]):
            continue
        key = (str(evidence["command"]), tuple(str(arg) for arg in evidence["args"]))
        if key in seen:
            continue
        seen.add(key)
        found.append(evidence)
    return found


def command_used_from_findings(source, research):
    if not source or not research:
        return False
    for item in usable_method_findings(research):
        command = str(item.get("command") or "")
        if command and command in source:
            return True
        for arg in item.get("args") or []:
            if str(arg) and str(arg) in source:
                return True
    return False


def inspect_research_method(research):
    # Judge が不十分へ移した finding も、Research が方法を出した証拠にする。
    findings = usable_method_findings(research, include_insufficient=True)
    return {
        "ok": bool(findings),
        "usable_count": len(findings),
        "findings": findings,
    }


def inspect_judge_adopted(judgments, *, research_sufficient):
    last = (judgments or [])[-1] if judgments else None
    return {
        "ok": bool(
            research_sufficient
            and last
            and last.get("satisfies_request")
        ),
        "satisfies_request": None if last is None else last.get("satisfies_request"),
        "rounds": len(judgments or []),
        "research_sufficient": bool(research_sufficient),
        "reason": None if last is None else last.get("reason"),
        "missing": None if last is None else last.get("missing"),
    }


def inspect_code_generated(payload):
    code = ""
    if isinstance(payload, dict):
        code = str(payload.get("code") or "")
    return {
        "ok": bool(code.strip()),
        "code_chars": len(code.strip()),
        "function": None if not isinstance(payload, dict) else payload.get("function"),
        "path": None if not isinstance(payload, dict) else payload.get("path"),
    }


def inspect_code_matches(code, research, classified=None):
    classified = classified or classify_implementation(
        code=code,
        research_result=research,
    )
    adopted = bool(classified.get("finding_adopted"))
    return {
        "ok": adopted,
        "class": classified.get("class"),
        "finding_adopted": adopted,
        "command_from_findings": command_used_from_findings(code, research),
        "missing": classified.get("missing") or [],
        "used_other": classified.get("used_other") or [],
    }


def inspect_registry(
    registered,
    proposal,
    *,
    path_exists=False,
    in_registry=False,
):
    module = str((proposal or {}).get("module") or "")
    structure = module.startswith("tools.system.")
    output = (proposal or {}).get("output")
    output_ok = output == ["status"] if output is not None else False
    registered_ok = (registered or {}).get("result") == "OK"
    return {
        "ok": bool(registered_ok and structure and path_exists and in_registry),
        "registered": registered_ok,
        "structure": structure,
        "output_ok": output_ok,
        "path_exists": bool(path_exists),
        "in_registry": bool(in_registry),
        "module": module,
        "path": (registered or {}).get("path"),
        "name": (proposal or {}).get("name") or (registered or {}).get("registered_name"),
        "errors": list((registered or {}).get("errors") or []),
    }


def inspect_runs(test_result):
    status = None if test_result is None else test_result.get("status")
    value = None if test_result is None else test_result.get("return_value")
    return {
        "ok": status == "pass",
        "status": status,
        "error": None if test_result is None else test_result.get("error"),
        "error_type": None if test_result is None else test_result.get("error_type"),
        "return_value": value,
        "is_dict": isinstance(value, dict),
    }


def inspect_fail_stage(checks, *, proposal_error=None):
    if proposal_error:
        return "proposal"
    for stage, key in CHECK_ORDER:
        item = (checks or {}).get(key) or {}
        if not item.get("ok"):
            return stage
    return None


def summarize_verified_round(researched):
    candidates = (researched or {}).get("candidates") or []
    verified = ((researched or {}).get("verified") or {}).get("results") or []
    runs = []
    candidate_keys = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        candidate_keys.append(
            {
                "command": str(cand.get("command") or ""),
                "args": list(cand.get("args") or []),
            }
        )
    for item in verified:
        evidence = item.get("evidence") or {}
        sample = evidence.get("sample") or []
        high = item.get("confidence") == "high"
        runs.append(
            {
                "ok": high,
                "sample_count": len(sample),
                "error": evidence.get("error"),
                "confidence": item.get("confidence"),
                "command": evidence.get("command"),
                "args": list(evidence.get("args") or []),
            }
        )
    return {
        "candidate_count": len(candidates),
        "verified_count": len(runs),
        "runs": runs,
        "candidate_keys": candidate_keys,
        "any_failure": bool(runs) and any(not item["ok"] for item in runs),
    }


def inspect_pipeline_stages(
    *,
    user_state=None,
    research_rounds=None,
    research=None,
    judgments=None,
    research_sufficient=False,
    payload=None,
    test_result=None,
    checks=None,
):
    checks = checks or {}
    rounds = list(research_rounds or [])
    round_count = len(rounds)
    any_candidates = any(item.get("candidate_count", 0) > 0 for item in rounds)
    any_verified = any(item.get("verified_count", 0) > 0 for item in rounds)
    any_verify_failure = any(item.get("verifier_failure") for item in rounds)
    judge_a_on_failure = any(
        item.get("judge_grade") == "A"
        and not item.get("satisfies_request")
        and item.get("verifier_failure")
        for item in rounds
    )
    retried = round_count >= 2 and any(item.get("round", 0) > 1 for item in rounds)
    usable = inspect_research_method(research)
    adopted = inspect_judge_adopted(
        judgments, research_sufficient=research_sufficient
    )
    code = inspect_code_generated(payload)
    runs = inspect_runs(test_result)

    stages = {
        "state_held": {
            "ok": bool((user_state or {}).get("ok")),
            "label": "STATE維持",
        },
        "candidates_generated": {
            "ok": any_candidates,
            "label": "Research候補生成",
            "rounds_with_candidates": sum(
                1 for item in rounds if item.get("candidate_count", 0) > 0
            ),
        },
        "verifier_ran": {
            "ok": any_verified,
            "label": "Verifier実行",
            "verified_total": sum(item.get("verified_count", 0) for item in rounds),
        },
        "verifier_failure_detected": {
            "ok": any_verify_failure,
            "label": "Verifier失敗検出",
            "rounds": [
                item.get("round")
                for item in rounds
                if item.get("verifier_failure")
            ],
        },
        "judge_a_quality": {
            "ok": judge_a_on_failure,
            "label": "Judge A品質",
            "rounds": [
                item.get("round")
                for item in rounds
                if item.get("judge_grade") == "A"
                and not item.get("satisfies_request")
            ],
        },
        "research_retried": {
            "ok": retried,
            "label": "Research再調査",
            "rounds": round_count,
        },
        "usable_finding": {
            "ok": bool((checks.get("research_method") or usable).get("ok")),
            "label": "usable finding",
            "usable_count": usable.get("usable_count", 0),
        },
        "judge_adopted": {
            "ok": bool((checks.get("judge_adopted") or adopted).get("ok")),
            "label": "Judge採用",
            "rounds": adopted.get("rounds", 0),
        },
        "implementation_code": {
            "ok": bool((checks.get("code_generated") or code).get("ok")),
            "label": "Implementation code",
            "code_chars": code.get("code_chars", 0),
        },
        "tool_runs": {
            "ok": bool((checks.get("runs") or runs).get("ok")),
            "label": "Tool実行",
            "return_value": runs.get("return_value"),
        },
    }
    first_fail = next(
        (key for key, _label in PIPELINE_STAGE_LABELS if not stages[key]["ok"]),
        None,
    )
    return {
        "stages": stages,
        "first_fail": first_fail,
        "ok": first_fail is None,
    }


def inspect_missing_handoff(handoff, *, prompt_materials=None):
    """
    Judge missing → Research への引き渡しが機械的に揃っているか。
    """
    handoff = handoff or {}
    questions = list(handoff.get("followup_questions") or [])
    items = list(handoff.get("research_items") or [])
    item_questions = [
        str(item.get("question") or "").strip()
        for item in items
        if item.get("followup") and str(item.get("question") or "").strip()
    ]
    questions_ok = questions == item_questions and bool(questions)
    in_prompt = True
    if prompt_materials is not None and questions:
        blob = json.dumps(prompt_materials, ensure_ascii=False)
        in_prompt = all(question in blob for question in questions)
    rejected = handoff.get("rejected_commands") or []
    prior = handoff.get("prior_failures") or []
    return {
        "ok": questions_ok and in_prompt,
        "followup_questions": questions,
        "item_questions": item_questions,
        "in_prompt": in_prompt,
        "rejected_count": len(rejected),
        "prior_failure_count": len(prior),
    }


def inspect_create_result(
    *,
    research=None,
    judgments=None,
    research_sufficient=False,
    payload=None,
    classified=None,
    registered=None,
    proposal=None,
    path_exists=False,
    in_registry=False,
    test_result=None,
    proposal_error=None,
    repaired=False,
    user_state=None,
    research_rounds=None,
):
    code = ""
    if isinstance(payload, dict):
        code = str(payload.get("code") or "")
    checks = {
        "research_method": inspect_research_method(research),
        "judge_adopted": inspect_judge_adopted(
            judgments, research_sufficient=research_sufficient
        ),
        "code_generated": inspect_code_generated(payload),
        "code_matches": inspect_code_matches(code, research, classified=classified),
        "registry": inspect_registry(
            registered,
            proposal,
            path_exists=path_exists,
            in_registry=in_registry,
        ),
        "runs": inspect_runs(test_result),
    }
    fail_stage = inspect_fail_stage(checks, proposal_error=proposal_error)
    pipeline = inspect_pipeline_stages(
        user_state=user_state,
        research_rounds=research_rounds,
        research=research,
        judgments=judgments,
        research_sufficient=research_sufficient,
        payload=payload,
        test_result=test_result,
        checks=checks,
    )
    return {
        "ok": fail_stage is None and not repaired,
        "fail_stage": fail_stage,
        "repaired": bool(repaired),
        "checks": checks,
        "pipeline": pipeline,
    }
