"""
Failure 分析能力の実験ハーネス。FA 実装・Schema・本番経路の変更ではない。

既存の test_tool / validate_tool_result / chat を読むだけ使う。
repair_tool / first_pipeline_step / MATERIALS / Repair Loop は使わない。
cpu_status.py は repair_benchmark と同様に一時書換し、終了時に戻す。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from tests.fixtures import broken_tools
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.tool_builder.test import test_tool
from tools.system.tool_builder.validate.result import validate_tool_result


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
TOOL_PATH = "tools/system/cpu/cpu_status.py"
PROPOSAL = {
    "name": "cpu_status",
    "module": "tools.system.cpu.cpu_status",
    "function": "cpu_status",
    "output": ["status"],
}

SOURCE_ATTRIBUTE_ERROR = """
def cpu_status():
    value = '28'
    return {'status': value.load_percentage}
"""

CASES = [
    {
        "id": "index_error",
        "title": "既存 fixture: IndexError",
        "source": broken_tools.SOURCE_INDEX_ERROR,
        "research": None,
    },
    {
        "id": "unparsed_output",
        "title": "既存 fixture: 例外なし・生出力",
        "source": broken_tools.SOURCE_UNPARSED,
        "research": None,
    },
    {
        "id": "attribute_error",
        "title": "実験専用 fixture: AttributeError（本番 CASES には無い）",
        "source": SOURCE_ATTRIBUTE_ERROR,
        "research": None,
    },
]

OUT_DIR = Path("research/llm_benchmarks/fa_capability_experiment_results")

SYSTEM = (
    "You analyze one software test failure.\n"
    "Use only facts in the messages. Do not invent missing facts.\n"
    "You may freely request any additional information you need. "
    "Do not wait for the experimenter to suggest what to ask.\n"
    "If you cannot safely patch, say so and do not invent a patch.\n"
    "Do not classify the case as Repair, Research, or Environment.\n"
)

QUESTIONS = """
Answer:
1. What happened?
2. What is known from the given information?
3. What is still unknown?
4. What additional information do you want in order to solve this?
5. Why do you need each item?
6. How would you obtain each item? Be specific. Do not wait for a menu of methods.
7. Can you safely patch with only the current information?
8. If you patched, what would the approach be? If you would not patch, why?
"""

INVESTIGATE = """
You listed additional information you want.
For each item, describe concretely how you would obtain it
(what to inspect, where, what command or search, what to execute).
Do not wait for the experimenter to propose methods.
"""

UPDATE = """
Update your analysis using the newly added information.
Answer the same 8 questions again.
Say what changed from your previous answers, including any hypothesis you withdraw.
"""

ASK_PATCH = """
If you now judge that a patch is safe, give:
- the patch approach
- the full replacement source for the tool function
- which given facts you used
- remaining uncertainty
If you would not patch, say why, and what you still need or whether you want human help.
"""

RETEST = """
The patch (or latest source) was executed. Here is the new test outcome.
Re-analyze. Note whether this is success, the same failure, or a new failure.
Say whether you would keep the same approach or change it.
If you would patch again, give the new full source. If you would stop or ask for help, say so.
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_source(source):
    Path(TOOL_PATH).write_text(source.strip() + "\n", encoding="utf-8")


def _minimal_failure(test_result):
    packet = {
        "tool_name": test_result.get("tool_name"),
        "status": test_result.get("status"),
        "result": test_result.get("result"),
    }
    if test_result.get("error_type") not in (None, ""):
        packet["error_type"] = test_result.get("error_type")
    if test_result.get("error") not in (None, ""):
        packet["error"] = test_result.get("error")
    if "error_type" not in packet and "error" not in packet:
        packet["return_value"] = test_result.get("return_value")
        packet["note"] = (
            "exception fields were empty; return_value included as the only "
            "test-result symptom"
        )
    return packet


def _vicinity(source, test_result):
    tb = test_result.get("traceback") or ""
    match = re.search(r"cpu_status\.py\", line (\d+)", tb)
    if not match:
        return None
    line_no = int(match.group(1))
    lines = source.strip().splitlines()
    start = max(0, line_no - 6)
    end = min(len(lines), line_no + 5)
    return {
        "traceback_line": line_no,
        "snippet": "\n".join(
            f"{i + 1}: {lines[i]}" for i in range(start, end)
        ),
    }


def _validation_packet(validation):
    items = []
    for item in validation.get("warning_items") or []:
        items.append(
            {
                "code": item.get("code"),
                "message": item.get("message"),
                "fix": item.get("fix"),
                "needs_research_findings": item.get("needs_research_findings"),
                "required_information": item.get("required_information"),
                "evidence": item.get("evidence"),
            }
        )
    return {
        "status": validation.get("status"),
        "errors": validation.get("errors") or [],
        "warning_items": items,
        "missing_outputs": validation.get("missing_outputs") or [],
    }


