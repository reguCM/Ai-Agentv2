"""Grill Q2 intermediate layer.

Reads parent Q1 run as material. Writes a NEW run. Never writes into the parent run.
Does not call production llm.chat. Does not encode Q-number rules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

from research.grill_observation_v0.display_q2 import render_q2_view
from research.grill_observation_v0.ollama_call import call_local
from research.grill_observation_v0.parse import extract_json_object
from research.grill_observation_v0.prompts_q2_layer import (
    CLASSIFY_SYSTEM,
    HUMANIZE_SYSTEM,
    REEVAL_SYSTEM,
    build_classify_user,
    build_humanize_user,
    build_reeval_user,
)
from research.grill_observation_v0.system_state import (
    add_confirmed_decision,
    add_human_requirement,
    empty_system_state,
    public_spec_view,
    set_unresolved,
    snapshot,
)

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
MAX_INTERNAL_DECISIONS = 5
PARENT_DEFAULT = "20260909T003636Z"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, obj: Any) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def parent_dir(parent_id: str) -> Path:
    return RUNS / parent_id


def fingerprint_parent(parent_id: str) -> dict[str, str]:
    d = parent_dir(parent_id)
    out: dict[str, str] = {}
    for path in sorted(d.iterdir()):
        if path.is_file():
            out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def load_parent(parent_id: str) -> dict[str, Any]:
    path = RUNS / parent_id / "run.json"
    if not path.is_file():
        raise FileNotFoundError(f"parent run not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parent_pending(parent: dict[str, Any]) -> dict[str, Any]:
    turns = parent.get("turns") or []
    if not turns:
        raise ValueError("parent run has no turns")
    q1 = turns[0]
    parsed = q1.get("parsed") or {}
    rec = parsed.get("recommendation") or {}
    rec_id = str(rec.get("id") or "")
    rec_opt = None
    for opt in parsed.get("options") or []:
        if str(opt.get("id") or "") == rec_id:
            rec_opt = opt
            break
    return {
        "source_turn": 1,
        "focus_item": parsed.get("focus_item") or {},
        "question": parsed.get("question") or "",
        "options": parsed.get("options") or [],
        "recommendation": rec,
        "recommended_option": rec_opt,
        "raw_response": q1.get("raw_response") or "",
    }


def llm_json(
    *,
    run: dict[str, Any],
    label: str,
    system: str,
    user: str,
) -> dict[str, Any]:
    profile = run.get("profile") or {}
    call = call_local(
        model=str(run["model"]),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label=label,
    )
    obj, parse_err = extract_json_object(str(call.get("raw_text") or ""))
    return {
        "label": label,
        "prompt": {"system": system, "user": user},
        "raw_response": call.get("raw_text") or "",
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "parse_error": parse_err,
        "parsed": obj if isinstance(obj, dict) else {},
    }


def new_run(*, parent: dict[str, Any], parent_id: str) -> dict[str, Any]:
    model_id = get_pipeline_active_model_id() or str(parent.get("model_id") or "qwen3_14b")
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    goal = str(parent.get("goal") or "")
    env = dict(parent.get("env_facts") or {})
    state = empty_system_state(goal=goal, environment_facts=env, concept=goal)
    add_human_requirement(
        state,
        item_id="goal_text",
        text=goal,
        source="parent_run.goal",
    )
    return {
        "experiment": "grill_observation_v0_q2_layer",
        "run_id": _utc_stamp(),
        "parent_run_id": parent_id,
        "status": "running",
        "model_id": model_id,
        "model": provider,
        "goal": goal,
        "max_internal_decisions": MAX_INTERNAL_DECISIONS,
        "profile": {
            "context_limit": profile.get("context_limit"),
            "num_predict": profile.get("num_predict"),
            "temperature": profile.get("temperature"),
            "hard_timeout_seconds": profile.get("hard_timeout_seconds") or profile.get("timeout_seconds"),
        },
        "system_state": state,
        "state_before": snapshot(state),
        "state_after_q1": None,
        "q1_adoption": {},
        "unresolved_comparisons": [],
        "internal_decisions": [],
        "q2": None,
        "human_promotion_reason": None,
        "conversion_notes": None,
        "stopped": None,
        "note": "New run. Parent Q1 files are read-only.",
    }


def save_artifacts(run_dir: Path, run: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _dump(run_dir / "run.json", run)
    _dump(run_dir / "state_before.json", run.get("state_before") or {})
    if run.get("state_after_q1") is not None:
        _dump(run_dir / "state_after_q1.json", run["state_after_q1"])
    _dump(run_dir / "q1_classification.json", (run.get("q1_adoption") or {}).get("classification_call") or {})
    _dump(run_dir / "q1_adoption.json", run.get("q1_adoption") or {})
    _dump(run_dir / "internal_decisions.json", run.get("internal_decisions") or [])
    _dump(run_dir / "unresolved_comparisons.json", run.get("unresolved_comparisons") or [])
    q2 = run.get("q2") or {}
    if q2:
        _dump(run_dir / "q2.json", q2)
        (run_dir / "q2_raw.txt").write_text(str(q2.get("raw_response") or ""), encoding="utf-8")
        _dump(
            run_dir / "human_promotion.json",
            {
                "reason": run.get("human_promotion_reason"),
                "selected_region": q2.get("selected_region"),
                "conversion_notes": run.get("conversion_notes") or (q2.get("parsed") or {}).get("conversion_notes"),
                "what_changes_for_human": (q2.get("parsed") or {}).get("what_changes_for_human"),
                "technical_decision": (q2.get("parsed") or {}).get("technical_decision"),
            },
        )
    (run_dir / "HUMAN_VIEW.md").write_text(render_q2_view(run), encoding="utf-8")
    _dump(run_dir / "system_state.json", run.get("system_state") or {})


def adopt_q1(run: dict[str, Any], classify_call: dict[str, Any], pending: dict[str, Any]) -> None:
    parsed = classify_call.get("parsed") or {}
    next_action = str(parsed.get("next_action") or "")
    ok = bool(parsed.get("recommendation_ok_to_adopt"))
    contradicts = bool(parsed.get("contradicts_goal_or_env"))
    classification = str(parsed.get("classification") or "")
    can_adopt = next_action == "adopt_recommendation" and ok and not contradicts
    adopt = parsed.get("adopt") if isinstance(parsed.get("adopt"), dict) else {}
    rec_opt = pending.get("recommended_option") or {}
    rec = pending.get("recommendation") or {}
    value = rec_opt.get("label") or rec.get("id")
    title = adopt.get("title") or (pending.get("focus_item") or {}).get("title") or "pending_item"
    item_id = str(adopt.get("id") or (pending.get("focus_item") or {}).get("id") or "q1_decision")
    record = {
        "adopted": False,
        "classification": {
            "human_intent_required": parsed.get("human_intent_required"),
            "human_impact": parsed.get("human_impact"),
            "technical_only": parsed.get("technical_only"),
            "classification": classification,
            "next_action": next_action,
            "reason": parsed.get("reason"),
            "contradicts_goal_or_env": contradicts,
            "recommendation_ok_to_adopt": ok,
        },
        "classification_call": classify_call,
        "pending_question": pending.get("question"),
        "recommendation": rec,
        "stop_reason": None,
    }
    if not can_adopt:
        record["stop_reason"] = "q1_not_adopted_as_ai_decision"
        run["q1_adoption"] = record
        run["state_after_q1"] = snapshot(run["system_state"])
        return
    decision = add_confirmed_decision(
        run["system_state"],
        item_id=item_id,
        title=str(title),
        value=value,
        decided_by="AI",
        reason=str(adopt.get("reason") or rec.get("reason") or parsed.get("reason") or ""),
        evidence={
            "source": "recommendation",
            "parent_run_id": run.get("parent_run_id"),
            "option_id": rec.get("id"),
            "decision_basis": "recommendation",
            "llm_adopt_value": adopt.get("value"),
        },
        human_confirmed=False,
        status="confirmed",
    )
    record["adopted"] = True
    record["decision"] = decision
    run["q1_adoption"] = record
    run["state_after_q1"] = snapshot(run["system_state"])


def apply_internal_decision(run: dict[str, Any], next_obj: dict[str, Any], comparison_row: dict[str, Any]) -> dict[str, Any]:
    ai = next_obj.get("ai_decision") if isinstance(next_obj.get("ai_decision"), dict) else {}
    item_id = str(ai.get("id") or next_obj.get("id") or f"internal_{len(run['internal_decisions']) + 1}")
    title = str(ai.get("title") or item_id)
    value = ai.get("value")
    decision = add_confirmed_decision(
        run["system_state"],
        item_id=item_id,
        title=title,
        value=value,
        decided_by="AI",
        reason=str(ai.get("reason") or next_obj.get("reason") or ""),
        evidence={
            "source": "internal_reeval",
            "evidence": ai.get("evidence"),
            "comparison_n": comparison_row.get("n"),
        },
        human_confirmed=False,
        status="confirmed",
    )
    row = {
        "kind": "internal_ai_decision",
        "n": len(run["internal_decisions"]) + 1,
        "decision": decision,
        "from_next": next_obj,
        "state_after": snapshot(run["system_state"]),
    }
    run["internal_decisions"].append(row)
    return row


def region_by_id(regions: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    for r in regions:
        if str(r.get("id") or "") == str(item_id):
            return r
    return regions[0] if regions else None


def stamp_parent_fingerprint(run: dict[str, Any], parent_id: str, fp_before: dict[str, str]) -> None:
    fp_after = fingerprint_parent(parent_id)
    run["parent_fingerprint_after"] = fp_after
    run["parent_unchanged"] = fp_before == fp_after


def run_layer(parent_id: str) -> dict[str, Any]:
    parent = load_parent(parent_id)
    pending = parent_pending(parent)
    fp_before = fingerprint_parent(parent_id)
    run = new_run(parent=parent, parent_id=parent_id)
    run["parent_fingerprint_before"] = fp_before
    run_dir = RUNS / str(run["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    _dump(run_dir / "parent_q1_snapshot.json", pending)
    save_artifacts(run_dir, run)
    try:
        return _run_layer_body(run, run_dir, pending)
    finally:
        stamp_parent_fingerprint(run, parent_id, fp_before)
        save_artifacts(run_dir, run)


def _run_layer_body(run: dict[str, Any], run_dir: Path, pending: dict[str, Any]) -> dict[str, Any]:
    classify_user = build_classify_user(
        goal=str(run["goal"]),
        env_facts=(run["system_state"].get("environment_facts") or {}),
        pending={k: v for k, v in pending.items() if k != "raw_response"},
        state=public_spec_view(run["system_state"]),
    )
    classify_call = llm_json(run=run, label="classify_q1", system=CLASSIFY_SYSTEM, user=classify_user)
    (run_dir / "classify_q1_raw.txt").write_text(str(classify_call.get("raw_response") or ""), encoding="utf-8")
    adopt_q1(run, classify_call, pending)
    save_artifacts(run_dir, run)

    if not (run.get("q1_adoption") or {}).get("adopted"):
        run["status"] = "stopped_q1_human_required"
        run["stopped"] = "q1_not_ai_decidable"
        save_artifacts(run_dir, run)
        return run

    selected_for_human: dict[str, Any] | None = None
    last_comparison = ""

    for i in range(1, MAX_INTERNAL_DECISIONS + 2):
        budget = MAX_INTERNAL_DECISIONS - len(run["internal_decisions"])
        reeval_user = build_reeval_user(
            goal=str(run["goal"]),
            state=public_spec_view(run["system_state"]),
            internal_budget_left=budget,
        )
        reeval = llm_json(run=run, label=f"reeval_{i}", system=REEVAL_SYSTEM, user=reeval_user)
        parsed = reeval.get("parsed") or {}
        regions = parsed.get("unresolved_regions") if isinstance(parsed.get("unresolved_regions"), list) else []
        set_unresolved(run["system_state"], [r for r in regions if isinstance(r, dict)])
        next_obj = parsed.get("next") if isinstance(parsed.get("next"), dict) else {}
        action = str(next_obj.get("action") or "none")
        row = {
            "n": i,
            "elapsed_s": reeval.get("elapsed_s"),
            "error": reeval.get("error"),
            "parse_error": reeval.get("parse_error"),
            "raw_response": reeval.get("raw_response"),
            "parsed": parsed,
            "comparison": parsed.get("comparison"),
            "unresolved_regions": regions,
            "next": next_obj,
            "action": action,
        }
        run["unresolved_comparisons"].append(row)
        _append_jsonl(run_dir / "unresolved_comparisons.jsonl", row)
        (run_dir / f"reeval_{i}_raw.txt").write_text(str(reeval.get("raw_response") or ""), encoding="utf-8")
        last_comparison = str(parsed.get("comparison") or "")
        save_artifacts(run_dir, run)

        if reeval.get("error") or reeval.get("parse_error"):
            run["stopped"] = f"reeval_{i}_failed"
            run["status"] = "error"
            save_artifacts(run_dir, run)
            return run

        if action == "ask_human":
            selected_for_human = region_by_id(regions, str(next_obj.get("id") or ""))
            if selected_for_human is None:
                selected_for_human = {"id": next_obj.get("id"), "title": next_obj.get("id"), "why": next_obj.get("reason")}
            run["human_promotion_reason"] = str(next_obj.get("reason") or parsed.get("comparison") or "")
            break

        if action == "internal_ai_decision":
            if len(run["internal_decisions"]) >= MAX_INTERNAL_DECISIONS:
                run["stopped"] = "internal_decision_cap"
                run["status"] = "stopped_no_human_question"
                save_artifacts(run_dir, run)
                return run
            apply_internal_decision(run, next_obj, row)
            save_artifacts(run_dir, run)
            continue

        run["stopped"] = "no_next_unresolved"
        run["status"] = "stopped_no_human_question"
        save_artifacts(run_dir, run)
        return run
    else:
        run["stopped"] = "internal_decision_cap"
        run["status"] = "stopped_no_human_question"
        save_artifacts(run_dir, run)
        return run

    humanize_user = build_humanize_user(
        goal=str(run["goal"]),
        state=public_spec_view(run["system_state"]),
        selected_region=selected_for_human or {},
        comparison=last_comparison,
    )
    q2_call = llm_json(run=run, label="humanize_q2", system=HUMANIZE_SYSTEM, user=humanize_user)
    parsed_q2 = q2_call.get("parsed") or {}
    run["q2"] = {
        **q2_call,
        "selected_region": selected_for_human,
    }
    run["conversion_notes"] = parsed_q2.get("conversion_notes")
    run["human_promotion_reason"] = parsed_q2.get("why_ask_human") or run.get("human_promotion_reason")
    run["status"] = "awaiting_human"
    run["stopped"] = "after_Q2"
    save_artifacts(run_dir, run)
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grill Q2 intermediate layer")
    parser.add_argument("--parent", default=PARENT_DEFAULT, help="parent Q1 run id (read-only)")
    args = parser.parse_args(argv)
    run = run_layer(args.parent)
    print(render_q2_view(run), flush=True)
    print(f"RUN {RUNS / run['run_id']}", flush=True)
    print(f"PARENT {args.parent} (unchanged)", flush=True)
    print(f"STOPPED {run.get('stopped')}", flush=True)
    if run.get("stopped") != "after_Q2":
        return 1
    q2 = run.get("q2") or {}
    return 1 if q2.get("error") or q2.get("parse_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
