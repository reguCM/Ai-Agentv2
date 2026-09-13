import collections
import json
import sys
from datetime import datetime
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT, bootstrap_repo_root

bootstrap_repo_root()
ROOT = REPO_ROOT

RESULTS_PATH = ROOT / "research" / "llm_benchmarks" / "research_implement_results.json"


def parse_ts(x):
    if not x:
        return None
    try:
        return datetime.fromisoformat(x)
    except Exception:
        return None


def classify_category(r):
    if r.get("pass") is True:
        return "PASS"
    fs = r.get("fail_stage")
    v1 = r.get("validation_1")
    vng = isinstance(v1, dict) and v1.get("result") == "NG"
    if fs == "research":
        return "research"
    if fs == "judge":
        return "judge"
    if fs == "proposal":
        return "proposal"
    if fs == "repair":
        return "repair"
    if fs == "implementation":
        return "validation" if vng else "implementation"
    if vng:
        return "validation"
    return "other"


def stage_ok(run, key):
    ps = run.get("pipeline_stages") or {}
    item = ps.get(key) or {}
    return bool(item.get("ok"))


def main():
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    runs = results.get("runs") or []

    # 「現在版（未確認メモ warning 化が効いた後）」だけを見る。
    # fatal NG に相当するエラー文字列が最後に出た時刻より後だけを対象にする。
    fatal_msg = "[unimplemented] 未確認項目があるのに unimplemented が空です"
    last_fatal_ts = None
    for r in runs:
        v1 = r.get("validation_1")
        if (
            isinstance(v1, dict)
            and v1.get("errors")
            and any(fatal_msg == e for e in (v1.get("errors") or []))
        ):
            ts = parse_ts(r.get("timestamp"))
            if ts and (last_fatal_ts is None or ts > last_fatal_ts):
                last_fatal_ts = ts

    # 念のため: 最初の fatal がなければ validation_1 保存開始時点から
    if last_fatal_ts is None:
        validation_runs = [r for r in runs if isinstance(r.get("validation_1"), dict)]
        cutoff = min(
            (parse_ts(r.get("timestamp")) for r in validation_runs),
            default=datetime.min,
        )
    else:
        cutoff = last_fatal_ts

    target = []
    for r in runs:
        ts = parse_ts(r.get("timestamp"))
        if ts and ts > cutoff:
            target.append(r)

    cats = collections.Counter(classify_category(r) for r in target)
    total = len(target)
    pass_cnt = cats.get("PASS", 0)

    # Implementation failures (exclude validation)
    impl_fail = [r for r in target if classify_category(r) == "implementation"]
    empty = 0
    other = 0
    for r in impl_fail:
        ic = (r.get("implementation_class") or {}).get("class")
        if ic == "empty_code":
            empty += 1
        else:
            other += 1

    fail_cats = ["research", "judge", "proposal", "implementation", "validation", "repair", "other"]
    fail_total = total - pass_cnt
    if fail_total == 0:
        bottleneck = "none"
    else:
        bottleneck = max(fail_cats, key=lambda k: cats.get(k, 0))

    latest = None
    if target:
        latest = max(target, key=lambda r: parse_ts(r.get("timestamp")) or datetime.min)

    research_ok = latest and stage_ok(latest, "candidates_generated")
    verifier_ok = latest and stage_ok(latest, "verifier_ran")
    judge_ok = latest and stage_ok(latest, "judge_adopted")
    proposal_ok = latest and isinstance(latest.get("proposal"), dict) and bool(
        latest.get("proposal").get("module")
    )
    implementation_ok = latest and stage_ok(latest, "implementation_code")
    validation_ok = latest and isinstance(latest.get("validation_1"), dict) and latest["validation_1"].get(
        "result"
    ) == "OK"
    registry_ok = latest and (
        (latest.get("registered") or {}).get("result") == "OK"
        or (latest.get("checks") or {}).get("registry", {}).get("ok") is True
    )
    runs_ok = latest and (
        (latest.get("checks") or {}).get("runs", {}).get("ok") is True
        or (latest.get("checks") or {}).get("tool_runs", {}).get("ok") is True
    )

    # Required report format
    print("対象run数:")
    print(f"PASS: {pass_cnt}")
    print(f"FAIL: {total - pass_cnt}")
    print("")
    print("fail_stage:")
    for key in ["research", "judge", "proposal", "implementation", "validation", "repair", "other"]:
        c = cats.get(key, 0)
        ratio = (c / total) if total else 0
        print(f"{key}: {c} / {total} = {ratio:.3f}")
    print("")
    print("Implementation failure:")
    print(f"empty_code: {empty}")
    print(f"その他: {other}")
    print("")
    print("現在の最有力ボトルネック:")
    print("根拠:")
    if bottleneck == "none":
        print("  bottleneck=none (FAIL=0 in target period)")
    else:
        print(f"  bottleneck={bottleneck} (fail counts={{k:cats.get(k,0) for k in fail_cats}})")
    print(f"  latest_run_ts={latest.get('timestamp') if latest else None}")
    print(
        "  reach:"
        f" Research={bool(research_ok)}"
        f" -> Verifier={bool(verifier_ok)}"
        f" -> Judge={bool(judge_ok)}"
        f" -> Proposal={bool(proposal_ok)}"
        f" -> Implementation={bool(implementation_ok)}"
        f" -> Validation={bool(validation_ok)}"
        f" -> Registry={bool(registry_ok)}"
        f" -> Tool execution={bool(runs_ok)}"
    )

    print("")
    print("次に孤立ベンチ化するべき工程:")
    print("理由:")
    if bottleneck == "none":
        print("  この対象期間では FAIL が 0 件。よって “現在版で失敗が残っている工程” は未検出。")
    elif bottleneck == "implementation":
        print("  fail_stage最多がimplementation。Implementation failure（特に空コード等）の孤立計測が最短。")
    elif bottleneck == "validation":
        print("  fail_stage最多がvalidation。Validation gate条件の孤立再確認が有効。")
    elif bottleneck == "judge":
        print("  fail_stage最多がjudge。Judge採用（usable→adopt）の孤立点検が有効。")
    elif bottleneck == "research":
        print("  fail_stage最多がresearch。多経路探索/再調査の孤立再測定が有効。")
    elif bottleneck == "proposal":
        print("  fail_stage最多がproposal。Proposal生成/補完の孤立点検が有効。")
    elif bottleneck == "repair":
        print("  fail_stage最多がrepair。Repairの孤立点検が有効。")
    else:
        print("  fail_stageがother。other内訳を分解して次工程を確定する。")


if __name__ == "__main__":
    main()