def _available_packets(case, test_result, validation, source):
    env = None
    try:
        from research.llm_benchmarks.environment_benchmark import (
            verified_environment,
        )

        env = verified_environment()
    except Exception as exc:
        env = {"error": f"{type(exc).__name__}:{exc}"}
    return {
        "traceback": test_result.get("traceback"),
        "source": source.strip(),
        "vicinity": _vicinity(source, test_result),
        "validation": _validation_packet(validation),
        "return_value": test_result.get("return_value"),
        "module": test_result.get("module"),
        "function": test_result.get("function"),
        "blocked_by_safety_gate": test_result.get("blocked_by_safety_gate"),
        "phase_b_code_safety": test_result.get("phase_b_code_safety"),
        "research": case.get("research"),
        "verified_environment": env,
        "sys_executable": None,
        "gpu": None,
    }


def _requested_keys(text):
    """実験用の照合。FA の正式分類ではない。"""
    t = (text or "").lower()
    keys = []
    pairs = [
        ("traceback", ("traceback", "stack trace", "stacktrace", "トレース")),
        ("source", ("source code", "full source", "ソース", "実装コード", "the code")),
        ("vicinity", ("nearby", "surrounding", "該当", "付近", "around the line")),
        ("validation", ("validation", "warning", "validator", "検査", "警告")),
        ("return_value", ("return_value", "return value", "戻り値")),
        ("module", ("module", "function", "モジュール")),
        ("verified_environment", ("environment", "python version", "venv", "cwd", "環境")),
        ("sys_executable", ("sys.executable", "which python", "実行 python")),
        ("gpu", ("nvidia-smi", "cuda", "gpu", "vram")),
        ("research", ("finding", "research", "command")),
        ("web", ("web search", "google", "search the web", "ウェブ", "検索")),
        ("pdf", ("pdf", "manual", "マニュアル", "ドキュメント")),
        ("repository", ("repository", "definition", "import", "定義", "リポジトリ")),
        ("human", ("human", "help", "確認", "人間")),
    ]
    for key, needles in pairs:
        if any(n in t for n in needles):
            keys.append(key)
    return keys


def _fulfill(keys, available):
    given = {}
    missing = []
    for key in keys:
        if key in ("web", "pdf", "repository", "human"):
            missing.append(key)
            continue
        if key == "sys_executable":
            import sys

            given[key] = sys.executable
            continue
        if key == "gpu":
            try:
                from tools.system.gpu.nvidia_smi import query_gpu_status

                given[key] = query_gpu_status()
            except Exception as exc:
                given[key] = {"error": f"{type(exc).__name__}:{exc}"}
            continue
        value = available.get(key)
        if value in (None, "", {}, []):
            missing.append(key)
        else:
            given[key] = value
    return given, missing


def _extract_source(text):
    if not text:
        return None
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, flags=re.S)
    for block in blocks:
        if "def cpu_status" in block:
            return block.strip() + "\n"
    start = text.find("def cpu_status")
    if start != -1:
        return text[start:].strip() + "\n"
    return None


def _ask(messages, user_text):
    messages.append({"role": "user", "content": user_text})
    try:
        response = chat(model=MODEL, messages=messages)
        text = (response.message.content or "").strip()
        err = None
    except LLMTimeoutError as exc:
        text = ""
        err = str(exc)
    messages.append({"role": "assistant", "content": text or f"[timeout] {err}"})
    return {
        "at": _now(),
        "user": user_text,
        "assistant": text,
        "timeout": err,
        "requested_keys_heuristic": _requested_keys(text),
        "extracted_source": _extract_source(text),
    }


