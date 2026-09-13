"""One-goal observation: Semantic Need → System First → optional Grill → Tool → Evidence.

Uses existing ChatTaskOrchestrator / Capability Resolution / Help describe /
Registry execution / Grill Tool Bridge path gate. Does not modify Production.
Does not add keywords, capabilities, tools, or Help behavior.
"""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from ai_tool.chat_interface.capability_resolution import required_capabilities
from ai_tool.chat_interface.concept_resolution import load_workspace_index
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from research.grill_observation_v0.grill_tool_bridge_v0.bridge import (
    ALLOWED_TOOLS,
    DEFAULT_SEARCH_PATH,
    _remap_rel,
    execute_exposed_tool,
)
from research.grill_observation_v0.medium_task_reality_v0.apply_patch import strip_think
from research.grill_observation_v0.natural_exit_v0.run import call_freeform
from tools.file.workspace._paths import path_error
from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)
from tools.system.tool_contract import canonical_tool_name, list_agent_visible_tools
from tools.system.tool_result_contract import normalize_tool_result

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

GOAL = "gridを検索して、その内容を要約してほしい。"
INITIAL_STATE = "まだ何も調査していない。"

# Harness stop only. Not a Production rule.
MAX_LLM_CALLS = 8
MAX_SYSTEM_RESOLVES = 8
MAX_GRILLS_PER_NEED = 2
MAX_TOOL_EXECS = 4

FORBIDDEN_IN_QWEN = (
    "search_files",
    "read_file",
    "workspace_file_search",
    "workspace_file_read",
    "/h",
    "Help API",
    "AgentToolDiscoveryAdapter",
    "Capability Index",
)

NEED_QUESTION = """このGoalを満たすために、
今の時点で次に満たす必要があることを1つだけ答えてください。

具体的なTool名、関数名、Capability ID、実装方法ではなく、
「何を知る・確認する・行う必要があるか」
という意味レベルで答えてください。

一度に1つだけ答えてください。
"""

GRILL_UNRESOLVED_QUESTION = """このNeedを実際のActionへ進めるために、
次に何を知る・確認する・行う必要があるかを
1つだけ具体化してください。

具体的なTool名、関数名、Capability ID、実装方法ではなく、
意味レベルで、一度に1つだけ答えてください。
"""

GRILL_PARTIAL_QUESTION = """現在のNeedを実行可能にするために、
まだ不足していることを1つだけ具体化してください。

具体的なTool名、関数名、Capability ID、実装方法ではなく、
意味レベルで、一度に1つだけ答えてください。
"""

AFTER_EVIDENCE_QUESTION = """未確認のことは書かないでください。

取得済みEvidenceだけでGoalに答えられる場合は、
次の不足ではなくGoalへの回答を書いてください。

まだ足りない場合は、
Goal達成まで、次に不足していることを1つだけ答えてください。

具体的なTool名、関数名、Capability ID、実装方法ではなく、
意味レベルで答えてください。
"""


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assert_qwen_prompt_clean(text: str) -> None:
    for token in FORBIDDEN_IN_QWEN:
        if token in text:
            raise RuntimeError(f"forbidden token in Qwen prompt: {token}")


def system_request(*, goal: str, state: str, need: str) -> str:
    return (
        f"Goal:\n{goal}\n\n"
        f"Current State:\n{state}\n\n"
        f"Next need:\n{need}\n"
    )


def qwen_user(*, goal: str, state: str, extra: str, question: str) -> str:
    parts = [f"Goal:\n{goal}", f"Current State:\n{state}"]
    if extra:
        parts.append(extra)
    parts.append(f"質問:\n{question}")
    return "\n\n".join(parts) + "\n"


def classify_research_label(
    *,
    caps: list[str],
    resolutions: list[dict[str, Any]],
    expectation: dict[str, Any],
) -> str:
    """Observation labels only. Reads existing System outputs; does not invent mapping."""
    generated = bool(expectation.get("generated"))
    tool = expectation.get("expected_tool")
    args = expectation.get("expected_arguments")
    if generated and tool and isinstance(args, dict) and args:
        return "RESOLVED"
    if not caps:
        return "UNRESOLVED"
    selected = [row.get("selected_tool") for row in resolutions if row.get("selected_tool")]
    if selected or any(row.get("required_capability") for row in resolutions):
        return "PARTIAL"
    return "UNRESOLVED"


