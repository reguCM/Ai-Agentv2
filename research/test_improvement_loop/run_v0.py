"""Run テスト改善ループ against the H4 Adoption Gate false-AUTO cases.

Stage order is enforced by Orchestrator. No LLM. No production promote.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.test_improvement_loop.adapters.h4_gate import score_ids
from research.test_improvement_loop.orchestrator import Orchestrator, StageViolation
from research.test_improvement_loop.schema import DISPLAY_NAME, empty_run, new_candidate, new_case
from research.test_improvement_loop.validation_gate import confirm_records

BENCH = ROOT / "research" / "llm_benchmarks" / "h4_decision_maker_bench"
BATCH_DIR = BENCH / "results" / "20260908T165641Z"
GATE_10_DIR = BENCH / "results" / "20260908T213718Z"
BEFORE_10_DIR = BENCH / "results" / "20260908T220502Z"
BEFORE_5_DIR = BENCH / "results" / "20260908T220515Z"
BEFORE_Q28_DIR = BENCH / "results" / "20260908T220607Z"
PACKAGE_DIR = Path(__file__).resolve().parent
RUNS = PACKAGE_DIR / "runs"

CANARY_1_IDS = ["Q31"]
VALIDATE_5_IDS = ["Q8", "Q16", "Q27", "Q31", "Q2"]
TARGET_IDS = [
    "Q9",
    "Q25",
    "Q29",
    "Q14-15",
    "Q30",
    "Q7",
    "Q10",
    "Q40",
    "Q47",
    "Q1",
    "Q28",
    "Q2",
    "Q31",
]
HOLDOUT_1_IDS = ["Q26"]
HOLDOUT_5_IDS = ["Q26", "Q32", "Q34", "Q36", "Q39"]

TRUE_AUTO_REGRESSION = {"Q29", "Q30", "Q10", "Q40", "Q47", "Q1", "Q8", "Q16", "Q27"}
MUST_NOT_AUTO = {"Q31", "Q2"}
TRUE_REVIEW_REGRESSION = {"Q9", "Q25", "Q14-15", "Q7", "Q28"}

GATE_DIRS = [GATE_10_DIR, BEFORE_Q28_DIR, BEFORE_5_DIR]


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_pytest() -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        str(BENCH / "test_adoption_gate.py"),
        str(PACKAGE_DIR / "tests" / "test_orchestrator_stages.py"),
        str(PACKAGE_DIR / "tests" / "test_validation_gate.py"),
        str(PACKAGE_DIR / "tests" / "test_naming.py"),
    ]
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
        "wall_s": round(time.perf_counter() - started, 3),
    }


def score(ids: list[str]) -> dict[str, Any]:
    return score_ids(ids, batch_dir=BATCH_DIR, gate_dirs=GATE_DIRS)


def _by_id(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(r["decision_id"]): r for r in result.get("records") or []}


def confirm_canary(result: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    recs = result.get("records") or []
    if len(recs) != 1:
        reasons.append(f"expected 1 record, got {len(recs)}")
        return False, reasons
    rec = recs[0]
    if rec.get("parse_failure") or rec.get("missing_output"):
        reasons.append("parse/output missing")
    if rec.get("route") == "AUTO":
        reasons.append("false AUTO remains on canary")
    if rec.get("semantic_gate") != "FAIL":
        reasons.append(f"expected Gate 1 FAIL, got {rec.get('semantic_gate')}")
    if rec.get("semantic_dangerous") is None or rec.get("semantic_dangerous") == []:
        reasons.append("expected semantic dangerous (cardinality invariant)")
    _, extra = confirm_records(result, n=1, forbid_false_auto=True, forbid_human=True)
    reasons.extend(extra)
    return (not reasons), reasons


def confirm_validate_5(result: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    by_id = _by_id(result)
    if set(by_id) != set(VALIDATE_5_IDS):
        reasons.append("id set mismatch")
    if result["summary"].get("parse_failure") or result["summary"].get("missing_output"):
        reasons.append("parse/output missing")
    if result["summary"].get("HUMAN"):
        reasons.append("unexpected HUMAN")
    for did in ("Q8", "Q16", "Q27"):
        if by_id.get(did, {}).get("route") != "AUTO":
            reasons.append(f"true AUTO regression {did} -> {by_id.get(did, {}).get('route')}")
    if by_id.get("Q31", {}).get("route") == "AUTO":
        reasons.append("Q31 still AUTO")
    if by_id.get("Q2", {}).get("route") == "AUTO":
        reasons.append("Q2 still AUTO")
    if by_id.get("Q2", {}).get("route") not in ("REVIEW", "HUMAN"):
        reasons.append(f"Q2 expected REVIEW, got {by_id.get('Q2', {}).get('route')}")
    _, extra = confirm_records(result, n=5, forbid_false_auto=True, forbid_human=True)
    reasons.extend(extra)
    return (not reasons), reasons


def confirm_target(result: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    by_id = _by_id(result)
    if result["summary"].get("parse_failure") or result["summary"].get("missing_output"):
        reasons.append("parse/output missing")
    if result["summary"].get("HUMAN"):
        reasons.append("unexpected HUMAN")
    for did in sorted(TRUE_AUTO_REGRESSION):
        if did in by_id and by_id[did].get("route") != "AUTO":
            reasons.append(f"true AUTO regression {did} -> {by_id[did].get('route')}")
    for did in sorted(TRUE_REVIEW_REGRESSION):
        if did in by_id and by_id[did].get("route") == "AUTO":
            reasons.append(f"expected REVIEW {did} became AUTO")
    for did in sorted(MUST_NOT_AUTO):
        if did in by_id and by_id[did].get("route") == "AUTO":
            reasons.append(f"false AUTO remains {did}")
    _, extra = confirm_records(result, forbid_false_auto=True, forbid_human=True)
    reasons.extend(extra)
    return (not reasons), reasons


def confirm_holdout(result: dict[str, Any], *, n: int) -> tuple[bool, list[str]]:
    return confirm_records(
        result,
        n=n,
        forbid_human=True,
        forbid_false_auto=True,
    )


def before_snapshot() -> dict[str, Any]:
    ten = _load(BEFORE_10_DIR / "routing_rescore.json")
    five = _load(BEFORE_5_DIR / "gate_results.json")
    q28 = _load(BEFORE_Q28_DIR / "gate_results.json")
    routes = {}
    for rec in (ten.get("records") or []):
        routes[rec["decision_id"]] = rec.get("route")
    for rec in (five.get("records") or []):
        routes[rec["decision_id"]] = rec.get("route")
    for rec in (q28.get("records") or []):
        routes[rec["decision_id"]] = rec.get("route")
    return {
        "source": {
            "ten": str(BEFORE_10_DIR),
            "five": str(BEFORE_5_DIR),
            "q28": str(BEFORE_Q28_DIR),
        },
        "routes": routes,
        "note": "Pre-upgrade Gate 2 routes from saved artifacts. No new LLM.",
    }


def compare_before_after(before: dict[str, Any], after_records: list[dict[str, Any]]) -> dict[str, Any]:
    before_routes = before.get("routes") or {}
    flipped: list[dict[str, str]] = []
    true_auto_dropped = []
    false_auto_fixed = []
    for rec in after_records:
        did = rec["decision_id"]
        prev = before_routes.get(did)
        now = rec["route"]
        if prev and prev != now:
            flipped.append({"decision_id": did, "before": prev, "after": now})
        if did in TRUE_AUTO_REGRESSION and prev == "AUTO" and now != "AUTO":
            true_auto_dropped.append(did)
        if did in MUST_NOT_AUTO and prev == "AUTO" and now != "AUTO":
            false_auto_fixed.append(did)
    return {
        "flipped": flipped,
        "true_auto_dropped": true_auto_dropped,
        "false_auto_fixed": false_auto_fixed,
        "false_auto_remaining": [
            rec["decision_id"]
            for rec in after_records
            if rec["decision_id"] in MUST_NOT_AUTO and rec["route"] == "AUTO"
        ],
    }


def human_review_markdown(packet: dict[str, Any]) -> str:
    d = packet["decision"]
    cands = packet["candidates"]
    lines = [
        f"# Human Review Packet — {DISPLAY_NAME}",
        "",
        "Production Runtime は変更していません。Promote / push はしていません。",
        "",
        "## 何が問題だったか",
        "",
        "- Case A: 複数候補に対して first/[0]/head を採用したまま AUTO になった。",
        "- Case B: add / do-not-add の Decision fork が閉じないまま AUTO になった。",
        "",
        "## どの Test Case で発見したか",
        "",
        "- 未使用 replay の保存済み Local 回答（証拠 ID は Q31 / Q2。ルールには Q番号を書いていない）。",
        "",
        "## 原因をどう一般化したか",
        "",
    ]
    for c in cands:
        lines.append(f"- **{c['case_id']}** ({c['upgrade_type']}): {c['generalized_cause']}")
    lines += [
        "",
        "## System のどの層を変更したか",
        "",
        "- `research/llm_benchmarks/h4_decision_maker_bench/adoption_gate.py`",
        "- Case A → Gate 1 Known Wrong（semantic FAIL）",
        "- Case B → Gate 2 Routing（REVIEW）",
        "",
        "## Before",
        "",
        f"- false AUTO 証拠: {packet['before']['routes'].get('Q31')} / {packet['before']['routes'].get('Q2')}",
        "",
        "## After",
        "",
        f"- 判定: `{d['verdict']}`",
        f"- false AUTO 修正: {packet['metrics'].get('false_auto_fixed')}",
        f"- true AUTO 脱落: {packet['metrics'].get('true_auto_dropped')}",
        "",
        "## Regression",
        "",
        f"- pytest: {'PASS' if packet['pytest']['passed'] else 'FAIL'}",
        f"- target confirm: {packet['confirm']['target']}",
        "",
        "## 副作用",
        "",
        f"- route flips: {packet['metrics'].get('flipped')}",
        "",
        "## Known Risk",
        "",
        "- Gate 1 の cardinality 規則が、禁止例の言及を adopt と誤認する余地（否定検出に依存）。",
        "- Gate 2 polarity が、異なる目的語への add / do-not-add を同一 fork と見なす余地。",
        "",
        "## Production へ入れると何が変わるか",
        "",
        "- まだ入れない。実験領域の Adoption Gate のみ。",
        "- 入れる場合: Local first_recommendation の [0]/first 採用は FAIL→1回制約再提示、未閉じ polarity は AUTO しない。",
        "",
        "## 推奨",
        "",
        f"- **{packet['recommendation']}**",
        "",
        f"## {DISPLAY_NAME} 自己評価",
        "",
    ]
    for k, v in (packet.get("system_eval") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    out_dir = RUNS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)

    orch = Orchestrator()
    run = empty_run("h4-false-auto-v0")
    run["applied_change"] = [
        "general Gate 1 cardinality_index_or_head_select (decision_ids=None)",
        "Gate 2 polarity_fork_unclosed",
    ]
    candidates = [
        new_candidate(
            case_id="h4-cardinality-index-select",
            upgrade_type="adoption_gate",
            problem="Index/head selection among 2+ routed AUTO.",
            generalized_cause="Selection/Cardinality invariant missing as a Gate 1 Known Wrong for adopt-not-mention.",
            proposed_change="Add a decision_id-less Known Wrong: adopt first/[0]/head among 2+ is FAIL; reject/mention-as-forbidden is not.",
            why_this_layer="H4 contract already forbids [0] ranking / first-of-multiple inject. That is a forbidden action, so Gate 1 semantic FAIL (retry with contract), not merely Gate 2 REVIEW.",
            affected_assets=["adoption_gate.py GATE_RULES"],
            known_risks=["false FAIL if a rec forbids [0] but still matches adopt_res first"],
            alternatives_considered=[
                "Gate 2 REVIEW only — too weak; Known Wrong would still be AUTO-eligible after PASS",
                "Q31-only if decision_id — forbidden individual patch",
            ],
            rollback_or_revert_hint="Remove GATE_RULES entry cardinality_index_or_head_select.",
        ),
        new_candidate(
            case_id="h4-decision-polarity-unclosed",
            upgrade_type="adoption_gate",
            problem="Mixed add + keywords-only / do-not-add still AUTO.",
            generalized_cause="Decision completeness/polarity: question offers both poles and rec asserts both.",
            proposed_change="Gate 2 REVIEW when polarity_fork_unclosed(question, rec).",
            why_this_layer="Not a single forbidden Known Wrong; the rec is incomplete rather than adopting one banned action. AUTO requires a uniquely closed decision.",
            affected_assets=["adoption_gate.py polarity_fork_unclosed"],
            known_risks=["false REVIEW if add X / do-not-add Y are actually consistent closures"],
            alternatives_considered=["Gate 1 FAIL — too strong for an unclosed fork", "HUMAN — not a user value judgment"],
            rollback_or_revert_hint="Remove polarity_fork_unclosed check in route_final.",
        ),
    ]
    cases = [
        new_case(
            case_id="h4-cardinality-index-select",
            source="h4_decision_maker_bench",
            source_test="saved unused replay",
            source_failure="false_AUTO",
            observed_failure="Inject only [0] routed AUTO",
            expected_invariant="Adopt [0]/first/head among 2+ => Gate 1 FAIL",
            evidence=["CANARY_1 evidence id Q31"],
            target_layer="adoption_gate",
            upgrade_type="adoption_gate",
            severity="high",
            status="experimental",
        ),
        new_case(
            case_id="h4-decision-polarity-unclosed",
            source="h4_decision_maker_bench",
            source_test="saved unused replay",
            source_failure="false_AUTO",
            observed_failure="add + keywords only routed AUTO",
            expected_invariant="Unclosed polarity => not AUTO",
            evidence=["VALIDATE_5 evidence id Q2"],
            target_layer="adoption_gate",
            upgrade_type="adoption_gate",
            severity="medium",
            status="experimental",
        ),
    ]

    pytest_res = run_pytest()
    run["validation_steps"].append({"name": "deterministic_pytest", **{k: pytest_res[k] for k in ("passed", "returncode", "wall_s")}})
    _dump(out_dir / "pytest.json", pytest_res)
    if not pytest_res["passed"]:
        orch.stop("deterministic_pytest_fail")
        _dump(out_dir / "upgrade_run.json", {**run, "stage": orch.stage, "stopped": orch.stopped_reason})
        print("STOP pytest fail", flush=True)
        return 1

    before = before_snapshot()
    run["before_result"] = before
    _dump(out_dir / "before.json", before)

    orch.begin_attempt()
    try:
        one = orch.run_stage(CANARY_1_IDS, score)
    except StageViolation as exc:
        orch.stop(str(exc))
        _dump(out_dir / "upgrade_run.json", {**run, "stopped": str(exc)})
        return 1
    run["one_case_result"] = one
    _dump(out_dir / "stage_canary_1.json", one)
    ok, reasons = confirm_canary(one)
    if not orch.confirm_and_advance(ok=ok, reasons=reasons, next_stage="VALIDATE_5"):
        _dump(out_dir / "upgrade_run.json", {**run, "stage": "STOP", "stopped": orch.stopped_reason})
        _write_packet(out_dir, cases, candidates, run, pytest_res, before, {}, "More Test", orch)
        print("STOP canary", reasons, flush=True)
        return 2

    five = orch.run_stage(VALIDATE_5_IDS, score)
    run["five_case_result"] = five
    _dump(out_dir / "stage_validate_5.json", five)
    ok, reasons = confirm_validate_5(five)
    if not orch.confirm_and_advance(ok=ok, reasons=reasons, next_stage="TARGET"):
        _dump(out_dir / "upgrade_run.json", {**run, "stage": "STOP", "stopped": orch.stopped_reason})
        _write_packet(out_dir, cases, candidates, run, pytest_res, before, {}, "More Test", orch)
        print("STOP validate5", reasons, flush=True)
        return 2

    target = orch.run_stage(TARGET_IDS, score)
    run["target_result"] = target
    run["after_result"] = target
    _dump(out_dir / "stage_target.json", target)
    ok, reasons = confirm_target(target)
    metrics = compare_before_after(before, target.get("records") or [])
    run["metrics"] = metrics
    run["regression_result"] = {"ok": ok, "reasons": reasons}
    if not orch.confirm_and_advance(ok=ok, reasons=reasons, next_stage="HOLDOUT_1"):
        _dump(out_dir / "upgrade_run.json", {**run, "stage": "STOP", "stopped": orch.stopped_reason})
        _write_packet(out_dir, cases, candidates, run, pytest_res, before, metrics, "Reject", orch)
        print("STOP target", reasons, flush=True)
        return 2

    hold1 = orch.run_stage(HOLDOUT_1_IDS, score)
    run["holdout_one_result"] = hold1
    _dump(out_dir / "stage_holdout_1.json", hold1)
    ok, reasons = confirm_holdout(hold1, n=1)
    if not orch.confirm_and_advance(ok=ok, reasons=reasons, next_stage="HOLDOUT_5"):
        _dump(out_dir / "upgrade_run.json", {**run, "stage": "STOP", "stopped": orch.stopped_reason})
        _write_packet(out_dir, cases, candidates, run, pytest_res, before, metrics, "More Test", orch)
        print("STOP holdout1", reasons, flush=True)
        return 2

    hold5 = orch.run_stage(HOLDOUT_5_IDS, score)
    run["holdout_five_result"] = hold5
    _dump(out_dir / "stage_holdout_5.json", hold5)
    ok, reasons = confirm_holdout(hold5, n=5)
    if not ok:
        orch.stop("holdout5_confirm_fail: " + "; ".join(reasons))
        rec = "More Test"
        verdict = "inconclusive"
    else:
        orch.stop("completed_to_holdout_5")
        rec = "Adopt" if not metrics.get("true_auto_dropped") and not metrics.get("false_auto_remaining") else "More Test"
        verdict = "improved" if rec == "Adopt" else "inconclusive"

    run["stage"] = orch.stage
    run["stopped"] = orch.stopped_reason
    run["history"] = orch.history
    _dump(out_dir / "upgrade_run.json", run)

    decision = {
        "verdict": verdict,
        "improved": verdict == "improved",
        "not_improved": verdict == "not_improved",
        "inconclusive": verdict == "inconclusive",
        "remaining_risks": [
            "polarity add X / do-not-add Y false REVIEW",
            "cardinality mention vs adopt",
        ],
        "production_candidate": False,
        "needs_human_review": True,
    }
    _write_packet(out_dir, cases, candidates, run, pytest_res, before, metrics, rec, orch, decision)
    print(json.dumps({"out_dir": str(out_dir), "recommendation": rec, "verdict": verdict, "metrics": metrics}, ensure_ascii=False, indent=2), flush=True)
    return 0


def _write_packet(
    out_dir: Path,
    cases: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    run: dict[str, Any],
    pytest_res: dict[str, Any],
    before: dict[str, Any],
    metrics: dict[str, Any],
    recommendation: str,
    orch: Orchestrator,
    decision: dict[str, Any] | None = None,
) -> None:
    decision = decision or {
        "verdict": "inconclusive",
        "improved": False,
        "not_improved": False,
        "inconclusive": True,
        "remaining_risks": list((metrics or {}).get("true_auto_dropped") or []),
        "production_candidate": False,
        "needs_human_review": True,
    }
    packet = {
        "cases": cases,
        "candidates": candidates,
        "decision": decision,
        "recommendation": recommendation,
        "before": before,
        "metrics": metrics,
        "pytest": {"passed": pytest_res.get("passed"), "wall_s": pytest_res.get("wall_s")},
        "confirm": {
            "canary": (run.get("one_case_result") or {}).get("summary"),
            "validate5": (run.get("five_case_result") or {}).get("summary"),
            "target": (run.get("target_result") or {}).get("summary"),
            "holdout1": (run.get("holdout_one_result") or {}).get("summary"),
            "holdout5": (run.get("holdout_five_result") or {}).get("summary"),
        },
        "system_eval": {
            "intake": "yes",
            "target_layer": "adoption_gate for both cases after contract survey",
            "general_rule_not_qid_patch": "yes (decision_ids=None + polarity on question/rec text)",
            "progressive_validation": f"orchestrator stage={orch.stage} stopped={orch.stopped_reason}",
            "before_after": "yes (saved artifacts vs rescore)",
            "regression": "pytest + true AUTO set",
            "human_packet": "yes",
            "reuse": "schema/orchestrator not bound to H4; adapter is H4-specific",
            "v0_gaps": "no LLM analyst loop, no production apply, no UI, holdout 10 not run",
        },
        "llm_called": False,
        "production_runtime_changed": False,
        "promoted": False,
    }
    _dump(out_dir / "human_review_packet.json", packet)
    (out_dir / "HUMAN_REVIEW.md").write_text(human_review_markdown(packet), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
