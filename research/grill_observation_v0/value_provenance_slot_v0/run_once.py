"""value_provenance_v0 比較: 不足 Slot の役割だけを AI へ追加。

Baseline Run は read-only。Production / `_search_query` は変更しない。
Tool は実行しない。1回だけ。
"""
from __future__ import annotations

import json
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
BASELINE_RUN = (
    ROOT
    / "research"
    / "grill_observation_v0"
    / "value_provenance_v0"
    / "runs"
    / "20260909T081235Z"
)

ASK = """現在、不足している値の役割は
『検索対象を表す文字列』です。

確認済みGoal / Stateからその値を決められる場合は、
値と、その値を採用できる根拠を返してください。

確認済み情報だけでは決められない場合は
UNRESOLVEDを返してください。

未確認の例・仮説を確定値として使わないでください。
"""

SYSTEM_FACTS_FOR_AI = """検索系の能力と対応する処理までは選択済みである。
実行に必要な値が1つ不足している。
不足している値の役割は『検索対象を表す文字列』である。
"""

SYSTEM_CONFIRMED_FOR_VALIDATOR = (
    "検索系の能力と対応する処理までは選択済みである。"
    "実行に必要な値が1つ不足している。"
    "不足している値の役割は『検索対象を表す文字列』である。"
)


def load_baseline() -> dict[str, Any]:
    path = BASELINE_RUN / "observation.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    started = time.perf_counter()
    baseline = load_baseline()
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
        label="value_provenance_slot",
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

    comparison = {
        "baseline_run": str(BASELINE_RUN.relative_to(ROOT)).replace("\\", "/"),
        "baseline": {
            "status": (baseline.get("parsed_proposal") or {}).get("status"),
            "value": baseline.get("value"),
            "source_type": baseline.get("source_type"),
            "source_text": baseline.get("source_text"),
            "reason": baseline.get("reason"),
            "grounding_violation": bool(
                (baseline.get("grounding") or {}).get("unconfirmed_example_markers_near_claim")
            )
            or bool((baseline.get("grounding") or {}).get("value_absent_from_all_confirmed_sources")),
            "validator": (baseline.get("validator") or {}).get("result"),
            "verdict": baseline.get("verdict"),
        },
        "this_run": {
            "status": proposal.get("status"),
            "value": proposal.get("value"),
            "source_type": proposal.get("source_type"),
            "source_text": proposal.get("source_text"),
            "reason": proposal.get("reason"),
            "grounding_violation": bool(grounding.get("unconfirmed_example_markers_near_claim"))
            or bool(grounding.get("value_absent_from_all_confirmed_sources")),
            "validator": validation.get("result"),
            "verdict": verdict,
        },
        "prompt_delta": "不足 Slot の役割『検索対象を表す文字列』と、検索系処理までは選択済みである事実だけを追加。正解値・内部引数名・Tool名は未記載。",
        "what_changed": None,
    }
    comparison["what_changed"] = {
        key: {
            "baseline": comparison["baseline"].get(key),
            "this_run": comparison["this_run"].get(key),
            "changed": comparison["baseline"].get(key) != comparison["this_run"].get(key),
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
    }

    observation = {
        "experiment": "value_provenance_slot_v0",
        "run_id": run_id,
        "model": provider,
        "production_modified": False,
        "search_query_parser_modified": False,
        "tool_executed": False,
        "schema_is_research_only": True,
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
        "baseline_run_id": baseline.get("run_id"),
    }
    dump(run_dir / "observation.json", observation)
    dump(run_dir / "comparison.json", comparison)
    lines = [
        "# value_provenance_slot_v0 比較",
        "",
        f"this_run: `{run_id}`",
        f"baseline: `{baseline.get('run_id')}`",
        "Production 未変更。`_search_query` 未使用。Tool 未実行。",
        "",
        "| 項目 | Baseline（Slotなし） | 今回（Slot役割のみ） | 変化 |",
        "|---|---|---|---|",
    ]
    for key, row in comparison["what_changed"].items():
        left = row["baseline"]
        right = row["this_run"]
        if left is None:
            left = "null"
        if right is None:
            right = "null"
        lines.append(
            f"| {key} | {left} | {right} | {'yes' if row['changed'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            f"判定: **{verdict}**",
            "",
            verdict_reason,
            "",
        ]
    )
    write_text(run_dir / "COMPARISON.md", "\n".join(lines) + "\n")
    dump(
        run_dir / "run.json",
        {
            "experiment": "value_provenance_slot_v0",
            "run_id": run_id,
            "model": provider,
            "verdict": verdict,
            "promotion": validation.get("result"),
            "value": proposal.get("value"),
            "elapsed_s": elapsed,
            "baseline_run_id": baseline.get("run_id"),
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
