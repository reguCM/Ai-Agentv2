"""
Phase 5.1 事前分析: 5ケース History から「無駄な反復」を分類する。

目的: Recall 強化の前に、Memory Recall が介入すべき反復の定義を決める。
"""
from __future__ import annotations

import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT

ROOT = REPO_ROOT
HERE = Path(__file__).resolve().parent
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from tools.ai.state.retrieve import classify_error_class, event_error_class

RESULTS_PATH = ROOT / "research" / "llm_benchmarks" / "research_implement_results.json"
COMPARE_PATH = HERE / "_phase5_vs_phase4_compare.json"
OUT_PATH = HERE / "_phase5_1_repetition_analysis.json"

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]


def match_case(request, case):
    mapping = {
        "memory_usage": "メモリ使用率",
        "cpu_temperature": "CPU温度",
        "disk_usage": "ディスク使用率",
        "gpu_usage": "GPUの使用率",
        "gpu_vram_usage": "GPU VRAM",
    }
    return mapping.get(case, case) in (request or "")


def command_key(action):
    action = action or {}
    return (
        str(action.get("command") or "").strip(),
        tuple(str(a) for a in (action.get("args") or [])),
    )


def command_family(action):
    """類似目的の粗いグループ（command 名 + スクリプト主トークン）。"""
    action = action or {}
    cmd = str(action.get("command") or "").strip().lower()
    args = " ".join(str(a) for a in (action.get("args") or []))
    tokens = re.findall(
        r"Win32_\w+|Get-\w+|nvidia-smi|wmic|cim|temperature|memory|disk|vram|gpu|cpu",
        args,
        flags=re.I,
    )
    token = tokens[0].lower() if tokens else ""
    return (cmd, token)


def fail_events(history):
    out = []
    for event in history or []:
        if event.get("type") == "verify_fail":
            out.append(event)
            continue
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        if result.get("ok") is False:
            out.append(event)
    return out


def analyze_history(history, judgments=None, rounds_detail=None):
    fails = fail_events(history)
    exact_seen = set()
    exact_repeats = []
    family_seen = set()
    family_repeats = []
    class_counts = Counter()
    class_sequences = []
    prev_cls = None
    class_streak = 0
    max_class_streak = 0
    max_class_name = None

    for event in fails:
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        key = command_key(action)
        fam = command_family(action)
        cls = event_error_class(event)
        class_counts[cls] += 1
        if prev_cls == cls:
            class_streak += 1
        else:
            class_streak = 1
            prev_cls = cls
        if class_streak > max_class_streak:
            max_class_streak = class_streak
            max_class_name = cls
        if key[0]:
            if key in exact_seen:
                exact_repeats.append(
                    {
                        "id": event.get("id"),
                        "round": (event.get("metadata") or {}).get("round"),
                        "command_key": [key[0], list(key[1])],
                        "error_class": cls,
                    }
                )
            exact_seen.add(key)
        if fam[0]:
            if fam in family_seen:
                family_repeats.append(
                    {
                        "id": event.get("id"),
                        "round": (event.get("metadata") or {}).get("round"),
                        "family": list(fam),
                        "error_class": cls,
                    }
                )
            family_seen.add(fam)
        class_sequences.append(
            {
                "id": event.get("id"),
                "round": (event.get("metadata") or {}).get("round"),
                "error_class": cls,
                "command": key[0],
            }
        )

    # open_question loops via judge missing stability
    missing_loops = []
    prev_missing = None
    streak = 0
    for item in judgments or []:
        missing = tuple(sorted(str(x) for x in (item.get("missing") or [])))
        if missing and missing == prev_missing:
            streak += 1
            if streak >= 2:
                missing_loops.append(
                    {
                        "round": item.get("round"),
                        "streak": streak + 1,
                        "missing": list(missing)[:4],
                    }
                )
        else:
            streak = 0
            prev_missing = missing if missing else None

    # same cause after command change: family/class continues while exact key changes
    same_cause_after_switch = []
    prev_key = None
    prev_cls = None
    for event in fails:
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        key = command_key(action)
        cls = event_error_class(event)
        if prev_key and key != prev_key and key[0] and prev_key[0]:
            if cls == prev_cls and cls not in ("other",):
                same_cause_after_switch.append(
                    {
                        "id": event.get("id"),
                        "round": (event.get("metadata") or {}).get("round"),
                        "from_command": prev_key[0],
                        "to_command": key[0],
                        "error_class": cls,
                    }
                )
            # also: empty_sample streak across command switch
            if cls == prev_cls == "empty_sample":
                same_cause_after_switch.append(
                    {
                        "id": event.get("id"),
                        "round": (event.get("metadata") or {}).get("round"),
                        "from_command": prev_key[0],
                        "to_command": key[0],
                        "error_class": cls,
                        "note": "empty_sample_across_switch",
                    }
                )
        prev_key = key if key[0] else prev_key
        prev_cls = cls

    # recalled but same pattern: if research_input had prior_failures / rejected and next fail shares family
    ignored_recall = []
    for item in rounds_detail or []:
        rin = item.get("research_input") or {}
        priors = rin.get("prior_failures") or []
        rejected = rin.get("rejected_commands") or []
        if not priors and not rejected:
            continue
        # look at verified fails this round
        for run in item.get("verified_runs") or []:
            if run.get("ok"):
                continue
            key = command_key({"command": run.get("command"), "args": run.get("args")})
            for p in priors:
                pk = command_key(p)
                if key[0] and pk[0] and key[0] == pk[0]:
                    ignored_recall.append(
                        {
                            "round": item.get("round"),
                            "kind": "same_command_despite_prior",
                            "command": key[0],
                        }
                    )
            # same family token in prior finding/error vs this command
            fam = command_family({"command": run.get("command"), "args": run.get("args")})
            for p in priors:
                pf = command_family(p)
                if fam[1] and fam[1] == pf[1]:
                    ignored_recall.append(
                        {
                            "round": item.get("round"),
                            "kind": "same_family_despite_prior",
                            "family": list(fam),
                        }
                    )

    n = len(fails) or 1
    return {
        "verify_fail_count": len(fails),
        "exact_command_key_repeats": len(exact_repeats),
        "exact_command_key_repeat_rate": round(len(exact_repeats) / n, 3),
        "exact_repeat_examples": exact_repeats[:5],
        "family_repeats": len(family_repeats),
        "family_repeat_rate": round(len(family_repeats) / n, 3),
        "family_repeat_examples": family_repeats[:5],
        "error_class_counts": dict(class_counts),
        "max_error_class_streak": max_class_streak,
        "max_error_class_name": max_class_name,
        "error_class_recurrence": {
            k: v for k, v in class_counts.items() if v >= 2
        },
        "open_question_missing_loops": missing_loops[-5:],
        "missing_loop_events": len(missing_loops),
        "same_cause_after_command_switch": same_cause_after_switch[:8],
        "same_cause_after_switch_count": len(same_cause_after_switch),
        "ignored_recall_signals": ignored_recall[:8],
        "ignored_recall_count": len(ignored_recall),
        "unique_exact_keys": len(exact_seen),
        "unique_families": len(family_seen),
    }


