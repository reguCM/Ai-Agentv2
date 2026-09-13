"""Case 2 固定状態: 不足実行値の proposal + 根拠を機械検証する最小観察。

Production / `_search_query` / Capability / Help / Registry は変更しない。
Tool は実行しない。1回だけ。
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.grill_observation_v0.grill_system_retry_v0.run_once import GRILL_GROUNDING
from research.grill_observation_v0.medium_task_reality_v0.apply_patch import strip_think
from research.grill_observation_v0.natural_exit_v0.run import call_freeform
from research.grill_observation_v0.system_first_loop_v0.run_once import assert_qwen_prompt_clean
from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

# Frozen Case 2 start (resolver_owner_v0 20260909T064802Z, after first Grill retry).
GOAL = "gridを検索して、その内容を要約してほしい。"
STATE = "まだ何も調査していない。"
NEED = "gridの構造と内容を確認する。"
START = {
    "case": "Case 2 frozen",
    "source_run": "research/grill_observation_v0/resolver_owner_v0/runs/20260909T064802Z/case2",
    "source_file": "04_system_retry.json",
    "system_note_for_record_only": {
        "required_capability": "workspace_file_search",
        "selected_tool": "search_files",
        "stopped_at": "tool_selected_arguments_incomplete",
        "missing": "query",
        "next_action": None,
    },
}

ASK = """現在、次の処理に必要な値が1つ不足している。
確認済み情報からその値を決められるなら、
値と、その値を採用できる根拠を示す。
確認済み情報だけでは決められないなら、
未確定として返す。
"""

OUTPUT_SHAPE = """出力はこのJSONオブジェクト1つのみ。説明文は付けない。

{
  "status": "PROPOSED または UNRESOLVED",
  "value": "文字列 または null",
  "source_type": "USER_GOAL または STATE または SYSTEM_CONFIRMED または NONE",
  "source_text": "根拠として使う確認済み原文の抜粋 または null",
  "reason": "短い説明"
}