def compact_evidence(result: Any) -> str:
    if not isinstance(result, dict):
        return str(result)[:4000]
    if result.get("matches"):
        lines = []
        for item in result["matches"][:30]:
            if not isinstance(item, dict):
                continue
            lines.append(f"{item.get('path')}:{item.get('line')}: {item.get('text')}")
        return "観測ヒット:\n" + ("\n".join(lines) if lines else "(0件)")
    if result.get("lines"):
        path = result.get("path") or ""
        body = "\n".join(
            f"{item.get('line')}: {item.get('text')}"
            for item in result["lines"][:80]
            if isinstance(item, dict)
        )
        return f"観測ファイル {path}:\n{body}"
    if result.get("entries"):
        return "観測一覧:\n" + json.dumps(result.get("entries")[:40], ensure_ascii=False)
    return json.dumps(
        {k: result.get(k) for k in ("ok", "status", "error", "path", "message") if k in result},
        ensure_ascii=False,
    )[:4000]


def execute_system_action(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool in ALLOWED_TOOLS:
        return execute_exposed_tool(tool, arguments)
    args = dict(arguments)
    if "path" in args or tool == "list_files":
        raw = args.get("path", ".")
        if raw is None or str(raw).strip() in ("", "."):
            args["path"] = DEFAULT_SEARCH_PATH
        else:
            mapped = _remap_rel(str(raw))
            if mapped is None:
                err = path_error(
                    "experiment workspace 外への実行は禁止です",
                    code="experiment_boundary",
                    path=raw,
                )
                return {
                    "tool_name": tool,
                    "requested_arguments": dict(arguments),
                    "executed_arguments": args,
                    "denied": True,
                    "record": None,
                    "result": err,
                    "normalized": normalize_tool_result(err, tool_name=tool),
                }
            args["path"] = mapped
    rec = execute_registry_tool(tool, args)
    result = rec.result if isinstance(rec.result, dict) else {"ok": rec.ok, "result": rec.result}
    return {
        "tool_name": tool,
        "requested_arguments": dict(arguments),
        "executed_arguments": args,
        "denied": False,
        "record": rec.to_dict(),
        "result": result,
        "normalized": normalize_tool_result(result, tool_name=tool),
    }


def system_resolve(request_text: str) -> dict[str, Any]:
    tools = list_agent_visible_tools()
    registry = load_registry_tools()
    index = load_workspace_index()
    orch = ChatTaskOrchestrator("system_first_obs", request_text)
    orch.initialize()
    orch.configure_tool_expectation(tools, registry_tools=registry)
    caps = required_capabilities(
        orch.task,
        expectation=orch.tool_expectation,
        capability_index=index,
        registry_tools=registry,
    )
    resolutions = [row.as_dict() for row in orch._task_resolutions()]
    expectation = asdict(orch.tool_expectation)
    label = classify_research_label(
        caps=caps, resolutions=resolutions, expectation=expectation
    )
    action = None
    if label == "RESOLVED":
        action = {
            "tool": expectation.get("expected_tool"),
            "arguments": dict(expectation.get("expected_arguments") or {}),
        }
    return {
        "request_text": request_text,
        "required_capabilities": caps,
        "resolutions": resolutions,
        "tool_expectation": expectation,
        "label": label,
        "action": action,
    }


def looks_like_goal_answer(text: str, *, has_evidence: bool) -> bool:
    if not has_evidence:
        return False
    body = strip_think(text)
    needish = bool(
        re.search(r"(必要がある|次に(満たす|不足)|まだ.{0,12}足り)", body)
    )
    talks_grid = bool(re.search(r"grid|Grid|グリッド", body, re.I))
    longish = len(body) >= 60
    if talks_grid and longish and not needish:
        return True
    if re.search(r"(要約すると|Goalへの回答|確認できた内容は)", body) and talks_grid:
        return True
    return False


def main() -> int:
    started = time.perf_counter()
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = utc_id()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    def llm(user: str, label: str) -> dict[str, Any]:
        assert_qwen_prompt_clean(user)
        call = call_freeform(
            model=provider,
            messages=[{"role": "user", "content": user}],
            num_ctx=int(profile.get("context_limit") or 8192),
            num_predict=int(profile.get("num_predict") or 2048),
            temperature=float(
                profile.get("temperature") if profile.get("temperature") is not None else 0
            ),
            timeout_s=int(profile.get("hard_timeout_seconds") or 300),
            label=label,
        )
        raw = str(call.get("raw_text") or "")
        return {
            "label": label,
            "prompt": user,
            "raw": raw,
            "visible": strip_think(raw),
            "elapsed_s": call.get("elapsed_s"),
            "error": call.get("error"),
            "model": provider,
        }

    goal = GOAL
    state = INITIAL_STATE
    need = ""
    evidence_blobs: list[str] = []
    timeline: list[dict[str, Any]] = []
    llm_calls = 0
    system_resolves = 0
    tool_execs = 0
    grills_this_need = 0
    stop_reason = None
    final_answer = ""
    last_label = None
    unresolved_streak = 0

    step = 0

    def save_step(name: str, payload: dict[str, Any]) -> None:
        dump(run_dir / "steps" / f"{step:02d}_{name}.json", payload)

    while True:
        if llm_calls >= MAX_LLM_CALLS or system_resolves >= MAX_SYSTEM_RESOLVES:
            stop_reason = "B"
            timeline.append({"event": "stop", "reason": "harness_cap", "stop": stop_reason})
            break

        step += 1
        if not need:
            user = qwen_user(goal=goal, state=state, extra="", question=NEED_QUESTION)
            llm_calls += 1
            got = llm(user, f"need_{step}")
            write_text(run_dir / "steps" / f"{step:02d}_need_prompt.txt", user)
            write_text(run_dir / "steps" / f"{step:02d}_need_raw.txt", got["raw"])
            need = got["visible"].strip()
            timeline.append(
                {
                    "event": "semantic_need",
                    "step": step,
                    "need": need,
                    "elapsed_s": got["elapsed_s"],
                    "error": got["error"],
                }
            )
            save_step("need", got)
            if got["error"] or not need:
                stop_reason = "B"
                timeline.append({"event": "stop", "reason": "need_failed", "stop": stop_reason})
                break
            continue

        step += 1
        system_resolves += 1
        request_text = system_request(goal=goal, state=state, need=need)
        resolution = system_resolve(request_text)
        last_label = resolution["label"]
        timeline.append(
            {
                "event": "system_resolution",
                "step": step,
                "label": resolution["label"],
                "required_capabilities": resolution["required_capabilities"],
                "selected_tools": [
                    row.get("selected_tool")
                    for row in resolution["resolutions"]
                    if row.get("selected_tool")
                ],
                "next_actions": [
                    row.get("next_action")
                    for row in resolution["resolutions"]
                    if row.get("next_action")
                ],
                "tool_expectation": resolution["tool_expectation"],
                "action": resolution["action"],
            }
        )
        save_step("system", resolution)

        if resolution["label"] == "RESOLVED":
            unresolved_streak = 0
            grills_this_need = 0
            action = resolution["action"] or {}
            tool = str(action.get("tool") or "")
            arguments = dict(action.get("arguments") or {})
            if not tool:
                stop_reason = "C"
                timeline.append({"event": "stop", "reason": "resolved_without_tool", "stop": stop_reason})
                break
            if tool_execs >= MAX_TOOL_EXECS:
                stop_reason = "B"
                timeline.append({"event": "stop", "reason": "tool_cap", "stop": stop_reason})
                break
            step += 1
            tool_execs += 1
            executed = execute_system_action(tool, arguments)
            evidence_text = compact_evidence(executed.get("result"))
            evidence_blobs.append(evidence_text)
            state = (
                state
                + "\n\n確認済みEvidence:\n"
                + evidence_text
            )
            timeline.append(
                {
                    "event": "tool_execution",
                    "step": step,
                    "tool": tool,
                    "requested_arguments": executed.get("requested_arguments"),
                    "executed_arguments": executed.get("executed_arguments"),
                    "denied": executed.get("denied"),
                    "ok": bool((executed.get("normalized") or {}).get("ok")),
                    "evidence_for_qwen": evidence_text,
                }
            )
            save_step(
                "tool",
                {
                    "tool": tool,
                    "executed": {
                        k: executed.get(k)
                        for k in (
                            "requested_arguments",
                            "executed_arguments",
                            "denied",
                            "result",
                            "normalized",
                        )
                    },
                    "evidence_for_qwen": evidence_text,
                },
            )
            if executed.get("denied") or not (executed.get("normalized") or {}).get("ok"):
                stop_reason = "B"
                timeline.append({"event": "stop", "reason": "tool_failed", "stop": stop_reason})
                break

            step += 1
            extra = "確認済みEvidence:\n" + "\n\n".join(evidence_blobs)
            user = qwen_user(goal=goal, state=state, extra=extra, question=AFTER_EVIDENCE_QUESTION)
            llm_calls += 1
            got = llm(user, f"after_evidence_{step}")
            write_text(run_dir / "steps" / f"{step:02d}_after_evidence_prompt.txt", user)
            write_text(run_dir / "steps" / f"{step:02d}_after_evidence_raw.txt", got["raw"])
            visible = got["visible"].strip()
            timeline.append(
                {
                    "event": "after_evidence_qwen",
                    "step": step,
                    "visible": visible,
                    "elapsed_s": got["elapsed_s"],
                    "error": got["error"],
                }
            )
            save_step("after_evidence", got)
            if looks_like_goal_answer(visible, has_evidence=True):
                final_answer = visible
                stop_reason = "A"
                timeline.append({"event": "stop", "reason": "goal_answer", "stop": stop_reason})
                break
            need = visible
            grills_this_need = 0
            continue

        if grills_this_need >= MAX_GRILLS_PER_NEED:
            stop_reason = "B"
            timeline.append(
                {
                    "event": "stop",
                    "reason": "grill_retry_exhausted",
                    "stop": stop_reason,
                    "label": resolution["label"],
                }
            )
            break

        step += 1
        extra = f"現在のNeed:\n{need}"
        question = (
            GRILL_PARTIAL_QUESTION
            if resolution["label"] == "PARTIAL"
            else GRILL_UNRESOLVED_QUESTION
        )
        user = qwen_user(goal=goal, state=state, extra=extra, question=question)
        llm_calls += 1
        grills_this_need += 1
        got = llm(user, f"grill_{step}")
        write_text(run_dir / "steps" / f"{step:02d}_grill_prompt.txt", user)
        write_text(run_dir / "steps" / f"{step:02d}_grill_raw.txt", got["raw"])
        grill_answer = got["visible"].strip()
        state = state + "\n\n具体化:\n" + grill_answer
        timeline.append(
            {
                "event": "grill",
                "step": step,
                "kind": resolution["label"],
                "answer": grill_answer,
                "elapsed_s": got["elapsed_s"],
                "error": got["error"],
            }
        )
        save_step("grill", {**got, "kind": resolution["label"]})
        if resolution["label"] == "UNRESOLVED":
            unresolved_streak += 1
        if got["error"] or not grill_answer:
            stop_reason = "B"
            timeline.append({"event": "stop", "reason": "grill_failed", "stop": stop_reason})
            break
        # Keep the same Need; System retries with added State. No new conversion.
        continue

    elapsed = round(time.perf_counter() - started, 3)
    if stop_reason == "A":
        verdict = "PASS"
        verdict_reason = (
            "System First のあと、必要なときだけ Grill し、"
            "System が選んだ Tool を実行して Evidence を Qwen に戻し、Goal 回答に到達した。"
        )
    elif any(item.get("event") == "system_resolution" for item in timeline):
        verdict = "PARTIAL"
        verdict_reason = (
            "Need → System First → 必要時 Grill の構造は動いたが、"
            f"停止は {stop_reason}。最終 System 判定は {last_label}。"
        )
    else:
        verdict = "FAIL"
        verdict_reason = "System First / Grill Retry のループを構成できなかった。"

    record = {
        "experiment": "system_first_loop_v0",
        "run_id": run_id,
        "model_id": model_id,
        "model": provider,
        "goal": goal,
        "initial_state": INITIAL_STATE,
        "workspace": DEFAULT_SEARCH_PATH,
        "elapsed_s": elapsed,
        "stop_reason": stop_reason,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "final_answer": final_answer,
        "final_state": state,
        "final_need": need,
        "llm_calls": llm_calls,
        "system_resolves": system_resolves,
        "tool_execs": tool_execs,
        "timeline": timeline,
        "note": (
            "Observation harness only. Production / Help / Registry / Classifier unchanged. "
            "Research labels RESOLVED/PARTIAL/UNRESOLVED are not a Production contract."
        ),
    }
    dump(run_dir / "run.json", record)
    dump(run_dir / "timeline.json", timeline)
    write_text(run_dir / "final_state.txt", state)
    write_text(run_dir / "final_answer.txt", final_answer)
    print(json.dumps({"run_id": run_id, "verdict": verdict, "stop": stop_reason}, ensure_ascii=False), flush=True)
    print(f"RUN {run_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