def _dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_case(case, original_tool):
    record = {
        "id": case["id"],
        "title": case["title"],
        "model": MODEL,
        "profile_id": PROFILE_ID,
        "turns": [],
        "notes": [],
    }
    _write_source(case["source"])
    test_result = test_tool("cpu_status")
    validation = validate_tool_result(
        PROPOSAL,
        test_result,
        implementation={},
        research_result=case.get("research"),
        source=case["source"],
    )
    available = _available_packets(case, test_result, validation, case["source"])
    record["initial_test_result"] = test_result
    record["initial_validation"] = _validation_packet(validation)
    record["minimal_failure"] = _minimal_failure(test_result)

    messages = [{"role": "system", "content": SYSTEM}]
    turn1 = _ask(
        messages,
        "This is a test failure with minimal information.\n"
        + json.dumps(record["minimal_failure"], ensure_ascii=False, indent=2)
        + "\n"
        + QUESTIONS,
    )
    record["turns"].append({"name": "minimal", "source_of_info": "experimenter_minimal", **turn1})

    turn2 = _ask(messages, INVESTIGATE)
    record["turns"].append(
        {"name": "how_to_investigate", "source_of_info": "none_added", **turn2}
    )

    llm_keys = []
    for turn in record["turns"]:
        for key in turn.get("requested_keys_heuristic") or []:
            if key not in llm_keys:
                llm_keys.append(key)
    record["llm_requested_keys_heuristic"] = llm_keys
    given, unfulfilled = _fulfill(llm_keys, available)
    record["fulfilled_because_llm_asked"] = list(given)
    record["asked_but_not_fulfilled"] = unfulfilled
    already = set(given)

    asked_payload = {
        "information_you_asked_for_that_this_experiment_can_provide": given,
        "you_asked_for_these_but_this_run_did_not_execute_them": unfulfilled,
    }
    turn3 = _ask(
        messages,
        "Only information you asked for (mapped by a heuristic, not a spec) "
        "is below. Nothing extra is added in this message.\n"
        + json.dumps(asked_payload, ensure_ascii=False, indent=2)[:3000]
        + "\n"
        + UPDATE,
    )
    record["turns"].append(
        {
            "name": "after_llm_requested",
            "source_of_info": "llm_asked",
            **turn3,
        }
    )

    staged = [
        ("traceback", "traceback", available.get("traceback")),
        ("source", "source", available.get("source")),
        ("vicinity", "vicinity", available.get("vicinity")),
        ("validation", "validation", available.get("validation")),
    ]
    experimenter_added = []
    for name, key, value in staged:
        if key in already:
            record["notes"].append(f"skip_stage_{name}_already_given_because_llm_asked")
            continue
        if value in (None, "", {}, []):
            record["notes"].append(f"skip_stage_{name}_not_present_on_this_failure")
            continue
        experimenter_added.append(name)
        stage_turn = _ask(
            messages,
            "The experimenter now adds information you did not necessarily request. "
            f"This packet is labeled experimenter_added:{name}.\n"
            + json.dumps({name: value}, ensure_ascii=False, indent=2)[:3000]
            + "\n"
            + UPDATE,
        )
        record["turns"].append(
            {
                "name": f"experimenter_added_{name}",
                "source_of_info": "experimenter_added",
                **stage_turn,
            }
        )
        already.add(key)
    record["experimenter_added_unasked"] = experimenter_added

    turn4 = _ask(messages, ASK_PATCH)
    record["turns"].append({"name": "ask_patch", "source_of_info": "none_added", **turn4})

    patch = turn4.get("extracted_source") or turn3.get("extracted_source")
    record["patch_source"] = patch
    if patch:
        _write_source(patch)
        retest = test_tool("cpu_status")
        re_validation = validate_tool_result(
            PROPOSAL,
            retest,
            implementation={},
            source=patch,
        )
        record["retest"] = {
            "test_result": retest,
            "validation": _validation_packet(re_validation),
        }
        retest_min = _minimal_failure(retest)
        extra = {}
        if retest.get("traceback"):
            extra["traceback"] = retest.get("traceback")
        extra["return_value"] = retest.get("return_value")
        extra["validation"] = _validation_packet(re_validation)
        turn5 = _ask(
            messages,
            RETEST
            + "\n"
            + json.dumps({"minimal": retest_min, "extra": extra}, ensure_ascii=False, indent=2)[:3500],
        )
        record["turns"].append(
            {"name": "after_retest", "source_of_info": "new_test", **turn5}
        )
        second = turn5.get("extracted_source")
        record["second_patch_source"] = second
        record["same_patch_repeated"] = bool(second and second.strip() == patch.strip())
        if second and second.strip() != patch.strip():
            _write_source(second)
            retest2 = test_tool("cpu_status")
            record["retest2"] = {
                "test_result": retest2,
                "validation": _validation_packet(
                    validate_tool_result(
                        PROPOSAL, retest2, implementation={}, source=second
                    )
                ),
            }
            turn6 = _ask(
                messages,
                RETEST
                + "\n"
                + json.dumps(
                    {
                        "minimal": _minimal_failure(retest2),
                        "return_value": retest2.get("return_value"),
                        "traceback": retest2.get("traceback"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )[:3000],
            )
            record["turns"].append(
                {"name": "after_second_retest", "source_of_info": "new_test", **turn6}
            )
    else:
        record["notes"].append("no_cpu_status_source_extracted")

    _write_source(original_tool)
    return record


def main():
    wanted = os.environ.get("AI_AGENT_TEST_CASE_ID", "").strip()
    cases = [c for c in CASES if (not wanted or c["id"] == wanted)]
    if wanted and not cases:
        raise SystemExit(f"unknown case {wanted}")
    original = Path(TOOL_PATH).read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / stamp
    run = {
        "note": "FA capability experiment. Not an FA spec. Not a production path.",
        "at": _now(),
        "model": MODEL,
        "profile_id": PROFILE_ID,
        "cases": [],
    }
    try:
        for case in cases:
            print(f"CASE {case['id']} ...", flush=True)
            record = run_case(case, original)
            run["cases"].append(record)
            _dump(out / f"{case['id']}.json", record)
            print(f"  turns={len(record['turns'])} patch={bool(record.get('patch_source'))}", flush=True)
    finally:
        Path(TOOL_PATH).write_text(original, encoding="utf-8")
        stop_model(MODEL)
    _dump(out / "run.json", run)
    print(f"wrote {out / 'run.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