status が UNRESOLVED のとき value と source_text は null、source_type は NONE。
確認済みでない例・仮説を value に入れない。
"""

SOURCE_TYPES = ("USER_GOAL", "STATE", "SYSTEM_CONFIRMED", "NONE")
STATUSES = ("PROPOSED", "UNRESOLVED")


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_proposal(visible: str) -> tuple[dict[str, Any] | None, str | None]:
    body = str(visible or "").strip()
    if not body:
        return None, "empty_visible"
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body, re.S)
    raw = fenced.group(1) if fenced else None
    if raw is None:
        match = re.search(r"\{.*\}", body, re.S)
        raw = match.group(0) if match else None
    if raw is None:
        return None, "no_json_object"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"json_error:{type(exc).__name__}"
    if not isinstance(parsed, dict):
        return None, "not_object"
    return parsed, None


def normalize_proposal(parsed: dict[str, Any] | None) -> dict[str, Any]:
    if not parsed:
        return {
            "status": None,
            "value": None,
            "source_type": None,
            "source_text": None,
            "reason": None,
        }
    status = str(parsed.get("status") or "").strip().upper() or None
    source_type = str(parsed.get("source_type") or "").strip().upper() or None
    value = parsed.get("value")
    source_text = parsed.get("source_text")
    if value is not None:
        value = str(value).strip() or None
    if source_text is not None:
        source_text = str(source_text).strip() or None
    return {
        "status": status if status in STATUSES else status,
        "value": value,
        "source_type": source_type if source_type in SOURCE_TYPES else source_type,
        "source_text": source_text,
        "reason": None if parsed.get("reason") is None else str(parsed.get("reason")).strip(),
    }


def contained(needle: str | None, haystack: str) -> bool:
    if not needle:
        return False
    return needle in haystack


def research_validator(
    proposal: dict[str, Any],
    *,
    goal: str,
    state: str,
    system_confirmed: str,
) -> dict[str, Any]:
    """Meaning-blind: claimed source must literally contain the claimed text/value."""
    status = proposal.get("status")
    value = proposal.get("value")
    source_type = proposal.get("source_type")
    source_text = proposal.get("source_text")
    sources = {
        "USER_GOAL": goal,
        "STATE": state,
        "SYSTEM_CONFIRMED": system_confirmed,
        "NONE": "",
    }

    if status == "UNRESOLVED":
        return {
            "result": "UNRESOLVED",
            "source_text_in_claimed_source": False,
            "value_in_source_text": False,
            "value_in_claimed_source": False,
            "checks": ["status_unresolved"],
            "note": "AI が未確定とした。意味の正誤は見ていない。",
        }
    if status != "PROPOSED":
        return {
            "result": "REJECTED_UNGROUNDED",
            "source_text_in_claimed_source": False,
            "value_in_source_text": False,
            "value_in_claimed_source": False,
            "checks": ["status_not_proposed"],
            "note": "研究用 status が PROPOSED / UNRESOLVED ではない。",
        }
    if source_type not in ("USER_GOAL", "STATE", "SYSTEM_CONFIRMED"):
        return {
            "result": "REJECTED_UNGROUNDED",
            "source_text_in_claimed_source": False,
            "value_in_source_text": False,
            "value_in_claimed_source": False,
            "checks": ["source_type_not_confirmable"],
            "note": "確認済み Source が指定されていない。",
        }
    claimed = sources[source_type]
    source_text_ok = contained(source_text, claimed)
    value_in_excerpt = contained(value, source_text or "")
    value_in_source = contained(value, claimed)
    value_ok = bool(value) and (value_in_excerpt or value_in_source)
    if source_text_ok and value_ok:
        result = "PROMOTABLE"
        note = "主張された Source に source_text と value が literal で存在する。"
    else:
        result = "REJECTED_UNGROUNDED"
        note = "主張された Source 上で source_text または value を literal 確認できない。"
    return {
        "result": result,
        "source_text_in_claimed_source": source_text_ok,
        "value_in_source_text": value_in_excerpt,
        "value_in_claimed_source": value_in_source,
        "checks": [
            f"source_type={source_type}",
            f"source_text_in_source={source_text_ok}",
            f"value_in_source_text={value_in_excerpt}",
            f"value_in_claimed_source={value_in_source}",
        ],
        "note": note,
    }


def grounding_observation(
    proposal: dict[str, Any],
    *,
    goal: str,
    state: str,
    system_confirmed: str,
) -> dict[str, Any]:
    value = proposal.get("value")
    source_text = proposal.get("source_text")
    source_type = proposal.get("source_type")
    sources = {
        "USER_GOAL": goal,
        "STATE": state,
        "SYSTEM_CONFIRMED": system_confirmed,
        "NONE": "",
    }
    claimed = sources.get(str(source_type), "")
    reason = str(proposal.get("reason") or "")
    exampleish = bool(re.search(r"(例えば|例:|例：|仮説)", reason)) or bool(
        re.search(r"(例えば|例:|例：)", str(source_text or ""))
    )
    return {
        "value": value,
        "source_type": source_type,
        "source_text": source_text,
        "reason": proposal.get("reason"),
        "value_in_goal": contained(value, goal),
        "value_in_state": contained(value, state),
        "value_in_system_confirmed": contained(value, system_confirmed),
        "source_text_in_claimed_source": contained(source_text, claimed),
        "unconfirmed_example_markers_near_claim": exampleish,
        "value_absent_from_all_confirmed_sources": bool(value)
        and not (
            contained(value, goal)
            or contained(value, state)
            or contained(value, system_confirmed)
        ),
    }


def classify_verdict(
    *,
    parse_error: str | None,
    proposal: dict[str, Any],
    grounding: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[str, str]:
    if parse_error:
        return "PARTIAL", f"研究用JSONを機械取得できない ({parse_error})。"
    result = validation.get("result")
    if result == "PROMOTABLE":
        if grounding.get("value_absent_from_all_confirmed_sources"):
            return "FAIL", "Validator は通したが、確認済み Source に value が無い。矛盾。"
        if grounding.get("unconfirmed_example_markers_near_claim") and not grounding.get(
            "value_in_goal"
        ):
            return "FAIL", "未確認例の疑いがあり、Goal にも value が無い。"
        return (
            "PASS",
            "確認済み Source に基づく値を提示し、研究 Validator が literal 確認できた。"
            "未確認例を確定値として昇格していない。",
        )
    if result == "UNRESOLVED":
        if proposal.get("value") and grounding.get("value_absent_from_all_confirmed_sources"):
            return (
                "FAIL",
                "status は UNRESOLVED だが、確認済みに無い value を確定値として置いている。",
            )
        return "PARTIAL", "AI は安全に UNRESOLVED を返した。"
    if grounding.get("value_absent_from_all_confirmed_sources") and proposal.get("status") == "PROPOSED":
        return "FAIL", "未確認の例・仮説を確定値として提示し、根拠も成立していない。"
    return "PARTIAL", "値は出したが、根拠が機械検証できない。"


def main() -> int:
    started = time.perf_counter()
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    if provider != "qwen3:14b":
        model_id = "qwen3_14b"
        provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = utc_id()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    system_confirmed = (
        "System は次の実行可能処理まで進めなかった。"
        "必要な値が1つ不足している。"
    )
    prompt = (
        f"Goal:\n{GOAL}\n\n"
        f"Current State:\n{STATE}\n\n"
        f"現在の未解決点:\n{NEED}\n\n"
        f"System の事実:\n{system_confirmed}\n\n"
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
        label="value_provenance",
    )
    raw = str(call.get("raw_text") or "")
    visible = strip_think(raw)
    write_text(run_dir / "02_raw.txt", raw)
    write_text(run_dir / "02_visible.txt", visible)

    parsed, parse_error = parse_proposal(visible)
    proposal = normalize_proposal(parsed)
    grounding = grounding_observation(
        proposal, goal=GOAL, state=STATE, system_confirmed=system_confirmed
    )
    validation = research_validator(
        proposal, goal=GOAL, state=STATE, system_confirmed=system_confirmed
    )
    verdict, verdict_reason = classify_verdict(
        parse_error=parse_error,
        proposal=proposal,
        grounding=grounding,
        validation=validation,
    )
    elapsed = round(time.perf_counter() - started, 3)
    observation = {
        "experiment": "value_provenance_v0",
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
    }
    dump(run_dir / "observation.json", observation)
    dump(
        run_dir / "run.json",
        {
            "experiment": "value_provenance_v0",
            "run_id": run_id,
            "model": provider,
            "verdict": verdict,
            "promotion": validation.get("result"),
            "value": proposal.get("value"),
            "elapsed_s": elapsed,
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
