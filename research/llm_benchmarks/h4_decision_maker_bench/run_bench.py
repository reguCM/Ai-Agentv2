#!/usr/bin/env python3
"""H4 Core Local-LLM Maker first-recommendation benchmark.

Does not call production tools.system.llm.chat (avoids context_monitor writes).
Uses Model Registry active model identity. Does not switch models.
Hidden eval file is never sent to the model.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adoption_gate import (
    HIGH_UNCERTAINTY as GATE_HIGH_UNCERTAINTY,
    build_gate_retry_user,
    evaluate_adoption_gate,
    final_adoption_status,
    final_route_status,
    route_final,
)
from ollama import Client

from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

PACKETS = HERE / "packets"
DECISIONS_PATH = PACKETS / "decisions.json"
SHARED_PATH = PACKETS / "shared_context.json"
HIDDEN_PATH = PACKETS / "hidden_eval.json"
RESULTS_ROOT = HERE / "results"

REQUIRED_FIELDS = [
    "decision_id",
    "first_recommendation",
    "reason",
    "rejected_alternatives",
    "known_issues",
    "concrete_failure_scenarios",
    "need_human",
    "uncertainty_score",
    "uncertainty_reason",
    "needs_deep_review",
]

HIGH_UNCERTAINTY = 50
HIGH_CONFIDENCE = 25
PHASE_B_RANDOM_FRAC = 0.15
RANDOM_SEED = 20260909


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def decision_index(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in decisions}


def prior_ids_for(decisions: list[dict[str, Any]], decision_id: str) -> list[str]:
    order = {str(item["id"]): int(item["order"]) for item in decisions}
    current = order[decision_id]
    return [str(item["id"]) for item in decisions if int(item["order"]) < current]


def locked_appendix(decisions: list[dict[str, Any]], hidden: dict[str, Any]) -> str:
    items = hidden["items"]
    lines = []
    for item in decisions:
        did = str(item["id"])
        adopted = items[did]["adopted"]
        lines.append(f"- {did}: {adopted}")
    return "\n".join(lines)


def strip_hidden(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_hidden(v) for k, v in obj.items() if k != "_eval"}
    if isinstance(obj, list):
        return [strip_hidden(x) for x in obj]
    return obj


def extract_json(text: str) -> tuple[Any | None, str | None]:
    if not text or not str(text).strip():
        return None, "empty"
    raw = str(text)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S | re.I)
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", raw, flags=re.S)
    if fence:
        raw = fence.group(1)
    decoder = json.JSONDecoder()
    for start in range(len(raw)):
        if raw[start] not in "{[":
            continue
        try:
            obj, _end = decoder.raw_decode(raw[start:])
            return obj, None
        except json.JSONDecodeError:
            continue
    return None, "json_decode_failed"


def normalize_rows(parsed: Any, expected_ids: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    notes: list[str] = []
    rows: list[Any]
    if isinstance(parsed, dict) and isinstance(parsed.get("decisions"), list):
        rows = parsed["decisions"]
    elif isinstance(parsed, list):
        rows = parsed
    elif isinstance(parsed, dict) and parsed.get("decision_id"):
        rows = [parsed]
    else:
        return [], ["structure_not_decisions"]

    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            notes.append("non_object_row")
            continue
        did = str(row.get("decision_id") or row.get("id") or "").strip()
        if not did:
            notes.append("missing_decision_id")
            continue
        by_id[did] = row

    out: list[dict[str, Any]] = []
    for did in expected_ids:
        row = by_id.get(did)
        if row is None:
            notes.append(f"missing_output:{did}")
            out.append({"decision_id": did, "_parse_missing": True})
            continue
        missing = [f for f in REQUIRED_FIELDS if f not in row]
        cleaned = dict(row)
        cleaned["decision_id"] = did
        if missing:
            cleaned["_missing_fields"] = missing
            notes.append(f"missing_fields:{did}:{','.join(missing)}")
        score = cleaned.get("uncertainty_score")
        try:
            cleaned["uncertainty_score"] = int(score)
        except (TypeError, ValueError):
            cleaned["uncertainty_score"] = None
            cleaned.setdefault("_missing_fields", [])
            if "uncertainty_score" not in cleaned["_missing_fields"]:
                cleaned["_missing_fields"].append("uncertainty_score")
            notes.append(f"bad_uncertainty:{did}")
        for key in ("need_human", "needs_deep_review"):
            val = cleaned.get(key)
            if isinstance(val, str):
                cleaned[key] = val.strip().lower() in ("true", "yes", "1")
            elif val is None:
                cleaned[key] = None
            else:
                cleaned[key] = bool(val)
        for key in ("rejected_alternatives", "known_issues", "concrete_failure_scenarios"):
            val = cleaned.get(key)
            if val is None:
                cleaned[key] = []
            elif isinstance(val, str):
                cleaned[key] = [val]
            elif not isinstance(val, list):
                cleaned[key] = [str(val)]
        out.append(cleaned)
    extra = sorted(set(by_id) - set(expected_ids))
    if extra:
        notes.append("extra_ids:" + ",".join(extra))
    return out, notes


def response_metrics(resp: Any) -> dict[str, Any]:
    def g(name: str) -> Any:
        if isinstance(resp, dict):
            return resp.get(name)
        return getattr(resp, name, None)

    total_ns = g("total_duration")
    eval_ns = g("eval_duration")
    prompt_ns = g("prompt_eval_duration")
    return {
        "prompt_eval_count": g("prompt_eval_count"),
        "eval_count": g("eval_count"),
        "total_duration_ns": total_ns,
        "eval_duration_ns": eval_ns,
        "prompt_eval_duration_ns": prompt_ns,
        "total_duration_ms": None if total_ns is None else round(int(total_ns) / 1e6, 1),
        "eval_duration_ms": None if eval_ns is None else round(int(eval_ns) / 1e6, 1),
        "prompt_eval_duration_ms": None if prompt_ns is None else round(int(prompt_ns) / 1e6, 1),
    }


def message_content(resp: Any) -> str:
    if isinstance(resp, dict):
        msg = resp.get("message") or {}
        if isinstance(msg, dict):
            return str(msg.get("content") or "")
        return str(getattr(msg, "content", "") or "")
    msg = getattr(resp, "message", None)
    return str(getattr(msg, "content", "") or "")


def call_local(
    *,
    model: str,
    messages: list[dict[str, str]],
    num_ctx: int,
    num_predict: int,
    temperature: float,
    timeout_s: int,
    label: str = "ollama",
) -> dict[str, Any]:
    client = Client(timeout=timeout_s)
    started = time.perf_counter()
    error = None
    resp = None
    stop = threading.Event()

    def heartbeat() -> None:
        while not stop.wait(15):
            elapsed = time.perf_counter() - started
            print(f"HEARTBEAT {label} elapsed_s={elapsed:.0f} timeout_s={timeout_s}", flush=True)

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    try:
        print(
            f"CALL {label} model={model} num_ctx={num_ctx} num_predict={num_predict} timeout_s={timeout_s}",
            flush=True,
        )
        resp = client.chat(
            model=model,
            messages=messages,
            format="json",
            options={
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
            keep_alive="10m",
        )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        print(f"ERROR {label} {error}", flush=True)
    finally:
        stop.set()
    wall_ms = round((time.perf_counter() - started) * 1000, 1)
    raw = "" if resp is None else message_content(resp)
    metrics = {} if resp is None else response_metrics(resp)
    kind = classify_call_error(error, raw)
    if kind:
        print(f"FAIL {label} class={kind} wall_ms={wall_ms}", flush=True)
    else:
        print(
            f"DONE {label} wall_ms={wall_ms} prompt={metrics.get('prompt_eval_count')} eval={metrics.get('eval_count')}",
            flush=True,
        )
    return {
        "wall_ms": wall_ms,
        "error": error,
        "error_class": kind,
        "raw_text": raw,
        "metrics": metrics,
    }


SYSTEM_PROMPT = """You are a design Maker giving an independent first recommendation.
You are not a rubber-stamp Critic. Decide as if the project must pick a direction now.
Do not wait to match a later Strong LLM or Cursor answer. Those answers are not provided as a key.
If this packet lists canonical priors, they are already-locked earlier project decisions. Use them. Do not relitigate them. Do not copy a prior as the answer for the current decision_id.
If safety, compatibility, or destructive change is involved and you are not sure, set need_human=true and needs_deep_review=true.
uncertainty_score: 0 = almost certain, 100 = very uncertain.
Return JSON only, no markdown, shaped as:
{"decisions":[{...one object per requested decision_id...}]}
Each object must include: decision_id, first_recommendation, reason, rejected_alternatives, known_issues, concrete_failure_scenarios, need_human, uncertainty_score, uncertainty_reason, needs_deep_review.
Keep prose short. Arrays of short strings. need_human and needs_deep_review are booleans. uncertainty_score is an integer.
"""


def build_phase_a_user(
    shared: dict[str, Any],
    decisions: list[dict[str, Any]],
    hidden: dict[str, Any],
    *,
    locked_prior_decisions: list[dict[str, Any]] | None = None,
) -> str:
    parts = [
        "# Shared locked premises (not the answers to the questions below)",
        json.dumps(
            {
                "locked_before_h4_core": shared["locked_before_h4_core"],
                "code_facts_at_design_time": shared["code_facts_at_design_time"],
                "design_constraints": shared["design_constraints"],
                "do_not_assume": shared["do_not_assume"],
                "deferred_out_of_core": shared["deferred_out_of_core"],
            },
            ensure_ascii=False,
            indent=2,
        ),
    ]
    locked_prior_decisions = locked_prior_decisions or []
    if locked_prior_decisions:
        parts.extend(
            [
                "",
                "# Canonical priors already locked before this slice",
                "These are project-locked earlier decisions. Use them. Do not relitigate them.",
                "They are not a hidden key for the questions below.",
                locked_appendix(locked_prior_decisions, hidden),
            ]
        )
    parts.extend(
        [
            "",
            "# Decisions to answer (chronological). Output all of them.",
            "Do not treat later questions as hints for earlier ones.",
            "Canonical Strong/Cursor answers for the questions below are not provided.",
            "When answering a later id, stay consistent with constraints and with the first recommendations you give for earlier ids in this same output — but still decide each id as a first recommendation, not as matching a hidden key.",
        ]
    )
    for item in decisions:
        parts.append(
            f"\n## {item['id']} (order {item['order']}, group {item['group']})\n"
            f"QUESTION: {item['question']}\n"
            f"CONTEXT: {item['context']}\n"
            f"Earlier ids (already asked above): {', '.join(prior_ids_for(decisions, item['id'])) or '(none)'}"
        )
    parts.append(
        "\nReturn JSON {\"decisions\":[...]} covering every id in order: "
        + ", ".join(item["id"] for item in decisions)
    )
    return "\n".join(parts)


def build_phase_b_user(
    shared: dict[str, Any],
    decisions: list[dict[str, Any]],
    hidden: dict[str, Any],
    decision_id: str,
) -> str:
    item = decision_index(decisions)[decision_id]
    priors = prior_ids_for(decisions, decision_id)
    hidden_items = hidden["items"]
    prior_lines = [f"- {pid}: {hidden_items[pid]['adopted']}" for pid in priors]
    payload = {
        "locked_before_h4_core": shared["locked_before_h4_core"],
        "code_facts_at_design_time": shared["code_facts_at_design_time"],
        "design_constraints": shared["design_constraints"],
        "do_not_assume": shared["do_not_assume"],
        "deferred_out_of_core": shared["deferred_out_of_core"],
        "canonical_priors_before_this_decision": prior_lines,
        "decision": {
            "decision_id": item["id"],
            "order": item["order"],
            "group": item["group"],
            "question": item["question"],
            "context": item["context"],
        },
    }
    return (
        "Answer exactly one decision. Do not reuse a previous Local batch answer. "
        "Use only canonical priors listed here plus shared facts.\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + '\nReturn JSON {"decisions":[{...only this decision_id...}]}'
    )


def tokenize_norm(text: str) -> set[str]:
    t = str(text or "").lower()
    t = re.sub(r"[^\wぁ-んァ-ン一-龥]+", " ", t)
    return {tok for tok in t.split() if len(tok) >= 2}


def agreement(rec: str, adopted: str) -> dict[str, Any]:
    a = tokenize_norm(adopted)
    r = tokenize_norm(rec)
    if not a:
        return {"overlap": 0.0, "label": "unknown"}
    overlap = len(a & r) / len(a)
    rec_l = str(rec or "").lower()
    adopted_l = adopted.lower()
    marker_hits = 0
    markers = []
    for marker in (
        "candidates_available",
        "selected",
        "look_first",
        "_rules",
        "prefer",
        "substring",
        "プロファイル",
        "残す",
        "削除",
        "ranking",
        "[0]",
        "side_effect",
        "dedicated_sandbox",
    ):
        if marker in adopted_l:
            markers.append(marker)
            if marker in rec_l:
                marker_hits += 1
    if overlap >= 0.18 or (markers and marker_hits >= max(1, len(markers) // 2)):
        label = "agreeish"
    elif overlap <= 0.04 and marker_hits == 0:
        label = "disagree"
    else:
        label = "partial"
    return {"overlap": round(overlap, 3), "label": label, "marker_hits": marker_hits, "markers": markers}


def danger_flags(rec: str, eval_item: dict[str, Any]) -> list[str]:
    text = str(rec or "")
    low = text.lower()
    flags: list[str] = []
    rules = [
        (r"candidate_tools\s*\[\s*0\s*\]", "ranking_by_index"),
        (r"selected_tool\s*=\s*candidate_tools\[0\]", "ranking_by_index"),
        (r"look_first\[0\]", "look_first0_default"),
        (r"text\[:80\]", "search_text_slice"),
        (r"fallback\s*=\s*['\"]read_file['\"]", "read_file_fallback"),
    ]
    for pat, name in rules:
        if re.search(pat, text, flags=re.I):
            flags.append(name)
    phrases = [
        ("_rules を正本", "restore_rules"),
        ("_rulesを正本", "restore_rules"),
        ("黙読を維持", "keep_silent_read"),
        ("look_first を戻", "restore_look_first"),
        ("write 側から削除", "delete_write_look_first"),
        ("write側から削除", "delete_write_look_first"),
        ("裸の「編集」", "bare_edit_keyword"),
        ("裸 verb を足", "bare_verb_keyword"),
        ("mutation に日本語「ファイル」", "jp_file_on_mutation"),
        ("掃除して完成", "delete_leftovers_as_done"),
        ("leftover を削除して完成", "delete_leftovers_as_done"),
        ("単数 api を削除", "delete_singular_api"),
        ("merge", "merge_push"),
        ("get_cpu_status を選", "rank_cpu"),
        ("[0] で選", "ranking_by_index"),
        ("一番それらしい", "ranking_in_core"),
    ]
    for needle, name in phrases:
        if needle in low.replace(" ", ""):
            flags.append(name)
        elif needle in low:
            flags.append(name)
    for item in eval_item.get("danger_if") or []:
        key = str(item)
        if key == "selected_tool = candidate_tools[0]" and "candidate_tools[0]" in text:
            flags.append("ranking_by_index")
        if key == "restore look_first[0] silent read" and "look_first[0]" in text and ("戻" in text or "維持" in text):
            flags.append("restore_look_first")
        if key == "delete write look_first" and "削除" in text and "look_first" in low:
            flags.append("delete_write_look_first")
        if key == "keep _RULES as canonical" and "_rules" in low and ("残" in text or "正本" in text):
            flags.append("restore_rules")
        if key == "execute suggested_minimal_tool" and ("実行" in text) and ("suggested" in low or "_minimal" in low):
            flags.append("execute_suggested")
    # ranking restoration is dangerous specifically for Q14-15 / Q38
    return sorted(set(flags))


def prior_contradictions(
    rec: str,
    decision_id: str,
    decisions: list[dict[str, Any]],
    hidden: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    low = str(rec or "").lower()
    priors = prior_ids_for(decisions, decision_id)
    items = hidden["items"]
    checks = [
        ("Q10", "_rules", ["残して正本", "正本に残"]),
        ("Q14-15", "candidate_tools[0]", ["選ぶ", "採用"]),
        ("Q23", "裸", ["編集を足", "keyword に足"]),
        ("Q25", "look_first[0]", ["戻す", "維持"]),
        ("Q27", "look_first", ["write", "削除"]),
    ]
    for pid, token, extra in checks:
        if pid not in priors:
            continue
        if token not in low and token not in str(rec or ""):
            continue
        if any(x in str(rec or "") for x in extra):
            flags.append(f"contradicts_{pid}")
    _ = items
    return flags


def evaluate_row(
    row: dict[str, Any],
    hidden: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    did = str(row.get("decision_id"))
    eval_item = hidden["items"][did]
    rec = str(row.get("first_recommendation") or "")
    agr = agreement(rec, eval_item["adopted"])
    dangers = danger_flags(rec, eval_item)
    contrad = prior_contradictions(rec, did, decisions, hidden)
    missing = list(row.get("_missing_fields") or [])
    parse_missing = bool(row.get("_parse_missing"))
    reasonable_alt = (
        agr["label"] in ("disagree", "partial")
        and not dangers
        and not contrad
        and not parse_missing
        and rec.strip() != ""
    )
    return {
        "decision_id": did,
        "agreement": agr,
        "dangerous_flags": dangers,
        "prior_contradictions": contrad,
        "reasonable_alternative": reasonable_alt,
        "parse_missing": parse_missing,
        "missing_fields": missing,
        "uncertainty_score": row.get("uncertainty_score"),
        "need_human": row.get("need_human"),
        "needs_deep_review": row.get("needs_deep_review"),
    }


def select_phase_b(
    phase_a_rows: list[dict[str, Any]],
    phase_a_eval: list[dict[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    eval_by = {e["decision_id"]: e for e in phase_a_eval}
    flagged: dict[str, list[str]] = {}

    def add(did: str, reason: str) -> None:
        flagged.setdefault(did, []).append(reason)

    high_conf: list[str] = []
    for row in phase_a_rows:
        did = str(row["decision_id"])
        ev = eval_by[did]
        score = row.get("uncertainty_score")
        if row.get("_parse_missing") or ev["parse_missing"]:
            add(did, "parse_missing")
        if ev["missing_fields"]:
            add(did, "missing_fields")
        if row.get("need_human") is True:
            add(did, "need_human")
        if row.get("needs_deep_review") is True:
            add(did, "needs_deep_review")
        if isinstance(score, int) and score >= HIGH_UNCERTAINTY:
            add(did, "high_uncertainty")
        if ev["dangerous_flags"]:
            add(did, "dangerous")
        if ev["prior_contradictions"]:
            add(did, "prior_contradiction")
        if ev["agreement"]["label"] == "disagree":
            add(did, "disagreement")
        if isinstance(score, int) and score <= HIGH_CONFIDENCE and did not in flagged:
            high_conf.append(did)

    rng = random.Random(seed)
    sample_n = max(1, round(len(high_conf) * PHASE_B_RANDOM_FRAC)) if high_conf else 0
    sampled = rng.sample(high_conf, sample_n) if sample_n else []
    for did in sampled:
        add(did, "random_high_confidence")

    return {
        "flagged": flagged,
        "high_confidence_pool": high_conf,
        "random_sample": sampled,
    }


def run_one(
    *,
    phase: str,
    expected_ids: list[str],
    messages: list[dict[str, str]],
    model: str,
    profile: dict[str, Any],
    num_predict: int,
    timeout_s: int,
    max_retry: int = 1,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    parsed_obj = None
    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    parse_error = "not_run"
    for attempt in range(max_retry + 1):
        call = call_local(
            model=model,
            messages=messages,
            num_ctx=int(profile.get("context_limit") or 16384),
            num_predict=num_predict,
            temperature=float(profile.get("temperature") or 0),
            timeout_s=timeout_s,
        )
        obj, err = extract_json(call["raw_text"])
        if obj is None:
            rows, notes = normalize_rows({"decisions": []}, expected_ids)
            notes = [err or "no_json"] + notes
        else:
            rows, notes = normalize_rows(obj, expected_ids)
        parse_error = err
        record = {
            "attempt": attempt,
            "call": {k: v for k, v in call.items() if k != "raw_text"} | {"raw_chars": len(call["raw_text"] or "")},
            "parse_error": err,
            "notes": notes,
            "error_class": call.get("error_class"),
        }
        attempts.append({**record, "raw_text": call["raw_text"]})
        parsed_obj = obj
        if call.get("error_class") in ("OVERFLOW", "TIMEOUT", "CALL_ERROR"):
            parse_error = call.get("error_class") or err
            break
        ok_rows = [r for r in rows if not r.get("_parse_missing")]
        if obj is not None and err is None and ok_rows:
            parse_error = None
            break
        if attempt < max_retry:
            messages = list(messages) + [
                {
                    "role": "user",
                    "content": "Previous output was not valid complete JSON for all requested decision_id values. Return JSON only with key decisions covering every requested id and all required fields.",
                }
            ]
    return {
        "phase": phase,
        "expected_ids": expected_ids,
        "attempts": attempts,
        "retry_count": max(0, len(attempts) - 1),
        "parse_error": parse_error,
        "notes": notes,
        "parsed": parsed_obj,
        "rows": rows,
        "model": model,
    }


def summarize(
    *,
    model_id: str,
    provider_model: str,
    decisions: list[dict[str, Any]],
    phase_a: dict[str, Any],
    phase_a_eval: list[dict[str, Any]],
    phase_b: dict[str, Any] | None,
    phase_b_eval: dict[str, dict[str, Any]],
    phase_b_select: dict[str, Any],
    phase_c: dict[str, Any] | None,
    wall_a_ms: float,
    wall_b_ms: float,
    wall_c_ms: float,
) -> dict[str, Any]:
    n = len(decisions)
    dang_a = sum(1 for e in phase_a_eval if e["dangerous_flags"])
    contrad_a = sum(1 for e in phase_a_eval if e["prior_contradictions"])
    agree_a = sum(1 for e in phase_a_eval if e["agreement"]["label"] == "agreeish")
    alt_a = sum(1 for e in phase_a_eval if e["reasonable_alternative"])
    parse_fail_a = sum(1 for r in phase_a["rows"] if r.get("_parse_missing"))
    missing_a = sum(1 for r in phase_a["rows"] if r.get("_missing_fields"))

    scores = [r.get("uncertainty_score") for r in phase_a["rows"] if isinstance(r.get("uncertainty_score"), int)]
    high_conf = [e for e in phase_a_eval if isinstance(e.get("uncertainty_score"), int) and e["uncertainty_score"] <= HIGH_CONFIDENCE]
    high_conf_wrong = [e for e in high_conf if e["agreement"]["label"] == "disagree" or e["dangerous_flags"]]

    b_ids = list(phase_b_select.get("ids") or [])
    dang_b = sum(1 for did, e in phase_b_eval.items() if e["dangerous_flags"])
    agree_b = sum(1 for did, e in phase_b_eval.items() if e["agreement"]["label"] == "agreeish")

    improved = 0
    worsened = 0
    for did, e_b in phase_b_eval.items():
        e_a = next(x for x in phase_a_eval if x["decision_id"] == did)
        a_bad = bool(e_a["dangerous_flags"] or e_a["parse_missing"] or e_a["agreement"]["label"] == "disagree")
        b_bad = bool(e_b["dangerous_flags"] or e_b["parse_missing"] or e_b["agreement"]["label"] == "disagree")
        if a_bad and not b_bad:
            improved += 1
        if (not a_bad) and b_bad:
            worsened += 1

    maker_possible = dang_a == 0 and contrad_a == 0 and parse_fail_a == 0
    critic_only = dang_a > 0 or contrad_a > 2 or parse_fail_a > n * 0.3
    chunk_needed = bool(
        phase_a.get("parse_error") is not None
        or parse_fail_a > n * 0.4
        or (bool(b_ids) and improved >= max(2, len(b_ids) // 3) and dang_a > dang_b)
    )

    return {
        "model_id": model_id,
        "provider_model": provider_model,
        "decision_count": n,
        "phase_a_wall_ms": wall_a_ms,
        "phase_a_wall_s": round(wall_a_ms / 1000, 1),
        "phase_a_per_decision_s": round((wall_a_ms / 1000) / max(n, 1), 2),
        "phase_b_count": len(b_ids),
        "phase_b_wall_ms": wall_b_ms,
        "phase_c_ran": phase_c is not None,
        "phase_c_wall_ms": wall_c_ms,
        "dangerous_recommendation_count_phase_a": dang_a,
        "dangerous_recommendation_count_phase_b": dang_b,
        "prior_contradiction_count_phase_a": contrad_a,
        "agreement_agreeish_phase_a": agree_a,
        "agreement_rate_phase_a": round(agree_a / max(n, 1), 3),
        "reasonable_alternative_count_phase_a": alt_a,
        "parse_missing_phase_a": parse_fail_a,
        "missing_fields_phase_a": missing_a,
        "retry_count_phase_a": phase_a.get("retry_count"),
        "phase_a_parse_error": phase_a.get("parse_error"),
        "phase_b_agreement_agreeish": agree_b,
        "phase_b_improved": improved,
        "phase_b_worsened": worsened,
        "high_confidence_count": len(high_conf),
        "high_confidence_but_disagree_or_danger": len(high_conf_wrong),
        "uncertainty_mean": None if not scores else round(sum(scores) / len(scores), 1),
        "maker_first_recommendation_looks_usable": maker_possible and not critic_only,
        "prefer_critic_only": critic_only and not maker_possible,
        "chunk_experiment_indicated": chunk_needed,
        "batch_first_plus_adaptive_deep_review_realistic": parse_fail_a <= 3 and dang_a <= 2,
    }


def write_human_summary(path: Path, summary: dict[str, Any], phase_b_select: dict[str, Any]) -> None:
    lines = [
        "# H4 Decision Maker Benchmark — Human Summary",
        "",
        f"- 使用モデル: `{summary['model_id']}` / `{summary['provider_model']}`",
        f"- 対象Decision数: {summary['decision_count']}",
        f"- Phase A所要時間: {summary['phase_a_wall_s']} s（Decisionあたり {summary['phase_a_per_decision_s']} s）",
        f"- Phase Bへ回ったDecision数: {summary['phase_b_count']}",
        f"- dangerous recommendation数: Phase A {summary['dangerous_recommendation_count_phase_a']} / Phase B {summary['dangerous_recommendation_count_phase_b']}",
        f"- prior decision矛盾数: Phase A {summary['prior_contradiction_count_phase_a']}",
        f"- BatchとIndividual: improved {summary['phase_b_improved']} / worsened {summary['phase_b_worsened']}",
        f"- confidence: mean {summary['uncertainty_mean']}; high-conf pool {summary['high_confidence_count']}; high-conf but disagree/danger {summary['high_confidence_but_disagree_or_danger']}",
        f"- parse: missing {summary['parse_missing_phase_a']}; retries {summary['retry_count_phase_a']}; parse_error {summary['phase_a_parse_error']}",
        f"- Strong/Cursor agreeish: {summary['agreement_agreeish_phase_a']} ({summary['agreement_rate_phase_a']})",
        f"- 合理的な別解: {summary['reasonable_alternative_count_phase_a']}",
        f"- Local Makerとして実用可能そうか: {summary['maker_first_recommendation_looks_usable']}",
        f"- Critic用途に留めるべきか: {summary['prefer_critic_only']}",
        f"- 次にChunk実験が必要か: {summary['chunk_experiment_indicated']}",
        f"- Batch-first + adaptive deep review が現実的か: {summary['batch_first_plus_adaptive_deep_review_realistic']}",
        "",
        "Phase B reasons:",
        json.dumps(phase_b_select.get("flagged") or {}, ensure_ascii=False, indent=2),
        "",
        "詳細は同ディレクトリの JSON/JSONL を正本とする。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def chunk_groups(decisions: list[dict[str, Any]]) -> list[list[str]]:
    ids = [d["id"] for d in decisions]
    # Semantic chunks of 8-12. Lock vs first-revision vs remaining revision.
    groups = [
        ids[0:10],   # Q1 .. Q11-13
        ids[10:20],  # Q14-15 .. Q29
        ids[20:30],  # Q30 .. Q39
        ids[30:],    # Q40 .. Q47
    ]
    return [g for g in groups if g]


def build_phase_c_user(
    shared: dict[str, Any],
    decisions: list[dict[str, Any]],
    hidden: dict[str, Any],
    chunk_ids: list[str],
) -> str:
    idx = decision_index(decisions)
    first = chunk_ids[0]
    priors = prior_ids_for(decisions, first)
    hidden_items = hidden["items"]
    prior_lines = [f"- {pid}: {hidden_items[pid]['adopted']}" for pid in priors]
    items = []
    for did in chunk_ids:
        item = idx[did]
        items.append(
            {
                "decision_id": item["id"],
                "order": item["order"],
                "question": item["question"],
                "context": item["context"],
            }
        )
    payload = {
        "locked_before_h4_core": shared["locked_before_h4_core"],
        "code_facts_at_design_time": shared["code_facts_at_design_time"],
        "design_constraints": shared["design_constraints"],
        "do_not_assume": shared["do_not_assume"],
        "canonical_priors_before_this_chunk": prior_lines,
        "decisions": items,
    }
    return (
        "Answer every decision in this chunk. Canonical priors are only those locked before the first id. "
        "Do not copy a hidden Strong key.\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + '\nReturn JSON {"decisions":[...every id in this chunk...]}'
    )


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def classify_call_error(error: str | None, raw_text: str) -> str | None:
    blob = f"{error or ''} {raw_text or ''}".lower()
    if not (error or raw_text):
        return None
    overflow_needles = (
        "context length",
        "too long",
        "overflow",
        "exceeds context",
        "n_keep",
        "prompt is too long",
        "maximum context",
        "num_ctx",
    )
    if any(n in blob for n in overflow_needles):
        return "OVERFLOW"
    if "timeout" in blob or "timed out" in blob:
        return "TIMEOUT"
    if error:
        return "CALL_ERROR"
    return None


def estimate_tokens(n: int) -> dict[str, int]:
    """Linear fit from measured Phase A runs: n=1/5/10 prompt 2135/2745/3580, eval 397/803/1355."""
    n = max(1, int(n))
    prompt_est = int(round(2135 + (n - 1) * 161))
    eval_est = int(round(397 + (n - 1) * 107))
    return {"prompt_est": prompt_est, "eval_est": eval_est}


def plan_context(n: int, num_ctx: int) -> dict[str, Any]:
    est = estimate_tokens(n)
    needed_out = max(512, int(est["eval_est"] * 1.5))
    reserve = 256
    max_predict = max(256, num_ctx - est["prompt_est"] - reserve)
    overflow = est["prompt_est"] + needed_out + reserve > num_ctx
    num_predict = min(needed_out, max_predict)
    if num_predict < 256:
        overflow = True
    timeout_s = int(max(90, min(720, 80 + est["prompt_est"] * 0.04 + needed_out * 0.10)))
    return {
        **est,
        "num_ctx": num_ctx,
        "num_predict": int(num_predict),
        "timeout_s": timeout_s,
        "headroom": num_ctx - est["prompt_est"] - int(num_predict),
        "overflow": overflow,
        "status": "OVERFLOW_PREFLIGHT" if overflow else "OK",
    }


def char_prompt_est(messages: list[dict[str, str]]) -> int:
    text = "".join(str(m.get("content") or "") for m in messages)
    return max(1, len(text) // 3)


def scale_overrides(n: int, num_ctx: int, *, prompt_est_override: int | None = None) -> dict[str, Any]:
    plan = plan_context(n, num_ctx)
    if prompt_est_override is not None:
        plan = dict(plan)
        plan["prompt_est"] = int(prompt_est_override)
        needed_out = max(512, int(plan["eval_est"] * 1.5))
        reserve = 256
        max_predict = max(256, num_ctx - plan["prompt_est"] - reserve)
        overflow = plan["prompt_est"] + needed_out + reserve > num_ctx
        num_predict = min(needed_out, max_predict)
        if num_predict < 256:
            overflow = True
        plan["num_predict"] = int(num_predict)
        plan["headroom"] = num_ctx - plan["prompt_est"] - int(num_predict)
        plan["overflow"] = overflow
        plan["status"] = "OVERFLOW_PREFLIGHT" if overflow else "OK"
        plan["timeout_s"] = int(max(90, min(720, 80 + plan["prompt_est"] * 0.04 + needed_out * 0.10)))
    return {
        "phase_a_num_predict": plan["num_predict"],
        "phase_a_timeout_s": plan["timeout_s"],
        "phase_b_num_predict": min(1024, plan_context(1, num_ctx)["num_predict"]),
        "phase_b_timeout_s": 180,
        "preflight": plan,
    }


def phase_a_error_class(phase_a: dict[str, Any]) -> str | None:
    attempts = phase_a.get("attempts") or []
    if not attempts:
        return None
    last = attempts[-1]
    return last.get("error_class") or (last.get("call") or {}).get("error_class")


def load_rows_by_id(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        did = str(row.get("decision_id") or "")
        if did:
            out[did] = row
    return out


def isolated_compare_row(
    *,
    decision_id: str,
    batch_row: dict[str, Any] | None,
    batch_eval: dict[str, Any] | None,
    iso_row: dict[str, Any] | None,
    iso_eval: dict[str, Any] | None,
    iso_run: dict[str, Any],
) -> dict[str, Any]:
    last = (iso_run.get("attempts") or [{}])[-1]
    call = last.get("call") or {}
    metrics = call.get("metrics") or {}
    return {
        "decision_id": decision_id,
        "batch": {
            "first_recommendation": None if batch_row is None else batch_row.get("first_recommendation"),
            "reason": None if batch_row is None else batch_row.get("reason"),
            "known_issues": None if batch_row is None else batch_row.get("known_issues"),
            "concrete_failure_scenarios": None if batch_row is None else batch_row.get("concrete_failure_scenarios"),
            "uncertainty_score": None if batch_eval is None else batch_eval.get("uncertainty_score"),
            "need_human": None if batch_eval is None else batch_eval.get("need_human"),
            "needs_deep_review": None if batch_eval is None else batch_eval.get("needs_deep_review"),
            "dangerous_flags": None if batch_eval is None else batch_eval.get("dangerous_flags"),
            "prior_contradictions": None if batch_eval is None else batch_eval.get("prior_contradictions"),
        },
        "isolated": {
            "first_recommendation": None if iso_row is None else iso_row.get("first_recommendation"),
            "reason": None if iso_row is None else iso_row.get("reason"),
            "known_issues": None if iso_row is None else iso_row.get("known_issues"),
            "concrete_failure_scenarios": None if iso_row is None else iso_row.get("concrete_failure_scenarios"),
            "uncertainty_score": None if iso_eval is None else iso_eval.get("uncertainty_score"),
            "need_human": None if iso_eval is None else iso_eval.get("need_human"),
            "needs_deep_review": None if iso_eval is None else iso_eval.get("needs_deep_review"),
            "dangerous_flags": None if iso_eval is None else iso_eval.get("dangerous_flags"),
            "prior_contradictions": None if iso_eval is None else iso_eval.get("prior_contradictions"),
            "parse_missing": None if iso_eval is None else iso_eval.get("parse_missing"),
            "missing_fields": None if iso_eval is None else iso_eval.get("missing_fields"),
            "retry_count": iso_run.get("retry_count"),
            "parse_error": iso_run.get("parse_error"),
            "error_class": last.get("error_class") or call.get("error_class"),
            "wall_ms": call.get("wall_ms"),
            "prompt_eval_count": metrics.get("prompt_eval_count"),
            "eval_count": metrics.get("eval_count"),
        },
        "dangerous_cleared": bool(
            batch_eval
            and iso_eval
            and batch_eval.get("dangerous_flags")
            and not iso_eval.get("dangerous_flags")
        ),
        "prior_contradiction_cleared": bool(
            batch_eval
            and iso_eval
            and batch_eval.get("prior_contradictions")
            and not iso_eval.get("prior_contradictions")
        ),
    }


def run_isolated_only(
    *,
    ids: list[str],
    compare_dir: Path | None,
    shared: dict[str, Any],
    all_decisions: list[dict[str, Any]],
    hidden: dict[str, Any],
    model_id: str,
    provider_model: str,
    profile: dict[str, Any],
    num_ctx: int,
) -> int:
    known = {str(d["id"]) for d in all_decisions}
    missing = [i for i in ids if i not in known]
    if missing:
        raise SystemExit(f"unknown isolated ids: {missing}")
    batch_rows = load_rows_by_id(compare_dir / "phase_a_parsed.jsonl") if compare_dir else {}
    batch_evals = load_rows_by_id(compare_dir / "phase_a_eval.jsonl") if compare_dir else {}

    out_dir = RESULTS_ROOT / _utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    comparisons: list[dict[str, Any]] = []
    walls: list[float] = []
    meta = {
        "experiment": "h4_decision_maker_bench_isolated_dangerous",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "provider_model": provider_model,
        "isolated_ids": ids,
        "compare_dir": None if compare_dir is None else str(compare_dir),
        "max_retry": 0,
        "note": "Isolated first-recommendation only. No Phase A. No prompt retune. No retry. Production llm_models.yaml unchanged.",
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OUT {out_dir}", flush=True)
    print(f"MODEL {model_id} {provider_model}", flush=True)
    print(f"ISOLATED ids={ids}", flush=True)

    for did in ids:
        user_prompt = build_phase_b_user(shared, all_decisions, hidden, did)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        prompt_est = max(estimate_tokens(1)["prompt_est"], char_prompt_est(messages))
        ov = scale_overrides(1, num_ctx, prompt_est_override=prompt_est)
        num_predict = max(2048, int(ov["phase_a_num_predict"]))
        timeout_s = max(180, int(ov["phase_a_timeout_s"]))
        preflight = {
            **ov["preflight"],
            "decision_id": did,
            "locked_prior_count": len(prior_ids_for(all_decisions, did)),
            "char_prompt_est": char_prompt_est(messages),
            "num_predict_used": num_predict,
            "timeout_s_used": timeout_s,
            "note": "Isolated floor num_predict=2048 to leave room for model thinking tokens; prompt unchanged.",
        }
        print("PREFLIGHT " + json.dumps(preflight, ensure_ascii=False), flush=True)
        (out_dir / f"packet_isolated_{did}.txt").write_text(user_prompt, encoding="utf-8")
        if preflight["overflow"]:
            print(f"ERROR OVERFLOW_PREFLIGHT {did}", flush=True)
            comparisons.append({"decision_id": did, "error_class": "OVERFLOW_PREFLIGHT", "preflight": preflight})
            continue
        print(f"ISOLATED {did}", flush=True)
        one = run_one(
            phase=f"ISO_{did}",
            expected_ids=[did],
            messages=messages,
            model=provider_model,
            profile=profile,
            num_predict=num_predict,
            timeout_s=timeout_s,
            max_retry=0,
        )
        dump_jsonl(out_dir / f"isolated_{did}_raw.jsonl", one["attempts"])
        row = one["rows"][0] if one["rows"] else {"decision_id": did, "_parse_missing": True}
        ev = evaluate_row(row, hidden, all_decisions)
        dump_jsonl(out_dir / f"isolated_{did}_parsed.jsonl", [row])
        dump_jsonl(out_dir / f"isolated_{did}_eval.jsonl", [ev])
        last = (one.get("attempts") or [{}])[-1]
        walls.append(float((last.get("call") or {}).get("wall_ms") or 0.0))
        comparisons.append(
            isolated_compare_row(
                decision_id=did,
                batch_row=batch_rows.get(did),
                batch_eval=batch_evals.get(did),
                iso_row=row,
                iso_eval=ev,
                iso_run=one,
            )
        )

    total_ms = round((time.perf_counter() - started) * 1000, 1)
    summary = {
        "model_id": model_id,
        "provider_model": provider_model,
        "isolated_ids": ids,
        "isolated_count": len(ids),
        "isolated_wall_ms_sum_calls": round(sum(walls), 1),
        "isolated_wall_s_sum_calls": round(sum(walls) / 1000, 1),
        "isolated_wall_ms_including_overhead": total_ms,
        "isolated_wall_s_including_overhead": round(total_ms / 1000, 1),
        "dangerous_cleared_count": sum(1 for c in comparisons if c.get("dangerous_cleared")),
        "still_dangerous_count": sum(
            1
            for c in comparisons
            if (c.get("isolated") or {}).get("dangerous_flags")
        ),
        "parse_missing_count": sum(
            1 for c in comparisons if (c.get("isolated") or {}).get("parse_missing")
        ),
        "retry_count_total": sum(int((c.get("isolated") or {}).get("retry_count") or 0) for c in comparisons),
        "judgment_hint": (
            "all_isolated_safe"
            if comparisons
            and all(not (c.get("isolated") or {}).get("dangerous_flags") for c in comparisons)
            else (
                "partial_isolated_safe"
                if any(c.get("dangerous_cleared") for c in comparisons)
                else "isolated_still_dangerous"
            )
        ),
    }
    (out_dir / "isolated_compare.json").write_text(
        json.dumps({"summary": summary, "comparisons": comparisons}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary, "comparisons": comparisons}, ensure_ascii=False, indent=2), flush=True)
    print(f"WROTE {out_dir}", flush=True)
    if any((c.get("isolated") or {}).get("error_class") in ("OVERFLOW", "TIMEOUT", "CALL_ERROR", "OVERFLOW_PREFLIGHT") for c in comparisons):
        return 3
    return 0


def _row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "first_recommendation": row.get("first_recommendation"),
        "reason": row.get("reason"),
        "rejected_alternatives": row.get("rejected_alternatives"),
        "known_issues": row.get("known_issues"),
        "concrete_failure_scenarios": row.get("concrete_failure_scenarios"),
        "uncertainty_score": row.get("uncertainty_score"),
        "uncertainty_reason": row.get("uncertainty_reason"),
        "need_human": row.get("need_human"),
        "needs_deep_review": row.get("needs_deep_review"),
    }


def run_gate_experiment(
    *,
    ids: list[str],
    replay_dir: Path,
    shared: dict[str, Any],
    all_decisions: list[dict[str, Any]],
    hidden: dict[str, Any],
    model_id: str,
    provider_model: str,
    profile: dict[str, Any],
    num_ctx: int,
    offline: bool = False,
    reuse_dirs: list[Path] | None = None,
) -> int:
    known = {str(d["id"]) for d in all_decisions}
    missing = [i for i in ids if i not in known]
    if missing:
        raise SystemExit(f"unknown gate ids: {missing}")
    batch_rows = load_rows_by_id(replay_dir / "phase_a_parsed.jsonl")
    out_dir = RESULTS_ROOT / _utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    meta = {
        "experiment": "h4_decision_adoption_gate",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "provider_model": provider_model,
        "gate_ids": ids,
        "replay_dir": str(replay_dir),
        "max_gate_retry": 1,
        "offline": offline,
        "reuse_dirs": [str(p) for p in (reuse_dirs or [])],
        "routing": {
            "gate1": "Known Wrong / Locked Prior / semantic dangerous / structure. FAIL retries once.",
            "gate2": "AUTO / REVIEW / HUMAN from meaning. Local need_human / uncertainty / needs_deep_review are signals only.",
            "high_uncertainty_threshold_signal_only": GATE_HIGH_UNCERTAINTY,
            "note": "No Q-number allowlist. Routing does not use IMPORTANT_DECISIONS.",
        },
        "note": (
            "Experiment-only. Production runtime unchanged. "
            "Initial rec is replayed batch first_recommendation. "
            "FAIL retry does not include Strong/Cursor adopted answers."
        ),
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OUT {out_dir}", flush=True)
    print(f"GATE ids={ids} replay={replay_dir}", flush=True)

    for did in ids:
        initial = batch_rows.get(did)
        if initial is None:
            raise SystemExit(f"replay dir missing {did}")
        eval_item = hidden["items"][did]
        heur = danger_flags(str(initial.get("first_recommendation") or ""), eval_item)
        prior = prior_contradictions(
            str(initial.get("first_recommendation") or ""), did, all_decisions, hidden
        )
        gate1 = evaluate_adoption_gate(
            row=initial,
            decision_id=did,
            heuristic_dangerous=heur,
            prior_contradictions=prior,
        )
        rec = {
            "decision_id": did,
            "initial_first_recommendation": initial.get("first_recommendation"),
            "initial": {**_row_metrics(initial), **gate1, "source": "replay_batch_phase_a"},
            "initial_gate_result": gate1["result"],
            "violated_prior_or_known_wrong": gate1.get("violated_prior_or_known_wrong") or [],
            "retry_performed": False,
            "revised_first_recommendation": None,
            "revised_gate_result": None,
            "revised": None,
            "final_adoption_status": final_adoption_status(gate1["result"]),
            "heuristic_dangerous": gate1["heuristic_dangerous"],
            "heuristic_only_dangerous": gate1["heuristic_only_dangerous"],
            "semantic_dangerous": gate1["semantic_dangerous"],
            "prior_contradiction": prior,
            "uncertainty": initial.get("uncertainty_score"),
            "need_human": initial.get("need_human"),
            "needs_deep_review": initial.get("needs_deep_review"),
            "wall_ms": 0.0,
            "prompt_eval_count": None,
            "eval_count": None,
            "parse_failure": bool(initial.get("_parse_missing")),
            "retry_parse_failure": False,
            "initial_semantic_gate": gate1.get("semantic_gate_result"),
            "initial_escalation": gate1.get("escalation_reasons") or [],
            "final_semantic_gate": gate1.get("semantic_gate_result"),
            "escalation_reasons": gate1.get("escalation_reasons") or [],
            "retry_source": None,
        }
        print(
            f"GATE {did} initial={gate1['result']} semantic_gate={gate1.get('semantic_gate_result')} "
            f"esc={gate1.get('escalation_reasons')} heuristic_only={gate1['heuristic_only_dangerous']}",
            flush=True,
        )
        payload = gate1.get("retry_payload")
        reused_row = None
        reused_raw = None
        for rd in reuse_dirs or []:
            parsed = Path(rd) / f"gate_retry_{did}_parsed.jsonl"
            if parsed.exists():
                by_id = load_rows_by_id(parsed)
                if did in by_id:
                    reused_row = by_id[did]
                    rawp = Path(rd) / f"gate_retry_{did}_raw.jsonl"
                    reused_raw = rawp if rawp.exists() else None
                    break
        if payload:
            adopted = str(eval_item.get("adopted") or "")
            base = build_phase_b_user(shared, all_decisions, hidden, did)
            retry_user = build_gate_retry_user(
                base_isolated_user=base,
                decision_id=did,
                previous_recommendation=str(initial.get("first_recommendation") or ""),
                payload=payload,
            )
            if adopted and adopted in retry_user:
                raise SystemExit(f"refusing to send adopted answer to Local for {did}")
            (out_dir / f"packet_gate_retry_{did}.txt").write_text(retry_user, encoding="utf-8")
            one = None
            row = None
            call: dict[str, Any] = {}
            metrics: dict[str, Any] = {}
            source = None
            if reused_row is not None:
                row = reused_row
                source = "reused_prior_retry"
                if reused_raw is not None:
                    attempts = [
                        json.loads(x)
                        for x in reused_raw.read_text(encoding="utf-8").splitlines()
                        if x.strip()
                    ]
                    dump_jsonl(out_dir / f"gate_retry_{did}_raw.jsonl", attempts)
                    last = attempts[-1] if attempts else {}
                    call = last.get("call") or {}
                    metrics = call.get("metrics") or {}
                print(f"RETRY {did} reused from prior run (no new LLM call)", flush=True)
            elif offline:
                rec["retry_source"] = "skipped_offline"
                print(f"RETRY {did} skipped (offline, no reused retry)", flush=True)
            else:
                print(f"RETRY {did} (constraints only, 1 time)", flush=True)
                one = run_one(
                    phase=f"GATE_RETRY_{did}",
                    expected_ids=[did],
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": retry_user},
                    ],
                    model=provider_model,
                    profile=profile,
                    num_predict=2048,
                    timeout_s=240,
                    max_retry=0,
                )
                dump_jsonl(out_dir / f"gate_retry_{did}_raw.jsonl", one["attempts"])
                row = one["rows"][0] if one["rows"] else {"decision_id": did, "_parse_missing": True}
                last = (one.get("attempts") or [{}])[-1]
                call = last.get("call") or {}
                metrics = call.get("metrics") or {}
                source = "local_retry_after_fail"
            if row is not None:
                dump_jsonl(out_dir / f"gate_retry_{did}_parsed.jsonl", [row])
                heur2 = danger_flags(str(row.get("first_recommendation") or ""), eval_item)
                prior2 = prior_contradictions(
                    str(row.get("first_recommendation") or ""), did, all_decisions, hidden
                )
                gate2 = evaluate_adoption_gate(
                    row=row,
                    decision_id=did,
                    heuristic_dangerous=heur2,
                    prior_contradictions=prior2,
                )
                rec["retry_performed"] = True
                rec["retry_source"] = source
                rec["revised_first_recommendation"] = row.get("first_recommendation")
                rec["revised_gate_result"] = gate2["result"]
                rec["revised"] = {
                    **_row_metrics(row),
                    **gate2,
                    "source": source,
                    "parse_error": None if one is None else one.get("parse_error"),
                    "retry_count": 0 if one is None else one.get("retry_count"),
                    "error_class": call.get("error_class"),
                }
                rec["final_adoption_status"] = final_adoption_status(gate2["result"])
                rec["heuristic_dangerous"] = gate2["heuristic_dangerous"]
                rec["heuristic_only_dangerous"] = gate2["heuristic_only_dangerous"]
                rec["semantic_dangerous"] = gate2["semantic_dangerous"]
                rec["prior_contradiction"] = prior2
                rec["uncertainty"] = row.get("uncertainty_score")
                rec["need_human"] = row.get("need_human")
                rec["needs_deep_review"] = row.get("needs_deep_review")
                rec["wall_ms"] = call.get("wall_ms") or 0.0
                rec["prompt_eval_count"] = metrics.get("prompt_eval_count")
                rec["eval_count"] = metrics.get("eval_count")
                rec["retry_parse_failure"] = bool(row.get("_parse_missing"))
                rec["violated_prior_or_known_wrong"] = (
                    gate2.get("violated_prior_or_known_wrong") or rec["violated_prior_or_known_wrong"]
                )
                rec["final_semantic_gate"] = gate2.get("semantic_gate_result")
                rec["escalation_reasons"] = gate2.get("escalation_reasons") or []
                print(
                    f"REVISED {did} gate={gate2['result']} semantic_gate={gate2.get('semantic_gate_result')} "
                    f"esc={gate2.get('escalation_reasons')} final={rec['final_adoption_status']}",
                    flush=True,
                )
        agr_text = str(
            rec.get("revised_first_recommendation")
            or rec.get("initial_first_recommendation")
            or ""
        )
        agr = agreement(agr_text, str(eval_item.get("adopted") or ""))
        rec["final_agreement_vs_hidden"] = agr
        sem = rec.get("final_semantic_gate")
        if sem == "FAIL" and agr.get("label") == "agreeish":
            rec["quality_flag"] = "possible_false_reject"
        elif sem == "PASS" and agr.get("label") == "disagree":
            rec["quality_flag"] = "possible_false_pass"
        else:
            rec["quality_flag"] = None
        item = next(d for d in all_decisions if str(d["id"]) == did)
        final_block = rec.get("revised") if rec.get("retry_performed") else rec.get("initial")
        final_block = final_block or rec.get("initial") or {}
        routing = route_final(
            semantic_gate_result=str(rec.get("final_semantic_gate") or "FAIL"),
            semantic_dangerous=rec.get("semantic_dangerous") or [],
            need_human=bool(rec.get("need_human")),
            needs_deep_review=bool(rec.get("needs_deep_review")),
            uncertainty_score=rec.get("uncertainty") if isinstance(rec.get("uncertainty"), int) else final_block.get("uncertainty_score"),
            uncertainty_reason=str(
                (rec.get("revised") or {}).get("uncertainty_reason")
                or final_block.get("uncertainty_reason")
                or initial.get("uncertainty_reason")
                or ""
            ),
            reason=str(final_block.get("reason") or initial.get("reason") or ""),
            known_issues=final_block.get("known_issues") or initial.get("known_issues"),
            question=str(item.get("question") or ""),
            context=str(item.get("context") or ""),
            recommendation=agr_text,
        )
        rec["route"] = routing["route"]
        rec["routing_notes"] = routing["notes"]
        rec["routing_attributes"] = routing["attributes"]
        rec["why_human"] = routing["why_human"]
        rec["final_adoption_status"] = final_route_status(routing["route"])
        records.append(rec)

    def count(pred) -> int:
        return sum(1 for r in records if pred(r))

    summary = {
        "model_id": model_id,
        "provider_model": provider_model,
        "ids": ids,
        "n": len(records),
        "initial_fail": count(lambda r: r["initial_gate_result"] == "FAIL"),
        "initial_pass": count(lambda r: r["initial_gate_result"] == "PASS"),
        "initial_unknown": count(lambda r: r["initial_gate_result"] == "UNKNOWN"),
        "known_wrong_caught_initial": count(lambda r: bool(r["initial"].get("semantic_dangerous"))),
        "retry_performed": count(lambda r: r["retry_performed"]),
        "retry_improved_to_pass": count(
            lambda r: r["retry_performed"] and (r.get("revised") or {}).get("semantic_gate_result") == "PASS"
        ),
        "retry_still_fail": count(
            lambda r: r["retry_performed"] and r.get("revised_gate_result") == "FAIL"
        ),
        "retry_then_unknown": count(
            lambda r: r["retry_performed"] and r.get("revised_gate_result") == "UNKNOWN"
        ),
        "final_escalate": count(lambda r: r["final_adoption_status"] == "escalate_strong_or_human"),
        "final_unknown": count(lambda r: r["final_adoption_status"] == "escalate_strong_or_human"),
        "final_adoption_candidate": count(lambda r: r["final_adoption_status"] == "adoption_candidate"),
        "final_rejected": count(lambda r: r["final_adoption_status"] == "rejected"),
        "semantic_dangerous_final": count(lambda r: bool(r.get("semantic_dangerous"))),
        "heuristic_only_final": count(
            lambda r: bool(r.get("heuristic_only_dangerous")) and not r.get("semantic_dangerous")
        ),
        "possible_false_reject": count(lambda r: r.get("quality_flag") == "possible_false_reject"),
        "possible_false_pass": count(lambda r: r.get("quality_flag") == "possible_false_pass"),
        "AUTO": count(lambda r: r.get("route") == "AUTO"),
        "REVIEW": count(lambda r: r.get("route") == "REVIEW"),
        "HUMAN": count(lambda r: r.get("route") == "HUMAN"),
        "auto_ids": [r["decision_id"] for r in records if r.get("route") == "AUTO"],
        "review_ids": [r["decision_id"] for r in records if r.get("route") == "REVIEW"],
        "human_ids": [r["decision_id"] for r in records if r.get("route") == "HUMAN"],
        "human_or_strong_needed": count(lambda r: r.get("route") in ("REVIEW", "HUMAN")),
        "human_intervention_rate": round(
            count(lambda r: r.get("route") == "HUMAN") / max(len(records), 1),
            3,
        ),
        "auto_plus_review_rate": round(
            count(lambda r: r.get("route") in ("AUTO", "REVIEW")) / max(len(records), 1),
            3,
        ),
        "wall_s_retries_sum": round(sum(float(r.get("wall_ms") or 0) for r in records) / 1000, 1),
        "prompt_eval_sum": sum(int(r["prompt_eval_count"]) for r in records if r.get("prompt_eval_count") is not None),
        "eval_sum": sum(int(r["eval_count"]) for r in records if r.get("eval_count") is not None),
        "wall_s_including_overhead": round((time.perf_counter() - started), 1),
    }
    (out_dir / "gate_results.json").write_text(
        json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary}, ensure_ascii=False, indent=2), flush=True)
    print(f"WROTE {out_dir}", flush=True)
    return 0


def _resolve_bench_dir(raw: str) -> Path:
    p = Path(raw)
    if p.exists():
        return p.resolve()
    by_name = HERE / "results" / Path(raw).name
    if by_name.exists():
        return by_name.resolve()
    return p


def rescore_routing(source_dir: Path, all_decisions: list[dict[str, Any]]) -> int:
    src = load_json(source_dir / "gate_results.json")
    idx = decision_index(all_decisions)
    meta = load_json(source_dir / "run_meta.json") if (source_dir / "run_meta.json").exists() else {}
    reason_by_id: dict[str, dict[str, Any]] = {}
    search_dirs: list[Path] = []
    replay = _resolve_bench_dir(str(meta.get("replay_dir") or ""))
    if replay.exists():
        search_dirs.append(replay)
    for extra in meta.get("reuse_dirs") or []:
        p = _resolve_bench_dir(str(extra))
        if p.exists():
            search_dirs.append(p)
    search_dirs.append(source_dir.resolve())
    for folder in search_dirs:
        parsed = folder / "phase_a_parsed.jsonl"
        if parsed.exists():
            reason_by_id.update(load_rows_by_id(parsed))
        for p in folder.glob("gate_retry_*_parsed.jsonl"):
            reason_by_id.update(load_rows_by_id(p))

    out_dir = RESULTS_ROOT / _utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    routed: list[dict[str, Any]] = []
    for rec in src.get("records") or []:
        did = str(rec["decision_id"])
        item = idx[did]
        final_block = rec.get("revised") if rec.get("retry_performed") else rec.get("initial")
        final_block = final_block or rec.get("initial") or {}
        extra = reason_by_id.get(did) or {}
        rec_text = str(
            rec.get("revised_first_recommendation")
            or rec.get("initial_first_recommendation")
            or ""
        )
        routing = route_final(
            semantic_gate_result=str(rec.get("final_semantic_gate") or final_block.get("semantic_gate_result") or "PASS"),
            semantic_dangerous=rec.get("semantic_dangerous") or final_block.get("semantic_dangerous") or [],
            need_human=bool(final_block.get("need_human") if rec.get("retry_performed") else rec.get("need_human")),
            needs_deep_review=bool(
                final_block.get("needs_deep_review") if rec.get("retry_performed") else rec.get("needs_deep_review")
            ),
            uncertainty_score=final_block.get("uncertainty_score")
            if rec.get("retry_performed")
            else rec.get("uncertainty"),
            uncertainty_reason=str(extra.get("uncertainty_reason") or ""),
            reason=str(final_block.get("reason") or extra.get("reason") or ""),
            known_issues=final_block.get("known_issues") or extra.get("known_issues"),
            question=str(item.get("question") or ""),
            context=str(item.get("context") or ""),
            recommendation=rec_text,
        )
        routed.append(
            {
                "decision_id": did,
                "previous_final": rec.get("final_adoption_status"),
                "semantic_gate": rec.get("final_semantic_gate"),
                "semantic_dangerous": rec.get("semantic_dangerous") or [],
                "need_human": rec.get("need_human") if not rec.get("retry_performed") else final_block.get("need_human"),
                "needs_deep_review": rec.get("needs_deep_review")
                if not rec.get("retry_performed")
                else final_block.get("needs_deep_review"),
                "uncertainty": rec.get("uncertainty") if not rec.get("retry_performed") else final_block.get("uncertainty_score"),
                "uncertainty_reason": extra.get("uncertainty_reason"),
                "first_recommendation": rec_text,
                "route": routing["route"],
                "attributes": routing["attributes"],
                "notes": routing["notes"],
                "why_human": routing["why_human"],
                "value_judgment": routing["value_judgment"],
            }
        )

    def n(route: str) -> int:
        return sum(1 for r in routed if r["route"] == route)

    auto_ids = [r["decision_id"] for r in routed if r["route"] == "AUTO"]
    review_ids = [r["decision_id"] for r in routed if r["route"] == "REVIEW"]
    human_ids = [r["decision_id"] for r in routed if r["route"] == "HUMAN"]
    summary = {
        "source_dir": str(source_dir),
        "n": len(routed),
        "AUTO": n("AUTO"),
        "REVIEW": n("REVIEW"),
        "HUMAN": n("HUMAN"),
        "auto_ids": auto_ids,
        "review_ids": review_ids,
        "human_ids": human_ids,
        "semantic_dangerous_remaining": sum(1 for r in routed if r.get("semantic_dangerous")),
        "human_intervention_rate": round(n("HUMAN") / max(len(routed), 1), 3),
        "auto_plus_review_rate": round((n("AUTO") + n("REVIEW")) / max(len(routed), 1), 3),
        "note": (
            "Offline rescore only. No new LLM calls. "
            "HUMAN is residual value judgment after Gate + Strong/Critic review, not Local need_human."
        ),
    }
    (out_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "experiment": "h4_decision_adoption_gate_routing_rescore",
                "source_dir": str(source_dir),
                "llm_called": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "routing_rescore.json").write_text(
        json.dumps({"summary": summary, "records": routed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary, "records": routed}, ensure_ascii=False, indent=2), flush=True)
    print(f"WROTE {out_dir}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Use N chronological decisions after --offset. 0 = rest.")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N chronological decisions.")
    parser.add_argument("--skip-phase-b", action="store_true", default=False)
    parser.add_argument("--skip-phase-c", action="store_true", default=False)
    parser.add_argument("--preflight-only", action="store_true", default=False)
    parser.add_argument(
        "--isolated-ids",
        type=str,
        default="",
        help="Comma-separated decision ids. Skip Phase A; run isolated packets only.",
    )
    parser.add_argument(
        "--compare-dir",
        type=str,
        default="",
        help="Batch result dir to compare isolated runs against (phase_a_parsed/eval).",
    )
    parser.add_argument(
        "--gate-ids",
        type=str,
        default="",
        help="Comma-separated ids for Decision Adoption Gate experiment. Replays batch rec then optional 1 retry.",
    )
    parser.add_argument(
        "--gate-replay-dir",
        type=str,
        default="",
        help="Batch result dir whose phase_a_parsed.jsonl supplies initial first_recommendation.",
    )
    parser.add_argument(
        "--gate-offline",
        action="store_true",
        default=False,
        help="Do not call Local. Reuse prior retries if --gate-reuse-dirs provides them.",
    )
    parser.add_argument(
        "--gate-reuse-dirs",
        type=str,
        default="",
        help="Comma-separated prior gate result dirs to reuse gate_retry_*_parsed.jsonl.",
    )
    parser.add_argument(
        "--gate-rescore-routing",
        type=str,
        default="",
        help="Offline AUTO/REVIEW/HUMAN rescore of an existing gate_results.json dir. No LLM calls.",
    )
    args = parser.parse_args()

    shared = load_json(SHARED_PATH)
    all_decisions = load_json(DECISIONS_PATH)
    hidden = load_json(HIDDEN_PATH)
    assert set(hidden["items"]) == {d["id"] for d in all_decisions}

    if args.gate_rescore_routing:
        return rescore_routing(_resolve_bench_dir(str(args.gate_rescore_routing)), all_decisions)

    model_id = get_pipeline_active_model_id()
    if model_id != "qwen3_14b":
        raise SystemExit(f"refusing to switch models; active is {model_id}")
    profile = get_llm_profile(model_id)
    provider_model = resolve_provider_model_name(model_id)
    num_ctx = int(profile.get("context_limit") or 16384)

    isolated_ids = [x.strip() for x in str(args.isolated_ids or "").split(",") if x.strip()]
    gate_ids = [x.strip() for x in str(args.gate_ids or "").split(",") if x.strip()]
    if gate_ids:
        replay = Path(args.gate_replay_dir) if args.gate_replay_dir else Path(args.compare_dir)
        if not replay or not str(replay):
            raise SystemExit("--gate-ids requires --gate-replay-dir (batch phase_a_parsed.jsonl)")
        return run_gate_experiment(
            ids=gate_ids,
            replay_dir=replay,
            shared=shared,
            all_decisions=all_decisions,
            hidden=hidden,
            model_id=model_id,
            provider_model=provider_model,
            profile=profile,
            num_ctx=num_ctx,
            offline=bool(args.gate_offline),
            reuse_dirs=[Path(p.strip()) for p in str(args.gate_reuse_dirs or "").split(",") if p.strip()],
        )
    if isolated_ids:
        compare_dir = Path(args.compare_dir) if args.compare_dir else None
        return run_isolated_only(
            ids=isolated_ids,
            compare_dir=compare_dir,
            shared=shared,
            all_decisions=all_decisions,
            hidden=hidden,
            model_id=model_id,
            provider_model=provider_model,
            profile=profile,
            num_ctx=num_ctx,
        )

    offset = max(0, int(args.offset or 0))
    if offset >= len(all_decisions):
        raise SystemExit(f"offset {offset} >= decision count {len(all_decisions)}")
    end = len(all_decisions) if not args.limit else min(len(all_decisions), offset + int(args.limit))
    decisions = all_decisions[offset:end]
    locked_prior_decisions = all_decisions[:offset]
    user_prompt = build_phase_a_user(
        shared, decisions, hidden, locked_prior_decisions=locked_prior_decisions
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    model_id = get_pipeline_active_model_id()
    if model_id != "qwen3_14b":
        raise SystemExit(f"refusing to switch models; active is {model_id}")
    profile = get_llm_profile(model_id)
    provider_model = resolve_provider_model_name(model_id)
    num_ctx = int(profile.get("context_limit") or 16384)
    linear = estimate_tokens(len(decisions))["prompt_est"]
    # n=20 measured prompt_eval_count=5780 vs linear 5194.
    calibrated = int(round(linear * (5780 / 5194)))
    prompt_est = max(linear, char_prompt_est(messages), calibrated)
    ov = scale_overrides(len(decisions), num_ctx, prompt_est_override=prompt_est)
    preflight = {
        **ov["preflight"],
        "offset": offset,
        "limit": args.limit or (end - offset),
        "decision_count": len(decisions),
        "locked_prior_count": len(locked_prior_decisions),
        "char_prompt_est": char_prompt_est(messages),
        "linear_prompt_est": estimate_tokens(len(decisions))["prompt_est"],
        "used_prompt_est": prompt_est,
        "decision_ids": [d["id"] for d in decisions],
    }
    print("PREFLIGHT " + json.dumps(preflight, ensure_ascii=False), flush=True)
    if args.preflight_only:
        return 0 if not preflight["overflow"] else 2
    if preflight["overflow"]:
        print(
            f"ERROR OVERFLOW_PREFLIGHT n={len(decisions)} prompt_est={prompt_est} "
            f"num_predict={preflight['num_predict']} num_ctx={num_ctx} headroom={preflight['headroom']}",
            flush=True,
        )
        out_dir = RESULTS_ROOT / _utc_stamp()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "preflight.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "run_meta.json").write_text(
            json.dumps({"status": "OVERFLOW_PREFLIGHT", "preflight": preflight}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"WROTE {out_dir}", flush=True)
        return 2

    out_dir = RESULTS_ROOT / _utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    skip_b = bool(args.skip_phase_b or len(decisions) <= 1)
    skip_c = bool(args.skip_phase_c or len(decisions) < 12)

    meta = {
        "experiment": "h4_decision_maker_bench",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "provider_model": provider_model,
        "offset": offset,
        "limit": args.limit or len(decisions),
        "profile": {
            "context_limit": profile.get("context_limit"),
            "temperature": profile.get("temperature"),
            "num_predict_production": profile.get("num_predict"),
            "hard_timeout_seconds_production": profile.get("hard_timeout_seconds"),
        },
        "experiment_overrides": {
            **{k: v for k, v in ov.items() if k != "preflight"},
            "skip_phase_b": skip_b,
            "skip_phase_c": skip_c,
            "note": "Overrides are experiment-only. Production llm_models.yaml was not changed.",
        },
        "preflight": preflight,
        "random_seed": RANDOM_SEED,
        "decision_ids": [d["id"] for d in decisions],
        "locked_prior_ids": [d["id"] for d in locked_prior_decisions],
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "packet_phase_a_user.txt").write_text(user_prompt, encoding="utf-8")

    print(f"OUT {out_dir}", flush=True)
    print(f"MODEL {model_id} {provider_model}", flush=True)
    print("PHASE A", flush=True)
    t0 = time.perf_counter()
    phase_a = run_one(
        phase="A_batch",
        expected_ids=[d["id"] for d in decisions],
        messages=messages,
        model=provider_model,
        profile=profile,
        num_predict=ov["phase_a_num_predict"],
        timeout_s=ov["phase_a_timeout_s"],
        max_retry=1,
    )
    wall_a = (time.perf_counter() - t0) * 1000
    dump_jsonl(out_dir / "phase_a_raw.jsonl", phase_a["attempts"])
    dump_jsonl(out_dir / "phase_a_parsed.jsonl", phase_a["rows"])
    phase_a_eval = [evaluate_row(row, hidden, all_decisions) for row in phase_a["rows"]]
    dump_jsonl(out_dir / "phase_a_eval.jsonl", phase_a_eval)
    err_class = phase_a_error_class(phase_a)
    if err_class in ("OVERFLOW", "TIMEOUT", "CALL_ERROR"):
        skip_b = True
        skip_c = True
        print(f"PHASE A failed class={err_class}; skipping B/C (no retry)", flush=True)
    (out_dir / "phase_a.json").write_text(
        json.dumps({k: v for k, v in phase_a.items() if k != "attempts"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    select = select_phase_b(phase_a["rows"], phase_a_eval, seed=RANDOM_SEED)
    order = {d["id"]: d["order"] for d in decisions}
    select["ids"] = sorted(select["flagged"], key=lambda i: order[i])
    (out_dir / "phase_b_selection.json").write_text(json.dumps(select, ensure_ascii=False, indent=2), encoding="utf-8")

    phase_b_runs: list[dict[str, Any]] = []
    phase_b_eval: dict[str, dict[str, Any]] = {}
    wall_b = 0.0
    if skip_b:
        print("PHASE B skipped (smoke / --skip-phase-b / n<=1)")
        select["ids"] = []
    else:
        print(f"PHASE B n={len(select['ids'])}")
        t1 = time.perf_counter()
        for did in select["ids"]:
            print(f"  B {did}")
            one = run_one(
                phase=f"B_{did}",
                expected_ids=[did],
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_phase_b_user(shared, all_decisions, hidden, did)},
                ],
                model=provider_model,
                profile=profile,
                num_predict=ov["phase_b_num_predict"],
                timeout_s=ov["phase_b_timeout_s"],
                max_retry=1,
            )
            ev = evaluate_row(one["rows"][0], hidden, all_decisions)
            phase_b_runs.append(one)
            phase_b_eval[did] = ev
            dump_jsonl(out_dir / f"phase_b_{did}_raw.jsonl", one["attempts"])
        wall_b = (time.perf_counter() - t1) * 1000
        dump_jsonl(out_dir / "phase_b_eval.jsonl", [phase_b_eval[i] for i in select["ids"]])
        (out_dir / "phase_b.json").write_text(
            json.dumps(
                [{"id": one["phase"], "parse_error": one["parse_error"], "retry_count": one["retry_count"], "notes": one["notes"], "row": one["rows"][0] if one["rows"] else None} for one in phase_b_runs],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    phase_c = None
    wall_c = 0.0
    dang_a = sum(1 for e in phase_a_eval if e["dangerous_flags"])
    dang_b = sum(1 for e in phase_b_eval.values() if e["dangerous_flags"]) if phase_b_eval else 0
    parse_a = sum(1 for r in phase_a["rows"] if r.get("_parse_missing"))
    isolated_better = parse_a > 8 or (dang_a >= 3 and dang_b < dang_a)
    if isolated_better and not skip_c:
        print("PHASE C")
        t2 = time.perf_counter()
        phase_c_runs = []
        for idx, chunk in enumerate(chunk_groups(decisions), start=1):
            print(f"  C{idx} {chunk}")
            one = run_one(
                phase=f"C_{idx}",
                expected_ids=chunk,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_phase_c_user(shared, all_decisions, hidden, chunk)},
                ],
                model=provider_model,
                profile=profile,
                num_predict=4096,
                timeout_s=360,
                max_retry=1,
            )
            ev = [evaluate_row(row, hidden, all_decisions) for row in one["rows"]]
            phase_c_runs.append({"chunk": idx, "ids": chunk, "run": one, "eval": ev})
            dump_jsonl(out_dir / f"phase_c_{idx}_raw.jsonl", one["attempts"])
            dump_jsonl(out_dir / f"phase_c_{idx}_eval.jsonl", ev)
        wall_c = (time.perf_counter() - t2) * 1000
        phase_c = {"chunks": [{"chunk": x["chunk"], "ids": x["ids"], "parse_error": x["run"]["parse_error"]} for x in phase_c_runs]}
        (out_dir / "phase_c.json").write_text(json.dumps(phase_c, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print("PHASE C skipped (not clearly indicated, n<12, or --skip-phase-c)")

    summary = summarize(
        model_id=model_id,
        provider_model=provider_model,
        decisions=decisions,
        phase_a=phase_a,
        phase_a_eval=phase_a_eval,
        phase_b=phase_b_runs[0] if phase_b_runs else None,
        phase_b_eval=phase_b_eval,
        phase_b_select=select,
        phase_c=phase_c,
        wall_a_ms=wall_a,
        wall_b_ms=wall_b,
        wall_c_ms=wall_c,
    )
    summary["phase_a_error_class"] = err_class
    summary["preflight_status"] = preflight.get("status")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_human_summary(out_dir / "HUMAN_SUMMARY.md", summary, select)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(f"WROTE {out_dir}", flush=True)
    if err_class in ("OVERFLOW", "TIMEOUT", "CALL_ERROR"):
        return 3
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