def pick_compare_runs(runs):
    """比較ベンチ直後の末尾 10 本（p4×5 + p5×5）を想定。"""
    # Prefer explicit: last occurrence pairs by scanning reverse for each case twice
    selected = {c: {"phase4": None, "phase5": None} for c in CASES}
    # Walk from end: first hit per case = phase5, second = phase4 (run order)
    counts = Counter()
    for run in reversed(runs):
        for case in CASES:
            if not match_case(run.get("request"), case):
                continue
            counts[case] += 1
            if counts[case] == 1:
                selected[case]["phase5"] = run
            elif counts[case] == 2:
                selected[case]["phase4"] = run
            break
    return selected


def dominant_waste(analysis):
    """ケース内で最も多い無駄パターンを返す。"""
    scores = {
        "exact_command_key_repeat": analysis.get("exact_command_key_repeats") or 0,
        "error_class_recurrence": sum(
            (analysis.get("error_class_recurrence") or {}).values()
        )
        - len(analysis.get("error_class_recurrence") or {}),  # extras beyond first
        "command_family_repeat": analysis.get("family_repeats") or 0,
        "open_question_loop": analysis.get("missing_loop_events") or 0,
        "same_cause_after_switch": analysis.get("same_cause_after_switch_count") or 0,
        "ignored_recall": analysis.get("ignored_recall_count") or 0,
    }
    # error_class extras: count of fails in classes with >=2 minus number of such classes
    # simpler ranking by raw counts above
    if not any(scores.values()):
        return "none_or_exploration_diversity", scores
    top = max(scores.items(), key=lambda kv: kv[1])
    return top[0], scores


