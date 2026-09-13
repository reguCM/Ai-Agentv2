"""Run NH10 mechanical prefill + explicit high_slots experiment."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ollama import Client

HERE = Path(__file__).resolve().parent
FRAMEWORK = HERE.parents[2]
NH5_DIR = FRAMEWORK / "selector" / "experiments" / "nh5"
NH6_DIR = FRAMEWORK / "selector" / "experiments" / "nh6"
NH9_DIR = FRAMEWORK / "selector" / "experiments" / "nh9"
NH10_DIR = FRAMEWORK / "selector" / "experiments" / "nh10"
NH9_RUN = FRAMEWORK / "runs" / "20260827_151000" / "nh9_fixed_observation_escalation"
INPUTS = HERE / "inputs"
RESULTS = HERE / "results"
EVAL = HERE / "evaluation"
PROMPTS = HERE / "prompts"

for p in (NH5_DIR, NH6_DIR, NH9_DIR, NH10_DIR):
    sys.path.insert(0, str(p))

from evaluation_axes import classify_outcome, high_slot_metrics  # noqa: E402
from fingerprint_utils import build_selector_case, evaluate_fingerprint  # noqa: E402
from fixed_slots import (  # noqa: E402
    evaluate_slot_accuracy,
    extract_json,
    map_slots_to_features,
    normalize_slots,
    slot_schema_prompt_block,
    validate_large_slots,
)
from high_slot_gate import build_high_slots  # noqa: E402
from mechanical_prefill import apply_mechanical_prefill  # noqa: E402
from nh5_selector import NH5Selector, evaluate_case  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def chat(client: Client, model: str, system: str, user: str, num_ctx: int, num_predict: int) -> str:
    kwargs = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": num_predict},
    }
    try:
        r = client.chat(**kwargs, think=False)
    except TypeError:
        r = client.chat(**kwargs)
    return r["message"]["content"]


def format_materials(materials: dict[str, Any]) -> str:
    return "\n\n".join(f"## {k}\n{v}" for k, v in materials.items())


def user_case(case: dict[str, Any]) -> str:
    return f"Case ID: {case['case_id']}\nScenario: {case.get('scenario')}\n\n{format_materials(case['materials'])}\n"


def finalize_selector(sel: dict[str, Any], remaining_high: bool, gate: dict[str, Any], esc_rec: dict[str, Any]) -> dict[str, Any]:
    sel = dict(sel)
    sel["auto_fix_allowed"] = False
    reused = list(sel.get("reused_experiments") or [])
    for tag in ("nh5", "nh6", "nh7", "nh8", "nh9", "nh10"):
        if tag not in reused:
            reused.append(tag)
    sel["reused_experiments"] = reused
    sel["escalation_record"] = esc_rec
    if remaining_high or gate.get("escalation") == "HUMAN_REVIEW":
        sel["human_review_required"] = True
        unk = list(sel.get("unknowns") or [])
        if "remaining_high" not in unk:
            unk.append("remaining_high")
        sel["unknowns"] = unk
        if sel.get("escalation") in {None, "NONE", "LARGE_LLM"}:
            sel["escalation"] = "HUMAN_REVIEW"
    return sel


def safety_flags(rec: dict[str, Any], gold_slots: dict | None = None) -> dict[str, Any]:
    feats = (rec.get("fingerprint") or {}).get("features") or {}
    slots = rec.get("slots") or {}
    remain = bool((rec.get("escalation_record") or {}).get("remaining_high"))
    human = bool((rec.get("selector_output") or {}).get("human_review_required"))
    accepted = not human and not remain
    fab_runtime = feats.get("has_runtime_logs") is True and rec.get("gold_has_runtime") is False
    gs = gold_slots or {}
    pred_evid = (slots.get("evidence_present") or {}).get("status") == "OBSERVED" and (slots.get("evidence_present") or {}).get("value") is True
    gold_evid = (gs.get("evidence_present") or {}).get("status")
    fab_evidence = bool(pred_evid and gold_evid == "NOT_OBSERVED" and "prefill:" not in str((slots.get("evidence_present") or {}).get("evidence_reference") or ""))
    # prefill evidence from materials is not fabrication
    if pred_evid and str((slots.get("evidence_present") or {}).get("evidence_reference") or "").startswith("prefill:"):
        fab_evidence = False
    return {
        "false_accept": bool(remain and accepted) or fab_runtime,
        "fabricated_runtime": fab_runtime,
        "fabricated_evidence": fab_evidence,
        "invalid_reopen": False,
        "old_state_reactivation": False,
        "unknown_forced_accept": bool(remain and accepted),
        "auto_fix": bool((rec.get("selector_output") or {}).get("auto_fix_allowed")),
    }


def pack_record(
    *,
    cid: str,
    cond: str,
    slots: dict,
    mapped: dict,
    gate: dict,
    gf: dict,
    selector: NH5Selector,
    selector_gold: dict,
    gold_slots: dict,
    gold_high: list[str],
    esc_rec: dict,
    remaining_high: bool,
    slot_eval: dict | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    fp = evaluate_fingerprint(
        gf["features"],
        {"features": mapped["features"], "uncertainties": mapped.get("uncertainties") or []},
        case_id=cid,
    )
    sel = selector.select(build_selector_case(gf, mapped["features"]))
    sel = finalize_selector(sel, remaining_high, gate, esc_rec)
    ev = evaluate_case(sel, selector_gold)
    hs_metrics = high_slot_metrics(gate.get("high_slot_names") or [], gold_high, slots)
    rec = {
        "case_id": cid,
        "condition": cond,
        "fingerprint": {"features": mapped["features"]},
        "fingerprint_eval": fp,
        "selector_output": sel,
        "selector_eval": ev,
        "slots": slots,
        "slot_eval": slot_eval or evaluate_slot_accuracy(gold_slots, slots),
        "gate": {
            "level": gate.get("level"),
            "reasons": gate.get("reasons"),
            "high_slots": gate.get("high_slots"),
            "high_slot_names": gate.get("high_slot_names"),
            "escalation": gate.get("escalation"),
        },
        "high_slot_metrics": hs_metrics,
        "escalation_record": esc_rec,
        "gold_has_runtime": gf["features"].get("has_runtime_logs"),
        "auto_fix_allowed": False,
    }
    if extra:
        rec.update(extra)
    rec["safety_flags"] = safety_flags(rec, gold_slots)
    rec["outcome"] = classify_outcome(
        selector_eval=ev,
        selector_output=sel,
        gold=selector_gold,
        safety_flags=rec["safety_flags"],
    )
    return rec


def summarize(cond: str, recs: list[dict], large_calls: int) -> dict[str, Any]:
    n = len(recs) or 1
    buckets = {k: 0 for k in ("correct_selector", "safe_but_human_review", "incorrect_selector", "unsafe_accept")}
    for r in recs:
        buckets[r["outcome"]["bucket"]] = buckets.get(r["outcome"]["bucket"], 0) + 1
    return {
        "condition": cond,
        "cases": len(recs),
        "fingerprint_mean_accuracy": round(sum(r["fingerprint_eval"]["field_accuracy"] for r in recs) / n, 4),
        "slot_mean_accuracy": round(sum(r["slot_eval"]["slot_accuracy"] for r in recs) / n, 4),
        "selector_all_ok": sum(1 for r in recs if r["selector_eval"]["checks"]["all_ok"]),
        "selector_soft_ok": sum(1 for r in recs if r["outcome"]["soft_accuracy_ok"]),
        "selector_safety_ok": sum(1 for r in recs if r["selector_eval"]["checks"]["safety_ok"]),
        "human_review": sum(1 for r in recs if r["selector_output"].get("human_review_required")),
        "high_slot_recall_mean": round(sum(r["high_slot_metrics"]["recall"] for r in recs) / n, 4),
        "high_slot_precision_mean": round(sum(r["high_slot_metrics"]["precision"] for r in recs) / n, 4),
        "missed_high_slot_total": sum(r["high_slot_metrics"]["missed_high_slot"] for r in recs),
        "large_calls": large_calls,
        "fabricated_runtime": sum(1 for r in recs if r["safety_flags"]["fabricated_runtime"]),
        "fabricated_evidence": sum(1 for r in recs if r["safety_flags"]["fabricated_evidence"]),
        "false_accept": sum(1 for r in recs if r["safety_flags"]["false_accept"]),
        "auto_fix_any": any(r["selector_output"].get("auto_fix_allowed") for r in recs),
        **buckets,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--large-model", default="qwen3:14b")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--num-predict", type=int, default=4096)
    args = ap.parse_args()

    if not (INPUTS / "case_inputs.json").exists():
        import build_inputs

        build_inputs.main()

    cases = load_json(INPUTS / "case_inputs.json")
    gold_fps = load_json(INPUTS / "gold_fingerprints.json")
    selector_gold = load_json(INPUTS / "selector_gold.json")
    gold_slots = load_json(INPUTS / "gold_slots.json")
    gold_high = load_json(INPUTS / "gold_high_slots.json")
    gold_esc = load_json(INPUTS / "gold_escalation.json")
    selector = NH5Selector()
    client = Client()
    schema = slot_schema_prompt_block()
    sys_audit = (PROMPTS / "condition_d.md").read_text(encoding="utf-8").format(schema=schema)

    # Load NH9 small slots once
    small_slots: dict[str, dict] = {}
    for case in cases:
        cid = case["case_id"]
        small_slots[cid] = load_json(NH9_RUN / "results" / "small_slots" / f"{cid}.json")["slots"]

    # --- A: NH9-C reuse ---
    rec_a = []
    for case in cases:
        cid = case["case_id"]
        src = load_json(NH9_RUN / "results" / "condition_c" / f"{cid}.json")
        # rebuild gate metrics with NH10 structured view on final slots
        slots = src.get("slots") or small_slots[cid]
        mapped = map_slots_to_features(slots, case["materials"])
        gate = build_high_slots(slots=slots, materials=case["materials"], mapped=mapped)
        remain = bool((src.get("escalation_record") or {}).get("remaining_high")) or gate["level"] == "HIGH" and src["selector_output"].get("human_review_required")
        # keep NH9 selector outcome as baseline; attach NH10 outcome axes
        sel = dict(src["selector_output"])
        sel["auto_fix_allowed"] = False
        esc = dict(src.get("escalation_record") or {})
        esc["mode"] = "nh9_c_reuse"
        esc["nh10_high_slots"] = gate["high_slots"]
        rec = {
            "case_id": cid,
            "condition": "A",
            "fingerprint": src["fingerprint"],
            "fingerprint_eval": src["fingerprint_eval"],
            "selector_output": sel,
            "selector_eval": src["selector_eval"],
            "slots": slots,
            "slot_eval": src.get("slot_eval") or evaluate_slot_accuracy(gold_slots[cid], slots),
            "gate": {
                "level": (src.get("uncertainty") or {}).get("after", {}).get("level") or gate["level"],
                "reasons": gate["reasons"],
                "high_slots": gate["high_slots"],
                "high_slot_names": gate["high_slot_names"],
                "escalation": sel.get("escalation"),
                "note": "nh9_c_saved; high_slots recomputed for metrics",
            },
            "high_slot_metrics": high_slot_metrics(gate["high_slot_names"], gold_high.get(cid) or [], slots),
            "escalation_record": esc,
            "gold_has_runtime": gold_fps[cid]["features"].get("has_runtime_logs"),
            "nh9_reuse": True,
        }
        rec["safety_flags"] = safety_flags(rec, gold_slots[cid])
        rec["outcome"] = classify_outcome(
            selector_eval=rec["selector_eval"],
            selector_output=sel,
            gold=selector_gold[cid],
            safety_flags=rec["safety_flags"],
        )
        dump(RESULTS / "condition_a" / f"{cid}.json", rec)
        rec_a.append(rec)
        print(f"A {cid}: sel={rec['selector_eval']['checks']['all_ok']} bucket={rec['outcome']['bucket']} missed_hs={rec['high_slot_metrics']['missed_high_slot']}")

    # --- B: explicit high_slots, no large ---
    rec_b = []
    for case in cases:
        cid = case["case_id"]
        slots = {k: dict(v) for k, v in small_slots[cid].items()}
        mapped = map_slots_to_features(slots, case["materials"])
        gate = build_high_slots(slots=slots, materials=case["materials"], mapped=mapped)
        remain = gate["level"] == "HIGH"
        esc = {
            "escalated": False,
            "reason": "explicit_high_slots_no_large",
            "remaining_high": remain,
            "high_slots": gate["high_slots"],
            "mode": "condition_b",
        }
        rec = pack_record(
            cid=cid,
            cond="B",
            slots=slots,
            mapped=mapped,
            gate=gate,
            gf=gold_fps[cid],
            selector=selector,
            selector_gold=selector_gold[cid],
            gold_slots=gold_slots[cid],
            gold_high=gold_high.get(cid) or [],
            esc_rec=esc,
            remaining_high=remain,
        )
        dump(RESULTS / "condition_b" / f"{cid}.json", rec)
        rec_b.append(rec)
        print(f"B {cid}: gate={gate['level']} hs={gate['high_slot_names']} sel={rec['selector_eval']['checks']['all_ok']} bucket={rec['outcome']['bucket']}")

    # --- C: mechanical prefill, no large ---
    rec_c = []
    for case in cases:
        cid = case["case_id"]
        pref = apply_mechanical_prefill(small_slots[cid], case["materials"])
        slots = pref["slots"]
        mapped = map_slots_to_features(slots, case["materials"])
        gate = build_high_slots(slots=slots, materials=case["materials"], mapped=mapped, prefill_meta=pref)
        remain = gate["level"] == "HIGH"
        esc = {
            "escalated": False,
            "reason": "mechanical_prefill_no_large",
            "remaining_high": remain,
            "high_slots": gate["high_slots"],
            "prefill_applied": pref["applied"],
            "mode": "condition_c",
        }
        rec = pack_record(
            cid=cid,
            cond="C",
            slots=slots,
            mapped=mapped,
            gate=gate,
            gf=gold_fps[cid],
            selector=selector,
            selector_gold=selector_gold[cid],
            gold_slots=gold_slots[cid],
            gold_high=gold_high.get(cid) or [],
            esc_rec=esc,
            remaining_high=remain,
            extra={"prefill_applied": pref["applied"]},
        )
        dump(RESULTS / "condition_c" / f"{cid}.json", rec)
        rec_c.append(rec)
        print(
            f"C {cid}: gate={gate['level']} hs={gate['high_slot_names']} pref={len(pref['applied'])} "
            f"fp={rec['fingerprint_eval']['field_accuracy']:.2f} sel={rec['selector_eval']['checks']['all_ok']} bucket={rec['outcome']['bucket']}"
        )

    # --- D: prefill + large on HIGH slots only ---
    rec_d = []
    large_d = 0
    for case in cases:
        cid = case["case_id"]
        pref = apply_mechanical_prefill(small_slots[cid], case["materials"])
        slots0 = pref["slots"]
        mapped0 = map_slots_to_features(slots0, case["materials"])
        gate0 = build_high_slots(slots=slots0, materials=case["materials"], mapped=mapped0, prefill_meta=pref)
        used = gate0["level"] == "HIGH"
        slots = slots0
        mapped = mapped0
        gate = gate0
        val = {"accepted": [], "rejected": []}
        remain = False
        if used:
            large_d += 1
            allowed = gate0["high_slot_names"] or ["llm_disagreement"]
            user = (
                user_case(case)
                + "\n## HIGH slots only\n"
                + json.dumps(gate0["high_slots"], ensure_ascii=False, indent=2)
                + "\n## Small/prefill slots (do not copy blindly)\n"
                + json.dumps({k: slots0[k] for k in allowed if k in slots0}, ensure_ascii=False, indent=2)
            )
            raw = chat(client, args.large_model, sys_audit, user, args.num_ctx, args.num_predict)
            (RESULTS / "condition_d" / "llm_io").mkdir(parents=True, exist_ok=True)
            (RESULTS / "condition_d" / "llm_io" / f"{cid}_large.txt").write_text(raw or "", encoding="utf-8")
            parsed = extract_json(raw)
            large_slots = normalize_slots(parsed)
            val = validate_large_slots(
                small_slots=slots0,
                large_slots=large_slots,
                allowed=allowed,
                materials=case["materials"],
            )
            slots = val["slots"]
            mapped = map_slots_to_features(slots, case["materials"])
            gate = build_high_slots(slots=slots, materials=case["materials"], mapped=mapped, prefill_meta=pref)
            remain = gate["level"] == "HIGH"
        esc = {
            "escalated": used,
            "reason": "high_slots_only" if used else "low_uncertainty",
            "remaining_high": remain,
            "high_slots": gate0["high_slots"],
            "rejected_corrections": val.get("rejected"),
            "accepted_corrections": val.get("accepted"),
            "mode": "condition_d_prefill_plus_large",
        }
        # After large, remaining HIGH or HUMAN_REVIEW escalation → stop
        if gate.get("escalation") == "HUMAN_REVIEW":
            remain = True
        rec = pack_record(
            cid=cid,
            cond="D",
            slots=slots,
            mapped=mapped,
            gate=gate,
            gf=gold_fps[cid],
            selector=selector,
            selector_gold=selector_gold[cid],
            gold_slots=gold_slots[cid],
            gold_high=gold_high.get(cid) or [],
            esc_rec=esc,
            remaining_high=remain,
            extra={"prefill_applied": pref["applied"], "validation": val, "gate_before_large": gate0},
        )
        dump(RESULTS / "condition_d" / f"{cid}.json", rec)
        rec_d.append(rec)
        print(
            f"D {cid}: esc={used} remain={remain} hs={gate0['high_slot_names']} "
            f"fp={rec['fingerprint_eval']['field_accuracy']:.2f} sel={rec['selector_eval']['checks']['all_ok']} bucket={rec['outcome']['bucket']}"
        )

    # Escalation metrics vs NH8/NH9 gold
    esc_rows = []
    missed = unnecessary = 0
    for c, d in zip(rec_c, rec_d):
        cid = c["case_id"]
        esc = bool(d["escalation_record"]["escalated"])
        must = cid in gold_esc["must_escalate"]
        must_not = cid in gold_esc["must_not_escalate"]
        # NH10: H should escalate or HUMAN for safety even if optional in NH8 gold
        # NH10: J may be solved by prefill without Large; count large-miss only if also not HUMAN_REVIEW
        is_miss = must and not esc and not d["selector_output"].get("human_review_required") and not (
            (d.get("fingerprint") or {}).get("features") or {}
        ).get("llm_disagreement")
        is_unnec = must_not and esc and cid != "NH5-H"
        missed += int(is_miss)
        unnecessary += int(is_unnec)
        esc_rows.append(
            {
                "case_id": cid,
                "C_gate": c["gate"]["level"],
                "C_hs": c["gate"]["high_slot_names"],
                "D_escalated": esc,
                "D_remain": d["escalation_record"].get("remaining_high"),
                "missed": is_miss,
                "unnecessary": is_unnec,
                "H_caught": cid != "NH5-H" or c["gate"]["level"] == "HIGH",
            }
        )

    sum_a = summarize("A", rec_a, sum(1 for r in rec_a if (r.get("escalation_record") or {}).get("escalated")))
    sum_b = summarize("B", rec_b, 0)
    sum_c = summarize("C", rec_c, 0)
    sum_d = summarize("D", rec_d, large_d)

    fp_metrics = {
        "run_id": "20260827_163000",
        "conditions": {"A": sum_a, "B": sum_b, "C": sum_c, "D": sum_d},
        "per_case": [
            {
                "case_id": a["case_id"],
                "A_fp": a["fingerprint_eval"]["field_accuracy"],
                "B_fp": b["fingerprint_eval"]["field_accuracy"],
                "C_fp": c["fingerprint_eval"]["field_accuracy"],
                "D_fp": d["fingerprint_eval"]["field_accuracy"],
                "A_miss_hs": a["high_slot_metrics"]["missed_high_slot"],
                "B_miss_hs": b["high_slot_metrics"]["missed_high_slot"],
                "C_miss_hs": c["high_slot_metrics"]["missed_high_slot"],
                "D_miss_hs": d["high_slot_metrics"]["missed_high_slot"],
                "C_hs": c["gate"]["high_slot_names"],
                "D_hs": d["gate"]["high_slot_names"],
            }
            for a, b, c, d in zip(rec_a, rec_b, rec_c, rec_d)
        ],
    }
    safety_metrics = {
        "summary": {
            k: {
                "false_accept": s["false_accept"],
                "fabricated_runtime": s["fabricated_runtime"],
                "fabricated_evidence": s["fabricated_evidence"],
                "selector_safety_ok": s["selector_safety_ok"],
                "auto_fix_any": s["auto_fix_any"],
            }
            for k, s in [("A", sum_a), ("B", sum_b), ("C", sum_c), ("D", sum_d)]
        }
    }
    escalation_metrics = {
        "per_case": esc_rows,
        "summary": {
            "missed": missed,
            "unnecessary": unnecessary,
            "large_A_nh9": sum_a["large_calls"],
            "large_B": 0,
            "large_C": 0,
            "large_D": large_d,
            "H_gate_high_C": next(r["H_caught"] for r in esc_rows if r["case_id"] == "NH5-H"),
        },
    }
    human_metrics = {
        "buckets": {
            k: {"A": sum_a[k], "B": sum_b[k], "C": sum_c[k], "D": sum_d[k]}
            for k in ("correct_selector", "safe_but_human_review", "incorrect_selector", "unsafe_accept")
        },
        "per_case": [
            {
                "case_id": a["case_id"],
                "A": a["outcome"]["bucket"],
                "B": b["outcome"]["bucket"],
                "C": c["outcome"]["bucket"],
                "D": d["outcome"]["bucket"],
                "A_soft": a["outcome"]["soft_accuracy_ok"],
                "C_soft": c["outcome"]["soft_accuracy_ok"],
                "D_soft": d["outcome"]["soft_accuracy_ok"],
                "I_safety_success": (
                    None
                    if a["case_id"] != "NH5-I"
                    else {
                        "A_bucket": a["outcome"]["bucket"],
                        "C_bucket": c["outcome"]["bucket"],
                        "D_bucket": d["outcome"]["bucket"],
                        "accuracy_mismatch": a["outcome"]["escalation_accuracy_mismatch"],
                        "safety_pass": a["outcome"]["safety_ok"],
                    }
                ),
            }
            for a, b, c, d in zip(rec_a, rec_b, rec_c, rec_d)
        ],
    }

    dump(EVAL / "fingerprint_metrics.json", fp_metrics)
    dump(EVAL / "safety_metrics.json", safety_metrics)
    dump(EVAL / "escalation_metrics.json", escalation_metrics)
    dump(EVAL / "human_review_metrics.json", human_metrics)

    rows = []
    for a, b, c, d, e in zip(rec_a, rec_b, rec_c, rec_d, esc_rows):
        rows.append(
            {
                "case_id": a["case_id"],
                "A_sel": a["selector_eval"]["checks"]["all_ok"],
                "B_sel": b["selector_eval"]["checks"]["all_ok"],
                "C_sel": c["selector_eval"]["checks"]["all_ok"],
                "D_sel": d["selector_eval"]["checks"]["all_ok"],
                "A_soft": a["outcome"]["soft_accuracy_ok"],
                "C_soft": c["outcome"]["soft_accuracy_ok"],
                "D_soft": d["outcome"]["soft_accuracy_ok"],
                "A_bucket": a["outcome"]["bucket"],
                "C_bucket": c["outcome"]["bucket"],
                "D_bucket": d["outcome"]["bucket"],
                "C_miss_hs": c["high_slot_metrics"]["missed_high_slot"],
                "D_esc": d["escalation_record"]["escalated"],
                "unnecessary": e["unnecessary"],
                "missed": e["missed"],
                "H_caught": e["H_caught"],
            }
        )
    with (EVAL / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    dump(
        HERE / "run_meta.json",
        {
            "run_id": "20260827_163000",
            "experiment": "nh10_mechanical_prefill_gate",
            "finished_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "large_model": args.large_model,
            "production_code_changed": False,
            "nh9_reuse": True,
            "large_calls_D": large_d,
            "auto_fix": "NOT_ALLOWED",
        },
    )
    print("summary C", sum_c)
    print("summary D", sum_d)
    print("esc", escalation_metrics["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
