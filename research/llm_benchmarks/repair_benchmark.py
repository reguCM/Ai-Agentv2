import json
import os
import traceback
from datetime import datetime, timezone

from tools.ai.llm.adapter import build_repair_messages, retry_extra, validation_extra
from tools.ai.tool_builder.repair import repair_tool
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.timing import Timing, stage
from tools.system.tool_builder.apply import apply_repair, has_repair_code
from tools.system.tool_builder.repair_family import classify_repair_family
from tools.system.tool_builder.test import test_tool
from tools.system.tool_builder.validate.implementation import (
    validate_tool_implementation,
)
from tools.system.tool_builder.validate.result import validate_tool_result
from tools.system.tool_builder.validate.warning_actions import first_pipeline_step

from tests.fixtures import broken_tools


PROFILE = get_llm_profile()
PIPELINE = get_pipeline()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
MAX_REPAIR_ROUNDS = int(PIPELINE.get("max_repair_rounds") or 3)

CASE_ID = os.environ.get("AI_AGENT_TEST_CASE_ID", "").strip() or None
FAMILY_ID = os.environ.get("AI_AGENT_REPAIR_FAMILY", "").strip() or None
DEBUG_TRACEBACK = os.environ.get("AI_AGENT_DEBUG_TRACEBACK", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

TOOL_PATH = "tools/system/cpu/cpu_status.py"
REGISTRY_PATH = "registry/tools.json"
BENCHMARK_DIR = "research/llm_benchmarks"
FAILURES_PATH = f"{BENCHMARK_DIR}/repair_failures.json"
RESULTS_PATH = f"{BENCHMARK_DIR}/repair_results.json"

PROPOSAL = {
    "name": "cpu_status",
    "module": "tools.system.cpu.cpu_status",
    "function": "cpu_status",
    "category": "system",
    "subcategory": "cpu",
    "description": "CPU status",
    "keywords": ["CPU", "status"],
    "risk": "low",
    "input": {},
    "output": ["status"],
}

CASES = [
    {
        "id": "unparsed_output",
        "family": "R1",
        "title": "R1 生出力 → 数値抽出",
        "source": broken_tools.SOURCE_UNPARSED,
        "research": None,
        "target_codes": ["unparsed_output"],
        "expect_step": "repair",
    },
    {
        "id": "wrong_output_key",
        "family": "R1",
        "title": "R1 outputキー間違い → 正しいキーへ",
        "source": broken_tools.SOURCE_WRONG_KEY,
        "research": None,
        "target_codes": ["wrong_output_key"],
        "expect_step": "repair",
    },
    {
        "id": "return_value_not_dict",
        "family": "R1",
        "title": "R1 return_valueがdictではない → dict化",
        "source": broken_tools.SOURCE_NOT_DICT,
        "research": None,
        "target_codes": ["return_value_not_dict"],
        "expect_step": "repair",
    },
    {
        "id": "empty_body",
        "family": "R1",
        "title": "R1 空 code → 戻り値の形を直す",
        "source": broken_tools.SOURCE_EMPTY_BODY,
        "research": None,
        "target_codes": ["return_value_not_dict"],
        "expect_step": "repair",
    },
    {
        "id": "subprocess_result_handling",
        "family": "R2",
        "title": "R2 subprocessの戻り値処理ミス",
        "source": broken_tools.SOURCE_SUBPROCESS_BAD,
        "research": None,
        "target_codes": ["subprocess_result_handling"],
        "expect_step": "repair",
    },
    {
        "id": "index_error",
        "family": "R2",
        "title": "R2 IndexError",
        "source": broken_tools.SOURCE_INDEX_ERROR,
        "research": None,
        "target_codes": ["runtime_exception"],
        "expect_step": "repair",
    },
    {
        "id": "key_error",
        "family": "R2",
        "title": "R2 KeyError",
        "source": broken_tools.SOURCE_KEY_ERROR,
        "research": None,
        "target_codes": ["runtime_exception"],
        "expect_step": "repair",
    },
    {
        "id": "type_error",
        "family": "R2",
        "title": "R2 TypeError",
        "source": broken_tools.SOURCE_TYPE_ERROR,
        "research": None,
        "target_codes": ["runtime_exception"],
        "expect_step": "repair",
    },
    {
        "id": "semantic_mismatch",
        "family": "R3",
        "title": "R3 動くが要求と違う値",
        "source": broken_tools.SOURCE_SEMANTIC,
        "research": broken_tools.VERIFIED_RESEARCH,
        "target_codes": ["semantic_mismatch"],
        "expect_step": "repair",
    },
    {
        "id": "wrong_command",
        "family": "R4",
        "title": "R4 間違ったfinding → 確認済みfindingへ",
        "source": broken_tools.SOURCE_WRONG_COMMAND,
        "research": broken_tools.VERIFIED_RESEARCH,
        "target_codes": ["wrong_command"],
        "expect_step": "research_repair",
    },
    {
        "id": "stub_needs_research",
        "family": "R5",
        "title": "R5 finding不足 → research",
        "source": broken_tools.SOURCE_STUB,
        "research": None,
        "target_codes": ["stub_value"],
        "expect_step": "research",
        "routing_only": True,
    },
    {
        "id": "stub_value",
        "family": "R5",
        "title": "R5 調査済みfindingでスタブを実装",
        "source": broken_tools.SOURCE_STUB,
        "research": broken_tools.VERIFIED_RESEARCH,
        "target_codes": ["stub_value"],
        "expect_step": "research_repair",
    },
]

if CASE_ID:
    CASES = [c for c in CASES if c.get("id") == CASE_ID]
    if not CASES:
        raise SystemExit(f"Unknown AI_AGENT_TEST_CASE_ID={CASE_ID}")
if FAMILY_ID:
    CASES = [c for c in CASES if c.get("family") == FAMILY_ID]
    if not CASES:
        raise SystemExit(f"Unknown AI_AGENT_REPAIR_FAMILY={FAMILY_ID}")


def extract_json_object(text):
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except Exception:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        v = json.loads(s[start : end + 1])
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def prepare_payload(payload):
    payload = dict(payload or {})
    payload["path"] = TOOL_PATH
    payload["function"] = "cpu_status"
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


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def save_json_file(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def benchmark_conditions():
    return {
        "model": MODEL,
        "profile": PROFILE_ID,
        "temperature": float(PROFILE.get("temperature") or 0),
        "num_predict": int(PROFILE.get("num_predict") or 2048),
        "timeout_seconds": int(PROFILE.get("timeout_seconds") or 90),
        "context_limit": int(PROFILE.get("context_limit") or 0),
        "prompt_style": PROFILE.get("prompt_style"),
        "keep_alive": PROFILE.get("keep_alive") or "5m",
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
        "case_filter": CASE_ID,
        "family_filter": FAMILY_ID,
    }


def classify_failure_pattern(result):
    codes_after = result.get("codes_after") or []
    error = str(result.get("error") or "")
    return_value = result.get("return_value")
    if "runtime_exception" in codes_after:
        return "runtime_exception_after_repair"
    if "meaningless_output" in codes_after:
        if isinstance(return_value, dict) and any(
            "---" in str(value) for value in return_value.values()
        ):
            return "separator_line_returned"
        return "meaningless_output_after_repair"
    if "wrong_command" in codes_after:
        return "wrong_command_after_repair"
    if "stub_value" in codes_after:
        return "stub_not_implemented"
    if "no_json" in error:
        return "llm_output_not_json"
    if "no_code" in error:
        return "llm_output_missing_code"
    if "timeout" in error.lower():
        return "llm_timeout"
    return "other"


def save_failure_records(failures):
    payload = load_json_file(
        FAILURES_PATH,
        {
            "note": "LLM修復ベンチの失敗詳細。将来の blacklist / 補助機構の材料として保存する。",
            "entries": [],
        },
    )
    payload.setdefault("entries", [])
    payload["entries"].extend(failures)
    save_json_file(FAILURES_PATH, payload)


def save_benchmark_run(results):
    payload = load_json_file(
        RESULTS_PATH,
        {
            "note": "LLM修復ベンチの実測結果。通常の unittest とは分離する。",
            "benchmark": "python -m research.llm_benchmarks.repair_benchmark",
            "runs": [],
        },
    )
    payload.setdefault("runs", [])
    passed = sum(1 for r in results if r.get("ok"))
    payload["runs"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conditions": benchmark_conditions(),
            "summary": {
                "passed_cases": passed,
                "total_cases": len(results),
                "passed_ratio": f"{passed}/{len(results)}",
                "by_family": {
                    family: {
                        "passed": sum(
                            1
                            for item in results
                            if item.get("family") == family and item.get("ok")
                        ),
                        "total": sum(
                            1 for item in results if item.get("family") == family
                        ),
                    }
                    for family in sorted(
                        {item.get("family") for item in results if item.get("family")}
                    )
                },
            },
            "cases": [
                {
                    "id": r.get("id"),
                    "family": r.get("family"),
                    "title": r.get("title"),
                    "ok": r.get("ok"),
                    "step_before": r.get("step_before"),
                    "step_after": r.get("step_after"),
                    "codes_before": r.get("codes_before"),
                    "codes_after": r.get("codes_after"),
                    "repair_rounds": r.get("rounds"),
                    "error": r.get("error"),
                    "timing": r.get("timing"),
                    "failure_pattern": None if r.get("ok") else classify_failure_pattern(r),
                }
                for r in results
            ],
        }
    )
    save_json_file(RESULTS_PATH, payload)


def is_usable_status(return_value):
    if not isinstance(return_value, dict):
        return False
    status = return_value.get("status")
    if status is None:
        return False
    t = str(status).strip()
    if t in ("", "error", "未実装"):
        return False
    if "LoadPercentage" in t:
        return False
    if "---" in t:
        return False
    return t.replace(".", "", 1).isdigit()


def warning_codes(validation, key):
    return [
        item.get("code")
        for item in (validation.get("disposition") or {}).get(key) or []
    ]


def classify(test_result, research_result=None, source=None):
    validation = validate_tool_result(
        PROPOSAL,
        test_result,
        implementation={},
        research_result=research_result,
        source=source,
    )
    step = first_pipeline_step(validation)
    return validation, step


def ask_llm(materials, extra=None):
    messages = build_repair_messages(materials, extra=extra)
    try:
        response = chat(model=MODEL, messages=messages)
    except LLMTimeoutError as exc:
        return "", None, str(exc)
    text = response.message.content
    payload = extract_json_object(text)
    return text, payload, None


def apply_llm_repair(test_result, validation, research_result):
    last_text = None
    with stage("repair"):
        materials = repair_tool(
            "cpu_status",
            PROPOSAL,
            {},
            test_result,
            validation,
            research_result=research_result,
        )
        text, payload, timeout_error = ask_llm(materials)
    last_text = text
    if timeout_error:
        return None, timeout_error, text, "timeout", {"llm_text": last_text}
    if payload is None:
        with stage("repair"):
            text, payload, timeout_error = ask_llm(materials, extra=retry_extra())
        last_text = text
        if timeout_error:
            return None, timeout_error, text, "timeout", {"llm_text": last_text}
    if payload is None:
        return None, "no_json", text, "no_json", {"llm_text": last_text}

    payload = prepare_payload(payload)
    if not has_repair_code(payload):
        return None, None, None, "no_code", {
            "llm_text": last_text,
            "generated_code": payload.get("code"),
            "payload": payload,
        }

    with stage("validation"):
        impl_validation = validate_tool_implementation(
            PROPOSAL, payload, registry=[{"name": "cpu_status"}], repair_mode=True
        )
    if impl_validation.get("result") != "OK":
        with stage("repair"):
            text, payload, timeout_error = ask_llm(
                materials, extra=validation_extra(impl_validation.get("errors"))
            )
        last_text = text
        if timeout_error:
            return None, timeout_error, text, "timeout", {"llm_text": last_text}
        if payload is None:
            return None, "no_json_after_validation", text, "no_json", {
                "llm_text": last_text
            }
        payload = prepare_payload(payload)
        if not has_repair_code(payload):
            return None, None, None, "no_code", {
                "llm_text": last_text,
                "generated_code": payload.get("code"),
                "payload": payload,
            }
        with stage("validation"):
            impl_validation = validate_tool_implementation(
                PROPOSAL, payload, registry=[{"name": "cpu_status"}], repair_mode=True
            )
        if impl_validation.get("result") != "OK":
            return None, "impl_validation_ng", text, "impl_validation_ng", {
                "llm_text": last_text,
                "generated_code": payload.get("code"),
                "payload": payload,
                "implementation_validation": impl_validation,
            }

    with stage("repair"):
        apply_result = apply_repair("cpu_status", PROPOSAL, payload, impl_validation)
    if apply_result.get("result") != "OK":
        return None, "apply_repair_ng", None, "apply_repair_ng", {
            "llm_text": last_text,
            "generated_code": payload.get("code"),
            "payload": payload,
            "apply_result": apply_result,
        }

    return payload, None, None, None, {
        "llm_text": last_text,
        "generated_code": payload.get("code"),
        "payload": payload,
    }


def main():
    with open(TOOL_PATH, "r", encoding="utf-8") as f:
        original_tool = f.read()
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        original_registry = f.read()

    results = []
    try:
        for case in CASES:
            result = {
                "id": case["id"],
                "family": case.get("family"),
                "title": case["title"],
                "ok": False,
                "step_before": None,
                "step_after": None,
                "rounds": 0,
                "codes_before": [],
                "codes_after": [],
                "return_value": None,
                "error": None,
            }
            clock = Timing()
            clock.__enter__()
            try:
                with open(TOOL_PATH, "w", encoding="utf-8") as f:
                    f.write(case["source"].strip() + "\n")

                with stage("validation"):
                    test_result = test_tool("cpu_status")
                    validation, step = classify(
                        test_result,
                        research_result=case["research"],
                        source=case["source"],
                    )
                result["step_before"] = step
                result["codes_before"] = warning_codes(
                    validation, "repairable"
                ) + warning_codes(validation, "blocked")
                result["initial_test_result"] = test_result
                result["initial_validation"] = validation

                result["family"] = case.get("family") or classify_repair_family(
                    codes=result["codes_before"], step=step
                )
                if step != case["expect_step"]:
                    result["error"] = f"bad step before: {step}"
                    results.append(result)
                    continue
                if not any(
                    code in result["codes_before"] for code in case["target_codes"]
                ):
                    result["error"] = (
                        f"target codes missing before: {result['codes_before']}"
                    )
                    results.append(result)
                    continue

                if case.get("routing_only"):
                    result["ok"] = True
                    result["step_after"] = step
                    result["codes_after"] = result["codes_before"]
                    results.append(result)
                    mark = "OK"
                    print(f"{mark}  {result['title']}")
                    print(
                        f"  family={result['family']} before={result['step_before']} "
                        f"routing_only codes={result['codes_before']}"
                    )
                    continue

                current_test = test_result
                current_validation = validation
                current_step = step
                current_source = case["source"]
                last_repair_details = {}

                for round_num in range(1, MAX_REPAIR_ROUNDS + 1):
                    if current_step == "pass":
                        break
                    if current_step not in ("repair", "research_repair"):
                        break
                    result["rounds"] = round_num

                    _, error, _, reason, repair_details = apply_llm_repair(
                        current_test, current_validation, case["research"]
                    )
                    last_repair_details = repair_details or {}
                    if reason == "timeout":
                        result["error"] = error or "LLM timeout"
                        break
                    if reason == "no_code":
                        continue
                    if error:
                        result["error"] = error
                        break

                    with open(TOOL_PATH, "r", encoding="utf-8") as f:
                        current_source = f.read()
                    with stage("validation"):
                        current_test = test_tool("cpu_status")
                        current_validation, current_step = classify(
                            current_test,
                            research_result=case["research"],
                            source=current_source,
                        )

                result["step_after"] = current_step
                result["codes_after"] = warning_codes(
                    current_validation, "repairable"
                ) + warning_codes(current_validation, "blocked")
                result["return_value"] = current_test.get("return_value")
                result["final_source"] = current_source
                result["final_test_result"] = current_test
                result["final_validation"] = current_validation
                result["last_repair_details"] = last_repair_details

                target_fixed = not any(
                    code in result["codes_after"] for code in case["target_codes"]
                )
                result["ok"] = (
                    target_fixed
                    and current_step == "pass"
                    and is_usable_status(current_test.get("return_value"))
                )
                if not result["ok"] and not result["error"]:
                    result["error"] = (
                        f"not ok: step={current_step}, "
                        f"codes_after={result['codes_after']}, "
                        f"value={current_test.get('return_value')}"
                    )
                if DEBUG_TRACEBACK and not result["ok"]:
                    if (current_test or {}).get("traceback"):
                        print("\n[DEBUG] traceback (last run):")
                        print(current_test.get("traceback"))
                    print("\n[DEBUG] final source after repair:")
                    print(current_source)
                    print("[DEBUG] end\n")
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
                result["traceback"] = traceback.format_exc()
            finally:
                result["timing"] = clock.snapshot()
                clock.__exit__(None, None, None)

            results.append(result)
            mark = "OK" if result["ok"] else "NG"
            print(f"{mark}  {result['title']}")
            if result["error"]:
                print(f"  error: {result['error']}")
            print(
                f"  family={result.get('family')} before={result['step_before']} "
                f"after={result['step_after']} "
                f"rounds={result['rounds']} codes_after={result['codes_after']}"
            )
            timing = result.get("timing") or {}
            if timing:
                print(
                    f"  timing: total={timing.get('total_seconds')}s "
                    f"llm={timing.get('llm_seconds')}s "
                    f"repair={timing.get('repair_seconds')}s "
                    f"validation={timing.get('validation_seconds')}s"
                )

        failures = []
        for result in results:
            if result.get("ok"):
                continue
            failures.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "profile": PROFILE_ID,
                    "model": MODEL,
                    "repair_type": result.get("id"),
                    "repair_family": result.get("family"),
                    "repair_title": result.get("title"),
                    "validator_classification": {
                        "before_step": result.get("step_before"),
                        "before_codes": result.get("codes_before"),
                    },
                    "before_state": {
                        "source": next(
                            (
                                case.get("source")
                                for case in CASES
                                if case.get("id") == result.get("id")
                            ),
                            None,
                        ),
                        "test_result": result.get("initial_test_result"),
                        "validation": result.get("initial_validation"),
                    },
                    "generated_code": (
                        (result.get("last_repair_details") or {}).get("generated_code")
                    ),
                    "llm_output": (
                        (result.get("last_repair_details") or {}).get("llm_text")
                    ),
                    "after_execution": {
                        "source": result.get("final_source"),
                        "test_result": result.get("final_test_result"),
                    },
                    "final_validator": {
                        "step": result.get("step_after"),
                        "codes": result.get("codes_after"),
                        "validation": result.get("final_validation"),
                    },
                    "error": result.get("error"),
                    "repair_rounds": result.get("rounds"),
                    "failure_pattern": classify_failure_pattern(result),
                    "conditions": benchmark_conditions(),
                }
            )

        save_benchmark_run(results)
        if failures:
            save_failure_records(failures)

        passed = sum(1 for r in results if r.get("ok"))
        print(f"\n{passed}/{len(results)} cases passed.")
        return 0 if passed == len(results) else 1
    finally:
        with open(TOOL_PATH, "w", encoding="utf-8") as f:
            f.write(original_tool)
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            f.write(original_registry)
        stop_model(MODEL)


if __name__ == "__main__":
    raise SystemExit(main())
