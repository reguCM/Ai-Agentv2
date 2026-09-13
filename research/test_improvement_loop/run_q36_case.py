"""Independent Q36 case for テスト改善ループ.

Stage order is enforced by Orchestrator: 1 → confirm → 5 → confirm → target
→ holdout 1 → holdout 5. No LLM. No production promote.
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
from research.test_improvement_loop.run_v0 import (
    BATCH_DIR,
    GATE_DIRS,
    TARGET_IDS as PREV_TARGET_IDS,
    TRUE_AUTO_REGRESSION,
    TRUE_REVIEW_REGRESSION,
    before_snapshot,
)
from research.test_improvement_loop.schema import DISPLAY_NAME, empty_run, new_candidate, new_case
from research.test_improvement_loop.validation_gate import confirm_records

BENCH = ROOT / "research" / "llm_benchmarks" / "h4_decision_maker_bench"
PACKAGE_DIR = Path(__file__).resolve().parent
RUNS = PACKAGE_DIR / "runs"
PREV_V0 = RUNS / "20260908T223431Z"
PREV_HOLDOUT = PREV_V0 / "stage_holdout_5.json"

CANARY_1_IDS = ["Q36"]
VALIDATE_5_IDS = ["Q26", "Q32", "Q34", "Q39", "Q36"]
# Previous 13 + Q36. Q8/Q16/Q27 are true AUTO that lived in the v0 VALIDATE_5
# neighborhood, not in that 13; include them here so the regression set is scored.
TARGET_IDS = list(dict.fromkeys(list(PREV_TARGET_IDS) + ["Q36", "Q8", "Q16", "Q27"]))
HOLDOUT_1_IDS = ["Q33"]
HOLDOUT_5_IDS = ["Q33", "Q37", "Q41", "Q23", "Q42"]

MUST_NOT_AUTO = {"Q31", "Q2", "Q36"}
TRUE_AUTO_VALIDATE = ("Q26", "Q32", "Q34", "Q39")


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def score(ids: list[str]) -> dict[str, Any]:
    return score_ids(ids, batch_dir=BATCH_DIR, gate_dirs=GATE_DIRS)


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


def confirm_canary(result: dict[str, Any]) -> tuple[bool, list[str]]:
    ok, reasons = confirm_records(
        result,
        n=1,
        require_ids=("Q36",),
        forbid_auto=("Q36",),
        forbid_human=True,
        forbid_false_auto=True,
    )
    recs = result.get("records") or []
    rec = recs[0] if recs else {}
    if rec.get("semantic_gate") != "FAIL":
        reasons.append(f"expected Gate 1 FAIL, got {rec.get('semantic_gate')}")
        ok = False
    dangerous = rec.get("semantic_dangerous") or []
    if not any(s.get("rule_id") == "shared_keyword_family_prefer" for s in dangerous):
        reasons.append("expected shared_keyword_family_prefer")
        ok = False
    return ok, reasons


def confirm_validate_5(result: dict[str, Any]) -> tuple[bool, list[str]]:
    return confirm_records(
        result,
        n=5,
        require_ids=tuple(VALIDATE_5_IDS),
        require_auto=TRUE_AUTO_VALIDATE,
        forbid_auto=("Q36",),
        forbid_human=True,
        forbid_false_auto=True,
    )


def confirm_target(result: dict[str, Any]) -> tuple[bool, list[str]]:
    ok, reasons = confirm_records(
        result,
        n=len(TARGET_IDS),
        require_ids=tuple(TARGET_IDS),
        require_auto=tuple(sorted(TRUE_AUTO_REGRESSION)),
        forbid_auto=tuple(sorted(MUST_NOT_AUTO)),
        forbid_human=True,
        forbid_false_auto=True,
    )
    by_id = {str(r["decision_id"]): r for r in result.get("records") or []}
    for did in sorted(TRUE_REVIEW_REGRESSION):
        if by_id.get(did, {}).get("route") == "AUTO":
            reasons.append(f"expected REVIEW {did} became AUTO")
            ok = False
    return ok, reasons


def confirm_holdout(result: dict[str, Any], *, n: int, ids: list[str]) -> tuple[bool, list[str]]:
    return confirm_records(
        result,
        n=n,
        require_ids=tuple(ids),
        forbid_human=True,
        forbid_false_auto=True,
    )


def q36_before() -> dict[str, Any]:
    """Before this case: v0 after-routes, with Q36 still AUTO from that holdout."""
    base = before_snapshot()
    for name in ("stage_validate_5.json", "stage_target.json", "stage_holdout_5.json"):
        path = PREV_V0 / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rec in payload.get("records") or []:
            base["routes"][rec["decision_id"]] = rec.get("route")
    base["v0_run"] = str(PREV_V0)
    base["q36_previous_holdout"] = str(PREV_HOLDOUT)
    base["note"] = (
        "Baseline is テスト改善ループ v0 after-routes. Q36 was AUTO on that holdout 5 "
        "because confirm only checked parse/HUMAN. Validation Gate now scores "
        "hidden_eval danger_if / rejected poles."
    )
    return base


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
        f"# Human Review Packet — {DISPLAY_NAME} / Q36",
        "",
        "Production Runtime は変更していません。Promote / push はしていません。",
        "",
        "## 何が問題だったか",
        "",
        "- 横断共有キーワードだけでは family を確定できないのに、片方（web_search）へ prefer したまま AUTO になった。",
        "- 前回 Holdout 5 の confirm は parse / HUMAN だけを見て、hidden_eval の期待結果を接続していなかった。",
        "",
        "## どの Test Case で発見したか",
        "",
        "- 前回 Upgrade の Holdout 5 保存済み Local 回答（証拠 ID は Q36。ルールには Q番号を書いていない）。",
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
        "- Validation Gate: `research/test_improvement_loop/validation_gate.py`（stage confirm に hidden_eval を接続）",
        "- Experimental Gate 1: `shared_keyword_family_prefer`（decision_ids=None）",
        "- Q2 / Q31 の一般則は Experimental Gate に保持",
        "",
        "## Before",
        "",
        f"- Q36 route: {packet['before']['routes'].get('Q36')}",
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
        "- shared-token prefer 規則が、正当な family 指定の prefer を FAIL する余地（web_search への prefer 文言に依存）。",
        "- Validation Gate の synonym は danger_if テキスト由来。英語 rec と日本語 danger が食い違うと見逃す。",
        "",
        "## Production へ入れると何が変わるか",
        "",
        "- まだ入れない。実験領域の Adoption Gate / Validation Gate のみ。",
        "",
        "## 推奨",
        "",
        f"- **{packet['recommendation']}**",
        "",
        "## 次段階（未実施）",
        "",
        "- 上位 LLM による Failure分析 → Upgrade分類 → Candidate生成 の自動 Loop は次段階として検討するだけ。本 run では呼んでいない。",
        "",
        f"## {DISPLAY_NAME} 自己評価",
        "",
    ]
    for k, v in (packet.get("system_eval") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines) + "\n"


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
            "target_layer": "validation_gate + adoption_gate Gate 1",
            "general_rule_not_qid_patch": "yes (decision_ids=None)",
            "progressive_validation": f"orchestrator stage={orch.stage} stopped={orch.stopped_reason}",
            "before_after": "yes (previous holdout AUTO vs rescore)",
            "regression": "pytest + true AUTO set + contract false-AUTO",
            "human_packet": "yes",
            "reuse": "same orchestrator; independent case runner",
            "v0_gaps": "no LLM analyst loop, no production apply, no UI",
        },
        "llm_called": False,
        "production_runtime_changed": False,
        "promoted": False,
    }
    _dump(out_dir / "human_review_packet.json", packet)
    (out_dir / "HUMAN_REVIEW.md").write_text(human_review_markdown(packet), encoding="utf-8")


def main() -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    out_dir = RUNS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)

    orch = Orchestrator()
    run = empty_run("h4-shared-keyword-family-prefer")
    run["applied_change"] = [
        "Validation Gate connects hidden_eval danger_if/rejected to stage confirm",
        "general Gate 1 shared_keyword_family_prefer (decision_ids=None)",
    ]
    candidates = [
        new_candidate(
            case_id="h4-shared-keyword-family-prefer",
            upgrade_type="adoption_gate",
            problem="Shared/cross-cutting keyword was treated as confirming one family (web_search) and still AUTO.",
            generalized_cause=(
                "Family confirmation from a shared token is a Known Wrong. "
                "Unnegated prefer/confirm of one family is FAIL even if the rec also says avoid shared keywords."
            ),
            proposed_change=(
                "Add a decision_id-less Known Wrong: unnegated prefer/confirm of one family "
                "from a shared keyword is FAIL; all-negated mention is not."
            ),
            why_this_layer=(
                "H4 contract already forbids confirming web from 検索 alone. "
                "That is a forbidden action, so Gate 1 semantic FAIL, not merely Gate 2 REVIEW."
            ),
            affected_assets=["adoption_gate.py GATE_RULES", "validation_gate.py"],
            known_risks=["false FAIL if a rec legitimately prefers web_search for a non-shared reason using the same phrase"],
            alternatives_considered=[
                "Gate 2 REVIEW only — too weak; Known Wrong would still be AUTO-eligible after PASS",
                "Q36-only if decision_id — forbidden individual patch",
            ],
            rollback_or_revert_hint="Remove GATE_RULES entry shared_keyword_family_prefer.",
        )
    ]
    cases = [
        new_case(
            case_id="h4-shared-keyword-family-prefer",
            source="h4_decision_maker_bench",
            source_test="previous holdout 5 saved replay",
            source_failure="false_AUTO",
            observed_failure="Prefer adding to web_search routed AUTO",
            expected_invariant="Unnegated family prefer from shared token => Gate 1 FAIL",
            evidence=["CANARY_1 evidence id Q36"],
            target_layer="adoption_gate",
            upgrade_type="adoption_gate",
            severity="high",
            status="experimental",
        )
    ]

    pytest_res = run_pytest()
    run["validation_steps"].append(
        {"name": "deterministic_pytest", **{k: pytest_res[k] for k in ("passed", "returncode", "wall_s")}}
    )
    _dump(out_dir / "pytest.json", pytest_res)
    if not pytest_res["passed"]:
        orch.stop("deterministic_pytest_fail")
        _dump(out_dir / "upgrade_run.json", {**run, "stage": orch.stage, "stopped": orch.stopped_reason})
        print("STOP pytest fail", pytest_res.get("stdout"), pytest_res.get("stderr"), flush=True)
        return 1

    before = q36_before()
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
    ok, reasons = confirm_holdout(hold1, n=1, ids=HOLDOUT_1_IDS)
    if not orch.confirm_and_advance(ok=ok, reasons=reasons, next_stage="HOLDOUT_5"):
        _dump(out_dir / "upgrade_run.json", {**run, "stage": "STOP", "stopped": orch.stopped_reason})
        _write_packet(out_dir, cases, candidates, run, pytest_res, before, metrics, "More Test", orch)
        print("STOP holdout1", reasons, flush=True)
        return 2

    hold5 = orch.run_stage(HOLDOUT_5_IDS, score)
    run["holdout_five_result"] = hold5
    _dump(out_dir / "stage_holdout_5.json", hold5)
    ok, reasons = confirm_holdout(hold5, n=5, ids=HOLDOUT_5_IDS)
    if not ok:
        orch.stop("holdout5_confirm_fail: " + "; ".join(reasons))
        rec = "More Test"
        verdict = "inconclusive"
    else:
        orch.stop("completed_to_holdout_5")
        rec = (
            "Adopt"
            if not metrics.get("true_auto_dropped") and not metrics.get("false_auto_remaining")
            else "More Test"
        )
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
            "shared-token prefer phrase overmatch",
            "hidden_eval English/Japanese synonym miss",
        ],
        "production_candidate": False,
        "needs_human_review": True,
    }
    _write_packet(out_dir, cases, candidates, run, pytest_res, before, metrics, rec, orch, decision)
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "recommendation": rec,
                "verdict": verdict,
                "metrics": metrics,
                "holdout5": hold5.get("summary"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
