"""Bare role→value bind: confirmed sentence only. No Runtime / Grill / System.

Production 未変更。Tool 未実行。1回だけ。
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

CONFIRMED = "gridを検索して、その内容を要約してほしい。"
ROLE = "検索対象を表す文字列"

ASK = """以下の確認済み文章から、
指定された役割に対応する値を決められる場合は、
文章中に実際に存在する文字列をそのまま返してください。

確認済み文章だけでは決められない場合は
UNRESOLVED を返してください。

文章に存在しない値を作らないでください。
"""

SHAPE = """出力はこのJSONオブジェクト1つのみ。説明文は付けない。

{
  "status": "PROPOSED または UNRESOLVED",
  "value": "文字列 または null",
  "source_text": "確認済み文章からの抜粋 または null",
  "reason": "短い説明"
}

status が UNRESOLVED のとき value と source_text は null。
"""

RUN_A = ROOT / "research/grill_observation_v0/value_provenance_v0/runs/20260909T081235Z"
RUN_B = ROOT / "research/grill_observation_v0/value_provenance_slot_v0/runs/20260909T081755Z"
RUN_C = ROOT / "research/grill_observation_v0/value_provenance_action_param_v0/runs/20260909T082518Z"


def utc_id() -> str:
    from datetime import datetime, timezone

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


def normalize(parsed: dict[str, Any] | None) -> dict[str, Any]:
    if not parsed:
        return {"status": None, "value": None, "source_text": None, "reason": None}
    status = str(parsed.get("status") or "").strip().upper() or None
    value = parsed.get("value")
    source_text = parsed.get("source_text")
    if value is not None:
        value = str(value).strip() or None
    if source_text is not None:
        source_text = str(source_text).strip() or None
    return {
        "status": status,
        "value": value,
        "source_text": source_text,
        "reason": None if parsed.get("reason") is None else str(parsed.get("reason")).strip(),
    }


def validate(proposal: dict[str, Any], confirmed: str) -> dict[str, Any]:
    status = proposal.get("status")
    value = proposal.get("value")
    source_text = proposal.get("source_text")
    if status == "UNRESOLVED":
        return {
            "result": "UNRESOLVED",
            "value_in_confirmed": False,
            "source_text_in_confirmed": False,
            "note": "AI が未確定とした。意味の正誤は見ていない。",
        }
    if status != "PROPOSED":
        return {
            "result": "UNGROUNDED",
            "value_in_confirmed": False,
            "source_text_in_confirmed": False,
            "note": "status が PROPOSED / UNRESOLVED ではない。",
        }
    value_ok = bool(value) and value in confirmed
    source_ok = bool(source_text) and source_text in confirmed
    if value_ok and source_ok:
        result = "EXTRACTABLE"
        note = "value と source_text が確認済み文章に literal で存在する。"
    else:
        result = "UNGROUNDED"
        note = "文章中に存在しない値を提示した、または根拠抜粋が文章に無い。"
    return {
        "result": result,
        "value_in_confirmed": value_ok,
        "source_text_in_confirmed": source_ok,
        "note": note,
    }


def verdict_of(parse_error: str | None, proposal: dict[str, Any], validation: dict[str, Any]) -> tuple[str, str]:
    if parse_error:
        return "PARTIAL", f"研究用JSONを機械取得できない ({parse_error})。"
    result = validation.get("result")
    if result == "EXTRACTABLE":
        return "PASS", "確認済み文章から指定役割に対応する値を抽出し、Validator が literal 確認できた。"
    if result == "UNRESOLVED":
        if proposal.get("value") and proposal.get("value") not in CONFIRMED:
            return "FAIL", "UNRESOLVED だが文章に無い value を置いている。"
        return "PARTIAL", "安全に UNRESOLVED を返した。"
    return "FAIL", "文章に存在しない値を生成した。"


def load_prev(path: Path) -> dict[str, Any]:
    obs = json.loads((path / "observation.json").read_text(encoding="utf-8"))
    return {
        "run_id": obs.get("run_id"),
        "status": (obs.get("parsed_proposal") or {}).get("status"),
        "value": obs.get("value"),
        "reason": obs.get("reason"),
        "validator": (obs.get("validator") or {}).get("result"),
        "verdict": obs.get("verdict"),
    }


def main() -> int:
    started = time.perf_counter()
    prev_a = load_prev(RUN_A)
    prev_b = load_prev(RUN_B)
    prev_c = load_prev(RUN_C)
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
        f"確認済み文章:\n{CONFIRMED}\n\n"
        f"求める値の役割:\n{ROLE}\n\n"
        f"依頼:\n{ASK}\n"
        f"{SHAPE}"
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
        label="value_bind_bare",
    )
    raw = str(call.get("raw_text") or "")
    visible = strip_think(raw)
    write_text(run_dir / "02_raw.txt", raw)
    write_text(run_dir / "02_visible.txt", visible)

    parsed, parse_error = parse_proposal(visible)
    proposal = normalize(parsed)
    validation = validate(proposal, CONFIRMED)
    verdict, verdict_reason = verdict_of(parse_error, proposal, validation)
    elapsed = round(time.perf_counter() - started, 3)

    d_row = {
        "run_id": run_id,
        "status": proposal.get("status"),
        "value": proposal.get("value"),
        "source_text": proposal.get("source_text"),
        "reason": proposal.get("reason"),
        "validator": validation.get("result"),
        "verdict": verdict,
    }
    if verdict == "PASS":
        implication = (
            "モデルは値束縛能力を持つが、"
            "これまでのRuntime / Grill Contextではその能力をうまく使えていない可能性"
        )
    elif validation.get("result") == "UNRESOLVED":
        implication = (
            "少なくともこの1ケースでは、"
            "qwen3:14b に自由形式の役割→値束縛を任せるだけでは成立しなかった。"
            "一般能力不足とは断定しない。"
        )
    else:
        implication = "この1ケースでは、文章に無い値の生成または形式不備が観察された。一般能力不足とは断定しない。"

    comparison = {
        "A_slot_none": prev_a,
        "B_slot_role": prev_b,
        "C_task_vs_action_param": prev_c,
        "D_bare_bind": d_row,
        "implication": implication,
    }
    observation = {
        "experiment": "value_bind_bare_v0",
        "run_id": run_id,
        "model": provider,
        "production_modified": False,
        "runtime_used": False,
        "grill_used": False,
        "capability_resolution_used": False,
        "help_used": False,
        "tool_executed": False,
        "confirmed_text": CONFIRMED,
        "role": ROLE,
        "prompt": prompt,
        "raw": raw,
        "visible": visible,
        "parse_error": parse_error,
        "parsed_output": parsed,
        "value": proposal.get("value"),
        "source_text": proposal.get("source_text"),
        "reason": proposal.get("reason"),
        "validator": validation,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "elapsed_s": elapsed,
        "error": call.get("error"),
        "implication": implication,
    }
    dump(run_dir / "observation.json", observation)
    dump(run_dir / "comparison.json", comparison)

    def cell(value: Any) -> str:
        if value is None:
            return "null"
        return str(value).replace("|", "/")

    lines = [
        "# value_bind_bare_v0 A/B/C/D 比較",
        "",
        f"D: `{run_id}` Runtimeなし 純粋な値束縛",
        "A/B/C は既存 Run（read-only）。",
        "",
        "| 項目 | A Slotなし | B Slot役割 | C Task≠Action | D 純粋束縛 |",
        "|---|---|---|---|---|",
        f"| status | {cell(prev_a.get('status'))} | {cell(prev_b.get('status'))} | {cell(prev_c.get('status'))} | {cell(d_row.get('status'))} |",
        f"| value | {cell(prev_a.get('value'))} | {cell(prev_b.get('value'))} | {cell(prev_c.get('value'))} | {cell(d_row.get('value'))} |",
        f"| validator | {cell(prev_a.get('validator'))} | {cell(prev_b.get('validator'))} | {cell(prev_c.get('validator'))} | {cell(d_row.get('validator'))} |",
        f"| verdict | {cell(prev_a.get('verdict'))} | {cell(prev_b.get('verdict'))} | {cell(prev_c.get('verdict'))} | {cell(d_row.get('verdict'))} |",
        f"| reason | {cell(prev_a.get('reason'))} | {cell(prev_b.get('reason'))} | {cell(prev_c.get('reason'))} | {cell(d_row.get('reason'))} |",
        "",
        f"判定 D: **{verdict}**",
        "",
        verdict_reason,
        "",
        implication,
        "",
    ]
    write_text(run_dir / "COMPARISON.md", "\n".join(lines) + "\n")
    dump(
        run_dir / "run.json",
        {
            "experiment": "value_bind_bare_v0",
            "run_id": run_id,
            "model": provider,
            "verdict": verdict,
            "validator": validation.get("result"),
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
                "validator": validation.get("result"),
                "value": proposal.get("value"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(f"RUN {run_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
