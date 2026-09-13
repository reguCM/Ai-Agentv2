"""
実装層ベンチ。unittest ではない。

Research/Judge は固定した usable_findings を渡す。
PASS は実用上の合格、score は品質比較。仕様は docs/scoring.md。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from tools.ai.llm.adapter import build_implement_messages, retry_extra, validation_extra
from tools.ai.state.task_state import TaskState
from tools.ai.tool_builder.implementation import create_tool_implementation
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.llm_failure_memory import load_environment_case
from tools.system.timing import Timing, stage
from tools.system.tool_builder.apply import has_repair_code
from tools.system.tool_builder.implementation_classify import (
    classify_implementation,
    distinctive_fragments,
)
from tools.system.tool_builder.register import register_tool
from tools.system.tool_builder.score import score_implementation
from tools.system.tool_builder.test import test_tool
from tools.system.tool_builder.validate.implementation import (
    validate_tool_implementation,
)
from research.llm_benchmarks.environment_benchmark import (
    load_registry_tools,
    prepare_code_payload,
    restore_system_tools,
    snapshot_system_tools,
)
from research.llm_benchmarks.history import refresh_history
from research.llm_benchmarks.research_implement_classify import inspect_create_result


CASE_ID = (
    os.environ.get("AI_AGENT_IMPLEMENT_CASE")
    or "implement_single_select_memory_usage"
)
REPEAT = int(os.environ.get("AI_AGENT_IMPLEMENT_REPEAT") or 3)
DEFAULT_MODELS = (
    "qwen3_8b,qwen3_14b,qwen2_5_coder_7b,gemma3_12b"
)
RESULTS_PATH = "research/llm_benchmarks/implementation_results.json"
FAILURES_PATH = "research/llm_benchmarks/implementation_failures.json"


def selected_models():
    listed = os.environ.get("AI_AGENT_IMPLEMENT_MODELS", "").strip()
    if listed:
        return [item.strip() for item in listed.split(",") if item.strip()]
    if os.environ.get("AI_AGENT_MODEL"):
        return [os.environ["AI_AGENT_MODEL"].strip()]
    return [item.strip() for item in DEFAULT_MODELS.split(",") if item.strip()]


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


def ask_implement(materials, profile, extra=None, state=None):
    messages = build_implement_messages(
        materials, extra=extra, profile=profile, state=state
    )
    try:
        response = chat(model=profile["model"], messages=messages)
        text = response.message.content
    except LLMTimeoutError as exc:
        return None, "timeout", str(exc)
    payload = extract_json_object(text)
    if payload is None:
        messages = build_implement_messages(
            materials,
            extra=extra or retry_extra(profile),
            profile=profile,
            state=state,
        )
        try:
            response = chat(model=profile["model"], messages=messages)
            text = response.message.content
        except LLMTimeoutError as exc:
            return None, "timeout", str(exc)
        payload = extract_json_object(text)
    if payload is None:
        return None, "no_json", text
    return payload, None, text


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


def load_json_file(path, default):
    target = Path(path)
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def save_json_file(path, payload):
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def selected_cases():
    listed = os.environ.get("AI_AGENT_IMPLEMENT_CASES", "").strip()
    if listed:
        return [item.strip() for item in listed.split(",") if item.strip()]
    return [CASE_ID]


def expected_findings(case):
    markers = list(case.get("correct_fragments") or [])
    if not markers and case.get("correct_fragment"):
        markers = [case["correct_fragment"]]
    findings = (case.get("research_result") or {}).get("usable_findings") or []
    matched = []
    for marker in markers:
        for item in findings:
            if marker in distinctive_fragments(item) and item not in matched:
                matched.append(item)
                break
    return matched


def expected_finding(case):
    matched = expected_findings(case)
    return matched[0] if matched else None


def case_state(case):
    if not case.get("state"):
        return None
    return TaskState.from_payload(case.get("state"))


def _is_unimplemented_stub_error(errors):
    if not errors:
        return False
    return all("unimplemented" in str(item).lower() for item in errors)


def apply_to_registry(case, payload, *, repair_mode=None):
    proposal = case.get("proposal") or {}
    if repair_mode is None:
        repair_mode = bool((case.get("judge") or {}).get("satisfies_request"))
    tools = load_registry_tools()
    payload = prepare_code_payload(payload, proposal)
    validation = validate_tool_implementation(
        proposal, payload, registry=tools, repair_mode=repair_mode
    )
    if validation.get("result") != "OK":
        return {
            "payload": payload,
            "registered": None,
            "test_result": None,
            "error": "impl_validation_ng",
            "validation": validation,
            "validation_errors": validation.get("errors"),
        }
    registered = register_tool(proposal, payload, validation_result=validation)
    if registered.get("result") != "OK":
        return {
            "payload": payload,
            "registered": registered,
            "test_result": None,
            "error": "register_ng",
            "validation": validation,
            "validation_errors": None,
        }
    return {
        "payload": payload,
        "registered": registered,
        "test_result": test_tool(proposal.get("name")),
        "error": None,
        "validation": validation,
        "validation_errors": None,
    }


def run_once(case, profile):
    state = case_state(case)
    snapshot = None
    with Timing() as clock:
        try:
            with stage("implementation"):
                materials = create_tool_implementation(
                    case.get("proposal"),
                    environment=verified_environment(),
                    research_result=case.get("research_result"),
                    request=case.get("request"),
                )
                payload, error, text = ask_implement(
                    materials, profile, state=state
                )
            required = expected_findings(case)
            classified = classify_implementation(
                payload=payload,
                error=error,
                research_result=case.get("research_result"),
                expected_findings=required,
            )
            code = (payload or {}).get("code") if isinstance(payload, dict) else None
            scored = score_implementation(classified=classified, error=error)
            registered = None
            test_result = None
            registry_error = None
            validation_errors = None
            if case.get("check_registry") and not error and has_repair_code(payload):
                snapshot = snapshot_system_tools()
                applied = apply_to_registry(case, payload, repair_mode=False)
                if (
                    applied["error"] == "impl_validation_ng"
                    and _is_unimplemented_stub_error(applied["validation_errors"])
                    and (case.get("judge") or {}).get("satisfies_request")
                ):
                    applied = apply_to_registry(case, payload, repair_mode=True)
                elif applied["error"] == "impl_validation_ng":
                    payload, error, text = ask_implement(
                        materials,
                        profile,
                        extra=validation_extra(applied["validation_errors"]),
                        state=state,
                    )
                    classified = classify_implementation(
                        payload=payload,
                        error=error,
                        research_result=case.get("research_result"),
                        expected_findings=required,
                    )
                    code = (
                        (payload or {}).get("code")
                        if isinstance(payload, dict)
                        else None
                    )
                    scored = score_implementation(
                        classified=classified, error=error
                    )
                    if not error and has_repair_code(payload):
                        applied = apply_to_registry(case, payload, repair_mode=False)
                        if (
                            applied["error"] == "impl_validation_ng"
                            and _is_unimplemented_stub_error(
                                applied["validation_errors"]
                            )
                            and (case.get("judge") or {}).get("satisfies_request")
                        ):
                            applied = apply_to_registry(
                                case, payload, repair_mode=True
                            )
                payload = applied["payload"]
                registered = applied["registered"]
                test_result = applied["test_result"]
                registry_error = applied["error"]
                validation_errors = applied.get("validation_errors")
                if isinstance(payload, dict):
                    code = payload.get("code")
                if registry_error:
                    scored = dict(scored)
                    scored["pass"] = False
                    scored["pipeline"] = dict(scored.get("pipeline") or {})
                    scored["pipeline"]["validation"] = "fail"
            inspected = None
            if case.get("check_registry"):
                judgments = [
                    {
                        "satisfies_request": (case.get("judge") or {}).get(
                            "satisfies_request"
                        ),
                        "missing": (case.get("judge") or {}).get("missing") or [],
                        "reason": (case.get("judge") or {}).get("reason") or "",
                    }
                ]
                path = (registered or {}).get("path")
                in_registry = False
                name = (case.get("proposal") or {}).get("name")
                if name:
                    in_registry = any(
                        item.get("name") == name for item in load_registry_tools()
                    )
                inspected = inspect_create_result(
                    research=case.get("research_result"),
                    judgments=judgments,
                    research_sufficient=bool(
                        (case.get("judge") or {}).get("satisfies_request")
                    ),
                    payload=payload,
                    classified=classified,
                    registered=registered,
                    proposal=case.get("proposal"),
                    path_exists=bool(path and Path(path).exists()),
                    in_registry=in_registry,
                    test_result=test_result,
                    repaired=False,
                    user_state={"ok": True} if state is not None else None,
                )
                if not inspected.get("ok"):
                    scored = dict(scored)
                    scored["pass"] = False
            return {
                "ok": scored["pass"],
                "pass": scored["pass"],
                "score": scored["score"],
                "grade": scored["grade"],
                "scoring_version": scored["scoring_version"],
                "score_breakdown": scored["score_breakdown"],
                "caps": scored["caps"],
                "pipeline": scored["pipeline"],
                "implementation_class": classified,
                "error": error or registry_error,
                "validation_errors": validation_errors,
                "generated_code": code,
                "unimplemented": (payload or {}).get("unimplemented")
                if isinstance(payload, dict)
                else None,
                "notes": (payload or {}).get("notes")
                if isinstance(payload, dict)
                else None,
                "parsed_keys": list(payload.keys())
                if isinstance(payload, dict)
                else [],
                "llm_text": text,
                "timing": clock.snapshot(),
                "registered": registered,
                "test_result": test_result,
                "checks": None if inspected is None else inspected.get("checks"),
                "fail_stage": None
                if inspected is None
                else inspected.get("fail_stage"),
            }
        finally:
            if snapshot is not None:
                restore_system_tools(*snapshot)


def append_results(entry):
    payload = load_json_file(
        RESULTS_PATH,
        {
            "note": "実装層ベンチ。Research/Judge は固定。unittest ではない。採点は docs/scoring.md。",
            "benchmark": "python -m research.llm_benchmarks.implementation_benchmark",
            "scoring_version": "1.0",
            "runs": [],
        },
    )
    payload.setdefault("runs", []).append(entry)
    save_json_file(RESULTS_PATH, payload)
    refresh_history(results=payload)
    if not entry.get("pass"):
        failures = load_json_file(
            FAILURES_PATH,
            {
                "note": "実装層の FAIL。PASS と score は docs/scoring.md。",
                "entries": [],
            },
        )
        failures.setdefault("entries", []).append(entry)
        save_json_file(FAILURES_PATH, failures)


def main():
    case_ids = selected_cases()
    models = selected_models()
    print(f"cases={case_ids}  repeat={REPEAT}  models={models}")
    all_totals = {}
    for case_id in case_ids:
        case = load_environment_case(case_id)
        if not case:
            raise SystemExit(f"case がない: {case_id}")
        print(f"case={case_id}")
        totals = {}
        for profile_id in models:
            os.environ["AI_AGENT_MODEL"] = profile_id
            profile = get_llm_profile(profile_id)
            counts = {}
            try:
                for index in range(1, REPEAT + 1):
                    result = run_once(case, profile)
                    kind = result["implementation_class"]["class"]
                    counts[kind] = counts.get(kind, 0) + 1
                    mark = "PASS" if result["pass"] else "FAIL"
                    extra = ""
                    if result.get("checks"):
                        extra = (
                            "  fail_stage={fail}  registry={reg}  runs={runs}".format(
                                fail=result.get("fail_stage"),
                                reg=(result["checks"].get("registry") or {}).get("ok"),
                                runs=(result["checks"].get("runs") or {}).get("ok"),
                            )
                        )
                    print(
                        f"{mark}  {case_id}  {profile_id} {index}/{REPEAT}  {kind}  "
                        f"{result['score']} {result['grade']}  "
                        f"{(result.get('timing') or {}).get('total_seconds')}s"
                        f"{extra}"
                    )
                    append_results(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "case": case_id,
                            "profile": profile_id,
                            "model": profile["model"],
                            "n": index,
                            "ok": result["pass"],
                            "pass": result["pass"],
                            "score": result["score"],
                            "grade": result["grade"],
                            "scoring_version": result["scoring_version"],
                            "score_breakdown": result["score_breakdown"],
                            "caps": result["caps"],
                            "pipeline": result["pipeline"],
                            "timing": result.get("timing"),
                            "implementation_class": result["implementation_class"],
                            "error": result["error"],
                            "validation_errors": result.get("validation_errors"),
                            "parsed_keys": result["parsed_keys"],
                            "unimplemented": result["unimplemented"],
                            "notes": result["notes"],
                            "generated_code": result["generated_code"],
                            "fail_stage": result.get("fail_stage"),
                            "checks": result.get("checks"),
                            "test_result": result.get("test_result"),
                        }
                    )
            finally:
                stop_model(profile["model"])
            totals[profile_id] = counts
            print(f"  {case_id} {profile_id}: {counts}")
        all_totals[case_id] = totals
    print("totals", all_totals)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"NG  {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        raise SystemExit(1)
