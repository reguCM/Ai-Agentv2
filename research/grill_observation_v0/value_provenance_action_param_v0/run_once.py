"""value_provenance 比較: Task未解決と Action 入力 Parameter を区別して伝える。

A/B の既存 Run は read-only。Validator / Grounding 文面は変更しない。
Production / `_search_query` / Tool 実行はしない。1回だけ。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.grill_observation_v0.grill_system_retry_v0.run_once import GRILL_GROUNDING
from research.grill_observation_v0.medium_task_reality_v0.apply_patch import strip_think
from research.grill_observation_v0.natural_exit_v0.run import call_freeform
from research.grill_observation_v0.system_first_loop_v0.run_once import assert_qwen_prompt_clean
from research.grill_observation_v0.value_provenance_v0.run_once import (
    GOAL,
    NEED,
    OUTPUT_SHAPE,
    START,
    STATE,
    classify_verdict,
    dump,
    grounding_observation,
    normalize_proposal,
    parse_proposal,
    research_validator,
    utc_id,
    write_text,
)
from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
RUN_A = (
    ROOT
    / "research/grill_observation_v0/value_provenance_v0/runs/20260909T081235Z"
)
RUN_B = (
    ROOT
    / "research/grill_observation_v0/value_provenance_slot_v0/runs/20260909T081755Z"
)

ASK = """今回求めているのは、
Goalの最終回答や、
調査によってこれから判明するgridの構造・内容ではありません。

すでに選択された次の調査Actionを実行するために必要な
入力Parameterが1つ不足しています。

不足しているParameterの役割は
『検索対象を表す文字列』です。

確認済みGoal / Stateだけから
このAction入力値を決められる場合は、
値とその根拠を返してください。