def main():
    runs = json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs") or []
    selected = pick_compare_runs(runs)
    per_case = {}
    aggregate = Counter()
    intervention_votes = Counter()

    for case in CASES:
        entry = {"case": case, "phase4": None, "phase5": None}
        for label in ("phase4", "phase5"):
            run = selected[case].get(label)
            if not run:
                entry[label] = {"error": "NOT_FOUND"}
                continue
            pipe = run.get("pipeline") or {}
            analysis = analyze_history(
                pipe.get("research_history") or [],
                judgments=pipe.get("judgments") or [],
                rounds_detail=pipe.get("research_rounds_detail") or [],
            )
            waste, scores = dominant_waste(analysis)
            analysis["dominant_waste"] = waste
            analysis["waste_scores"] = scores
            analysis["pass"] = run.get("pass")
            analysis["fail_stage"] = run.get("fail_stage")
            analysis["rounds"] = (pipe.get("research") or {}).get("rounds")
            analysis["usable_findings"] = len(
                ((pipe.get("research") or {}).get("usable_findings") or [])
            )
            entry[label] = analysis
            if label == "phase5" and analysis.get("rounds") is not None:
                intervention_votes[waste] += 1
                for k, v in scores.items():
                    aggregate[k] += v
        per_case[case] = entry

    # Define intervention targets from evidence
    # Rank waste types by aggregate across phase5 research-reached cases
    ranked = sorted(aggregate.items(), key=lambda kv: -kv[1])
    definitions = {
        "intervene": [],
        "do_not_intervene_as_primary": [],
        "rationale": [],
    }
    # Rules based on observed dominance
    for name, count in ranked:
        if name in (
            "open_question_loop",
            "same_cause_after_switch",
            "error_class_recurrence",
            "command_family_repeat",
        ) and count > 0:
            definitions["intervene"].append(
                {
                    "pattern": name,
                    "observed_weight": count,
                    "policy_hint": {
                        "open_question_loop": "同一 missing 連続時に exploration pivot を強制 / 別経路ヒント",
                        "same_cause_after_switch": "command 変更後も同 error_class なら『原因クラス』を Prompt に明示",
                        "error_class_recurrence": "error_class 単位を exact command_key より優先して Recall",
                        "command_family_repeat": "command_family（Win32_*/Get-* 等）単位で ban/冷却",
                    }.get(name),
                }
            )
        if name == "exact_command_key_repeat":
            definitions["do_not_intervene_as_primary"].append(
                {
                    "pattern": name,
                    "observed_weight": count,
                    "policy_hint": "機械フィルタ banned_actions が既に主担当。Recall の主目標にしない",
                }
            )
        if name == "ignored_recall":
            definitions["intervene"].append(
                {
                    "pattern": name,
                    "observed_weight": count,
                    "policy_hint": "提示しても無視されるなら提示量より『禁止理由の明示 + 別経路必須』が先",
                }
            )

    if not definitions["intervene"]:
        definitions["rationale"].append(
            "Phase5 比較ランでは exact command_key 反復は稀。主無駄はクラス/family/missing ループ系の可能性が高い。"
        )
    definitions["rationale"].append(
        "Memory Recall が介入すべきなのは『同じ command を再実行』より"
        "『同じ原因クラス・同じ open_question・同じ探索ファミリーを回り続けること』。"
    )
    definitions["proposed_recall_targets"] = [
        "error_class streak >= 2（command が変わっても）",
        "command_family の再登場（syntax 違い含む）",
        "同一 missing / open_question が 2+ rounds",
        "prior 提示後に同 family を再提案したとき（ignored_recall）→ mode=repeating + pivot 強制",
    ]
    definitions["non_targets"] = [
        "exact command_key 再実行（banned_actions / filter_rejected に委譲）",
        "単発の新規失敗（fresh）への過剰 History 提示",
    ]

    payload = {
        "cases": per_case,
        "aggregate_waste_weights_phase5": dict(ranked),
        "dominant_waste_votes_phase5": dict(intervention_votes),
        "intervention_definition": definitions,
    }
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("=== PHASE 5.1 REPETITION ANALYSIS ===")
    for case in CASES:
        p5 = per_case[case].get("phase5") or {}
        p4 = per_case[case].get("phase4") or {}
        print(
            f"\n{case}: rounds p4/p5={p4.get('rounds')}/{p5.get('rounds')} "
            f"fails={p5.get('verify_fail_count')} dominant={p5.get('dominant_waste')}"
        )
        print(f"  waste_scores={p5.get('waste_scores')}")
        print(
            f"  exact_repeats={p5.get('exact_command_key_repeats')} "
            f"family_repeats={p5.get('family_repeats')} "
            f"class_streak={p5.get('max_error_class_streak')}:{p5.get('max_error_class_name')} "
            f"missing_loops={p5.get('missing_loop_events')} "
            f"same_cause_switch={p5.get('same_cause_after_switch_count')} "
            f"ignored_recall={p5.get('ignored_recall_count')}"
        )
        print(f"  error_classes={p5.get('error_class_counts')}")

    print("\n=== AGGREGATE (phase5) ===")
    print(dict(ranked))
    print("dominant votes:", dict(intervention_votes))
    print("\n=== INTERVENTION DEFINITION ===")
    print(json.dumps(definitions, ensure_ascii=False, indent=2))
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