確認済み情報だけでは決められない場合は
UNRESOLVEDを返してください。
"""

SYSTEM_FACTS_FOR_AI = """検索系の処理までは選択済みである。
次Actionを実行するための入力値が1つ不足している。
その入力値の役割は『検索対象を表す文字列』である。
"""

SYSTEM_CONFIRMED_FOR_VALIDATOR = (
    "検索系の処理までは選択済みである。"
    "次Actionを実行するための入力値が1つ不足している。"
    "その入力値の役割は『検索対象を表す文字列』である。"
)


def load_obs(path: Path) -> dict[str, Any]:
    return json.loads((path / "observation.json").read_text(encoding="utf-8"))


def row_from_obs(obs: dict[str, Any]) -> dict[str, Any]:
    grounding = obs.get("grounding") or {}
    return {
        "status": (obs.get("parsed_proposal") or {}).get("status") or obs.get("source_type") and obs.get("parsed_proposal"),
        "value": obs.get("value"),
        "source_type": obs.get("source_type"),
        "source_text": obs.get("source_text"),
        "reason": obs.get("reason"),
        "grounding_violation": bool(grounding.get("unconfirmed_example_markers_near_claim"))
        or bool(grounding.get("value_absent_from_all_confirmed_sources")),
        "validator": (obs.get("validator") or {}).get("result"),
        "verdict": obs.get("verdict"),
    }


def distinction_trace(reason: str | None, status: str | None, value: str | None) -> dict[str, Any]:
    text = str(reason or "")
    taskish = bool(re.search(r"(構造|内容|最終回答|要約)", text))
    actionish = bool(re.search(r"(Action|入力|Parameter|検索対象)", text))
    proposed_from_goal = status == "PROPOSED" and bool(value)
    return {
        "reason_mentions_task_level_gap": taskish,
        "reason_mentions_action_input": actionish,
        "proposed_action_input_value": proposed_from_goal,
        "note": (
            "観察のみ。Validator の意味判断ではない。"
        ),
    }


def main() -> int:
    started = time.perf_counter()
    obs_a = load_obs(RUN_A)
    obs_b = load_obs(RUN_B)
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    if provider != "qwen3:14b":
        model_id = "qwen3_14b"
        provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = utc_id()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt = (
        f"Goal:\n{GOAL}\n\n"
        f"Current State:\n{STATE}\n\n"
        f"現在の未解決点:\n{NEED}\n\n"
        f"System の事実:\n{SYSTEM_FACTS_FOR_AI}\n"
        f"依頼:\n{ASK}\n"
        f"{GRILL_GROUNDING}\n"
        f"{OUTPUT_SHAPE}"
    )
    assert_qwen_prompt_clean(prompt)
    write_text(run_dir / "01_prompt.txt", prompt)

    call = call_freeform(
        model=provider,
        messages=[{"role": "user", "content": prompt}],
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(
            profile.get("temperature") if profile.get("temperature") is not None else 0
        ),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label="value_provenance_action_param",
    )
    raw = str(call.get("raw_text") or "")
    visible = strip_think(raw)
    write_text(run_dir / "02_raw.txt", raw)
    write_text(run_dir / "02_visible.txt", visible)

    parsed, parse_error = parse_proposal(visible)
    proposal = normalize_proposal(parsed)
    grounding = grounding_observation(
        proposal,
        goal=GOAL,
        state=STATE,
        system_confirmed=SYSTEM_CONFIRMED_FOR_VALIDATOR,
    )
    validation = research_validator(
        proposal,
        goal=GOAL,
        state=STATE,
        system_confirmed=SYSTEM_CONFIRMED_FOR_VALIDATOR,
    )
    verdict, verdict_reason = classify_verdict(
        parse_error=parse_error,
        proposal=proposal,
        grounding=grounding,
        validation=validation,
    )
    elapsed = round(time.perf_counter() - started, 3)

    row_a = row_from_obs(obs_a)
    row_a["status"] = (obs_a.get("parsed_proposal") or {}).get("status")
    row_b = row_from_obs(obs_b)
    row_b["status"] = (obs_b.get("parsed_proposal") or {}).get("status")
    row_c = {
        "status": proposal.get("status"),
        "value": proposal.get("value"),
        "source_type": proposal.get("source_type"),
        "source_text": proposal.get("source_text"),
        "reason": proposal.get("reason"),
        "grounding_violation": bool(grounding.get("unconfirmed_example_markers_near_claim"))
        or bool(grounding.get("value_absent_from_all_confirmed_sources")),
        "validator": validation.get("result"),
        "verdict": verdict,
    }
    dist_a = distinction_trace(row_a.get("reason"), row_a.get("status"), row_a.get("value"))
    dist_b = distinction_trace(row_b.get("reason"), row_b.get("status"), row_b.get("value"))
    dist_c = distinction_trace(row_c.get("reason"), row_c.get("status"), row_c.get("value"))

    comparison = {
        "A_value_provenance_v0": {**row_a, "run_id": obs_a.get("run_id"), "distinction_trace": dist_a},
        "B_value_provenance_slot_v0": {**row_b, "run_id": obs_b.get("run_id"), "distinction_trace": dist_b},
        "C_this_run": {**row_c, "run_id": run_id, "distinction_trace": dist_c},
        "prompt_delta_from_B": (
            "Task-level（Goal最終回答 / これから判明する構造・内容）と、"
            "既選択の次調査Actionの入力Parameterを区別する説明だけを追加。"
            "正解値・内部引数名・Tool名は未記載。Grounding文面とValidatorは未変更。"
        ),
        "changed_from_B": {
            key: {
                "B": row_b.get(key),
                "C": row_c.get(key),
                "changed": row_b.get(key) != row_c.get(key),
            }
            for key in (
                "status",
                "value",
                "source_type",
                "source_text",
                "reason",
                "grounding_violation",
                "validator",
                "verdict",
            )
        },
    }

    observation = {
        "experiment": "value_provenance_action_param_v0",
        "run_id": run_id,
        "model": provider,
        "production_modified": False,
        "search_query_parser_modified": False,
        "tool_executed": False,
        "schema_is_research_only": True,
        "validator_modified": False,
        "grounding_text_modified": False,
        "goal": GOAL,
        "state": STATE,
        "need": NEED,
        "start_state": START,
        "prompt": prompt,
        "raw": raw,
        "visible": visible,
        "parse_error": parse_error,
        "parsed_proposal": parsed,
        "value": proposal.get("value"),
        "source_type": proposal.get("source_type"),
        "source_text": proposal.get("source_text"),
        "reason": proposal.get("reason"),
        "grounding": grounding,
        "validator": validation,
        "promotion": validation.get("result"),
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "elapsed_s": elapsed,
        "error": call.get("error"),
        "baseline_a": obs_a.get("run_id"),
        "baseline_b": obs_b.get("run_id"),
    }
    dump(run_dir / "observation.json", observation)
    dump(run_dir / "comparison.json", comparison)

    def cell(value: Any) -> str:
        if value is None:
            return "null"
        return str(value).replace("|", "/")

    lines = [
        "# value_provenance_action_param_v0 3段階比較",
        "",
        f"A: `{obs_a.get('run_id')}` Slotなし",
        f"B: `{obs_b.get('run_id')}` Slot役割のみ",
        f"C: `{run_id}` Slot役割 + Task/Action入力の区別",
        "",
        "Production 未変更。`_search_query` 未使用。Tool 未実行。Validator / Grounding 文面は未変更。",
        "",
        "| 項目 | A Slotなし | B Slot役割 | C Task≠Action入力 |",
        "|---|---|---|---|",
    ]
    for key in (
        "status",
        "value",
        "source_type",
        "source_text",
        "reason",
        "grounding_violation",
        "validator",
        "verdict",
    ):
        lines.append(
            f"| {key} | {cell(row_a.get(key))} | {cell(row_b.get(key))} | {cell(row_c.get(key))} |"
        )
    lines.append(
        "| Task/Action区別の形跡 | "
        f"taskish={dist_a['reason_mentions_task_level_gap']} "
        f"actionish={dist_a['reason_mentions_action_input']} | "
        f"taskish={dist_b['reason_mentions_task_level_gap']} "
        f"actionish={dist_b['reason_mentions_action_input']} | "
        f"taskish={dist_c['reason_mentions_task_level_gap']} "
        f"actionish={dist_c['reason_mentions_action_input']} "
        f"proposed={dist_c['proposed_action_input_value']} |"
    )
    lines.extend(["", f"判定 C: **{verdict}**", "", verdict_reason, ""])
    write_text(run_dir / "COMPARISON.md", "\n".join(lines) + "\n")
    dump(
        run_dir / "run.json",
        {
            "experiment": "value_provenance_action_param_v0",
            "run_id": run_id,
            "model": provider,
            "verdict": verdict,
            "promotion": validation.get("result"),
            "value": proposal.get("value"),
            "elapsed_s": elapsed,
            "baseline_a": obs_a.get("run_id"),
            "baseline_b": obs_b.get("run_id"),
            "production_modified": False,
        },
    )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "verdict": verdict,
                "promotion": validation.get("result"),
                "value": proposal.get("value"),
                "source_type": proposal.get("source_type"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(f"RUN {run_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
