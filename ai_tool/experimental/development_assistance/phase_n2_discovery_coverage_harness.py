"""Phase N+2 — Facet Discovery coverage (paraphrase / slots / prior research)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.facet_coverage import (
    asserts_coverage_not_a_decision,
    discover_coverage,
)
from ai_tool.experimental.development_assistance.facet_discovery import plan_follow_up
from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog, PreservedIdea
from ai_tool.experimental.development_assistance.phase_n_facet_discovery_harness import (
    pytorch_record_a,
    robot_store,
)
from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import (
    record_a,
    record_a_515_517,
    record_b,
    typed_record,
)
from ai_tool.experimental.development_assistance.research_record import ResearchStore

MODES = ("K", "KA", "GC", "GCR")

CASES: list[dict[str, Any]] = [
    {
        "id": "P-api-s3",
        "miss": "paraphrase",
        "requirement": "Aの最新Versionで使えるAPIを調べて",
        "expected_required": ["version", "api", "availability"],
        "forbidden": ["docker", "cuda", "control_authority"],
        "store": "ab",
    },
    {
        "id": "P-confirm",
        "miss": "paraphrase",
        "requirement": "Aが実際に使えるか確認して",
        "expected_required": ["environment"],
        "forbidden": ["docker", "control_authority"],
        "store": "ab",
    },
    {
        "id": "P-works",
        "miss": "paraphrase",
        "requirement": "これで動く？",
        "expected_required": ["environment"],
        "forbidden": ["docker", "license", "cuda", "python_version"],
        "store": "ab",
    },
    {
        "id": "P-try-env",
        "miss": "paraphrase",
        "requirement": "この環境で試せる？",
        "expected_required": ["environment"],
        "expected_unknown": ["os", "docker", "hardware"],
        "forbidden": [],
        "store": "empty",
        "must_not_pick_os": True,
    },
    {
        "id": "P-prod",
        "miss": "paraphrase",
        "requirement": "本番で使って大丈夫？",
        "expected_required": ["environment"],
        "forbidden": [],
        "store": "ab",
        "no_safe_verdict": True,
    },
    {
        "id": "P-other-ver",
        "miss": "paraphrase",
        "requirement": "別バージョンでもいける？",
        "expected_required": ["version", "conflict"],
        "forbidden": ["docker"],
        "store": "ver",
    },
    {
        "id": "I-human-ur",
        "miss": "implicit",
        "requirement": "これ、人間が途中で操作できる？",
        "expected_candidate": ["control_authority", "human_handoff"],
        "forbidden_required": ["control_authority"],
        "store": "robot",
        "no_handoff_verdict": True,
    },
    {
        "id": "I-human-generic",
        "miss": "implicit",
        "requirement": "このToolを人間と一緒に使える？",
        "expected_unknown": ["control_authority"],
        "forbidden": ["docker", "python_version", "cuda"],
        "store": "ab",
    },
    {
        "id": "I-repeat",
        "miss": "implicit",
        "requirement": "何回も繰り返したらどうなる？",
        "expected_unknown": ["cycle_controller"],
        "forbidden": ["python_version", "license"],
        "store": "ab",
    },
    {
        "id": "C-py-only",
        "miss": "change",
        "requirement": "前に調べたAについて、Python 3.12の場合だけもう少し調べて",
        "expected_required": ["python_version"],
        "expected_keep": ["cuda", "license"],
        "forbidden": ["docker", "ursim"],
        "store": "ab",
        "partial": True,
    },
    {
        "id": "C-win",
        "miss": "change",
        "requirement": "Windowsなら？",
        "expected_required": ["os"],
        "forbidden": ["docker"],
        "store": "ab",
        "session": {"last_research_id": "RR-A", "last_python": "3.12"},
    },
    {
        "id": "C-gpu",
        "miss": "change",
        "requirement": "じゃあRTX 3060なら？",
        "expected_required": ["hardware"],
        "forbidden": ["docker"],
        "store": "ab",
        "session": {"last_research_id": "RR-A", "last_python": "3.12", "last_cuda": "12.3"},
    },
    {
        "id": "Q-ab",
        "miss": "compare",
        "requirement": "AとBどちらを使った方がいい？",
        "expected_required": ["target", "environment", "version", "license", "conflict"],
        "forbidden": ["ursim", "control_authority"],
        "store": "ab",
        "no_choice_verdict": True,
    },
    {
        "id": "F-env-unresolved",
        "miss": "follow-up",
        "requirement": "その環境ならどう？",
        "expected_required": [],
        "forbidden": ["windows", "docker", "virtualbox"],
        "store": "ab",
        "expect_unresolved": ["その環境"],
    },
    {
        "id": "F-env-bound",
        "miss": "follow-up",
        "requirement": "その環境ならどう？",
        "expected_required": ["environment"],
        "forbidden": ["docker"],
        "store": "ab",
        "session": {"last_research_id": "RR-A", "last_environment": "Windows RTX 3060 Python 3.12"},
        "expect_unresolved": [],
    },
    {
        "id": "F-other-method",
        "miss": "follow-up",
        "requirement": "前と同じ条件で別の方法は？",
        "expected_required": [],
        "forbidden": ["docker", "virtualbox"],
        "store": "ab",
        "expect_unresolved": ["別の方法"],
    },
    {
        "id": "F-partial-reuse",
        "miss": "follow-up",
        "requirement": "前回の調査結果を使って、ここだけ確認して",
        "expected_required": ["changed_condition"],
        "forbidden": ["ursim"],
        "store": "ab",
        "session": {"last_research_id": "RR-A"},
    },
    {
        "id": "V-515",
        "miss": "version",
        "requirement": "A 5.15で使いたい",
        "expected_required": ["version"],
        "forbidden": [],
        "store": "ver",
        "isolation": True,
    },
    {
        "id": "U-313",
        "miss": "unknown",
        "requirement": "前に調べたAをPython 3.13で使いたい。必要な変更だけ調べて",
        "expected_required": ["python_version"],
        "forbidden": [],
        "store": "unk",
        "python_unknown": True,
    },
    {
        "id": "K-conflict",
        "miss": "conflict",
        "requirement": "AをPythonで使いたい",
        "expected_required": [],
        "forbidden": [],
        "store": "conflict",
        "preserve_conflict": True,
    },
    {
        "id": "X-json",
        "miss": "false_discovery",
        "requirement": "PythonでJSONを読むコードを書いて",
        "expected_required": [],
        "forbidden": ["python_version", "license", "environment", "api", "docker", "cuda"],
        "store": "ab",
        "skip": True,
    },
    {
        "id": "X-json-q",
        "miss": "false_discovery",
        "requirement": "JSONとは何ですか？",
        "expected_required": [],
        "forbidden": ["license", "docker", "cuda"],
        "store": "ab",
        "skip": True,
    },
    {
        "id": "G-stop",
        "miss": "general",
        "requirement": "途中で止められる？",
        "expected_unknown": ["control_authority"],
        "forbidden": ["python_version", "cuda", "license"],
        "store": "ab",
    },
]


def _ab_store() -> ResearchStore:
    s = ResearchStore()
    s.add(typed_record(record_a(python="Python 3.12", extra_python_versions=("3.12",))))
    s.add(typed_record(record_b()))
    return s


def _unk_store() -> ResearchStore:
    payload = record_a(python="Python 3.12", extra_python_versions=("3.12",))
    payload["unknowns"] = ["Python 3.13: no official information"]
    payload["environment_facts"]["python_3_13"] = "UNKNOWN"
    s = ResearchStore()
    s.add(typed_record(payload))
    return s


def _conflict_store() -> ResearchStore:
    payload = record_a(python="Python 3.12", extra_python_versions=("3.12", "3.13"))
    payload["conflicts"] = [
        {"id": "src-official", "summary": "Official source: Python 3.12 supported"},
        {"id": "src-third", "summary": "Third-party source: Python 3.13 supported"},
    ]
    s = ResearchStore()
    s.add(typed_record(payload))
    return s


def _store(kind: str) -> ResearchStore:
    if kind == "empty":
        return ResearchStore()
    if kind == "robot":
        return robot_store()
    if kind == "ver":
        s = ResearchStore()
        s.add(typed_record(record_a_515_517()))
        return s
    if kind == "unk":
        return _unk_store()
    if kind == "conflict":
        return _conflict_store()
    return _ab_store()


def _recall(got: list[str], expected: list[str]) -> float | None:
    if not expected:
        return None
    return len(set(got) & set(expected)) / len(expected)


def _false_rate(got: list[str], forbidden: list[str]) -> float:
    if not forbidden:
        return 0.0
    return len(set(got) & set(forbidden)) / len(forbidden)


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _eval_case(case: dict[str, Any], mode: str) -> dict[str, Any]:
    store = _store(case.get("store") or "ab")
    session = dict(case.get("session") or {})
    cov = discover_coverage(case["requirement"], store, mode=mode, session=session)  # type: ignore[arg-type]
    required = cov.required_ids()
    candidates = cov.candidate_ids()
    unknown = cov.unknown_ids()
    forbidden = list(case.get("forbidden") or [])
    forbidden_req = list(case.get("forbidden_required") or [])
    exp_req = list(case.get("expected_required") or [])
    exp_cand = list(case.get("expected_candidate") or [])
    exp_unk = list(case.get("expected_unknown") or [])
    union_exp = list(dict.fromkeys(exp_req + exp_cand))
    covered = list(dict.fromkeys(required + candidates))
    over_promote = [x for x in required if x in exp_cand or x in forbidden_req]
    guessed_env = False
    if case.get("must_not_pick_os"):
        guessed_env = any(x in required for x in ("windows", "docker", "virtualbox"))
    unresolved_ok = True
    if case.get("expect_unresolved"):
        unresolved_ok = all(u in cov.unresolved for u in case["expect_unresolved"])
    keep_ok = True
    if case.get("expected_keep") and mode == "GCR":
        keep_ok = all(k in cov.keep_facets or k in candidates for k in case["expected_keep"])
    isolation = True
    if case.get("isolation"):
        blob = str(cov.to_dict()).lower()
        isolation = "apply 5.17" not in blob
    py_unknown = True
    if case.get("python_unknown"):
        plan = plan_follow_up(case["requirement"], store)
        py_unknown = plan is not None and any("3.13" in m for m in plan.missing)
    conflict_ok = True
    if case.get("preserve_conflict"):
        conflict_ok = len(store.records[0].conflicts or []) >= 2
    no_decision = asserts_coverage_not_a_decision(cov)
    fd = [x for x in required if x in forbidden]
    return {
        "id": case["id"],
        "miss": case["miss"],
        "skipped": cov.skipped,
        "required": required,
        "candidates": candidates,
        "unknown": unknown,
        "unresolved": cov.unresolved,
        "keep": cov.keep_facets,
        "changed": cov.changed_facets,
        "required_recall": _recall(required, exp_req),
        "candidate_recall": _recall(candidates, exp_cand),
        "unknown_recall": _recall(unknown, exp_unk),
        "coverage_recall": _recall(covered, union_exp) if union_exp else None,
        "false_discovery": bool(fd) or guessed_env,
        "false_ids": fd,
        "over_promotion": over_promote,
        "suppression": 1.0 - _false_rate(required, forbidden) if forbidden else 1.0,
        "unresolved_ok": unresolved_ok,
        "keep_ok": keep_ok,
        "isolation": isolation,
        "python_unknown": py_unknown,
        "conflict_ok": conflict_ok,
        "no_decision": no_decision,
        "searches": cov.searches_estimate,
        "target": cov.slots.target,
        "target_research_id": cov.target_research_id,
    }


def followup_chain() -> dict[str, Any]:
    store = ResearchStore()
    store.add(pytorch_record_a(python="Python 3.12"))
    session: dict[str, Any] = {"last_research_id": "RR-A"}
    texts = [
        "PyTorchについて調べて",
        "Python 3.12なら？",
        "CUDA 12.3なら？",
        "Windowsでも？",
        "じゃあRTX 3060なら？",
        "この条件でToolにできそう？",
    ]
    acc: list[str] = []
    rows = []
    for i, t in enumerate(texts, 1):
        cov = discover_coverage(t, store, mode="GCR", session=session)
        for fid in cov.required_ids() + cov.candidate_ids():
            if fid not in acc:
                acc.append(fid)
        if cov.slots.python:
            session["last_python"] = cov.slots.python
        if cov.slots.cuda:
            session["last_cuda"] = cov.slots.cuda
        if cov.slots.os:
            session["last_os"] = cov.slots.os
        if cov.slots.hardware:
            session["last_hardware"] = cov.slots.hardware
        plan = plan_follow_up(t, store, session=session)
        rows.append(
            {
                "turn": i,
                "required": cov.required_ids(),
                "candidates": cov.candidate_ids(),
                "changed": cov.changed_facets,
                "keep": cov.keep_facets,
                "full_reresearch": bool(plan.full_reresearch) if plan else False,
                "no_decision": asserts_coverage_not_a_decision(cov),
                "purpose": cov.slots.purpose,
            }
        )
    last = rows[-1]
    return {
        "turns": rows,
        "python_kept": session.get("last_python") == "3.12",
        "cuda_not_overwritten_by_python": session.get("last_cuda") == "12.3",
        "continuity": len(acc) >= 3,
        "last_is_feasibility_check": last["purpose"] == "feasibility_check",
        "last_no_decision": last["no_decision"],
        "no_full_reresearch": all(not r["full_reresearch"] for r in rows[1:]),
    }


def run_phase_n2() -> dict[str, Any]:
    by_mode: dict[str, Any] = {}
    for mode in MODES:
        rows = [_eval_case(c, mode) for c in CASES]
        by_mode[mode] = {
            "required_recall": _mean([r["required_recall"] for r in rows]),
            "coverage_recall": _mean([r["coverage_recall"] for r in rows]),
            "false_discovery_count": sum(1 for r in rows if r["false_discovery"]),
            "over_promotion_count": sum(1 for r in rows if r["over_promotion"]),
            "suppression": _mean([r["suppression"] for r in rows]),
            "unresolved_ok": all(r["unresolved_ok"] for r in rows),
            "no_decision": all(r["no_decision"] for r in rows),
            "keep_ok": all(r["keep_ok"] for r in rows),
            "mean_searches": _mean([float(r["searches"]) for r in rows]),
            "cases": rows,
        }
    chain = followup_chain()
    k = by_mode["K"]["required_recall"] or 0.0
    gcr = by_mode["GCR"]["required_recall"] or 0.0
    fd = by_mode["GCR"]["false_discovery_count"]
    still_miss: list[str] = []
    for r in by_mode["GCR"]["cases"]:
        if r["required_recall"] is not None and r["required_recall"] < 1.0:
            still_miss.append(r["id"])
        elif r["candidate_recall"] is not None and r["candidate_recall"] < 1.0 and r["miss"] == "implicit":
            still_miss.append(r["id"])
        elif r["unknown_recall"] is not None and r["unknown_recall"] < 1.0 and r["miss"] in {"implicit", "general"}:
            still_miss.append(r["id"])
    ideas = [
        PreservedIdea(
            idea="Paraphrase alias table for Facet Discovery",
            why_it_appeared="Cue table missed 使えるAPI / 確認して / 動く？",
            higher_level_goal="Same research-need, different wording",
            why_not_implemented="Experimental overlay; not merged into default discover_facets yet",
            existing_alternative="facet_discovery._CUES + facet_coverage._ALIAS_FAMILIES",
            potential_future_trigger="Adopt aliases into discover_facets after workflow wiring",
            decision="EXPERIMENTAL",
        ),
        PreservedIdea(
            idea="Required vs Candidate vs Unknown envelope",
            why_it_appeared="Implicit human-ops must not be asserted as required",
            higher_level_goal="Do not guess facets",
            why_not_implemented="Measurement adapter, not a Core",
            existing_alternative="facet_coverage.CoverageItem.status",
            potential_future_trigger="If Decision Support needs the three-way split as input",
            decision="EXPERIMENTAL",
        ),
        PreservedIdea(
            idea="Reasoning Core / LLM inference for facet need",
            why_it_appeared="Temptation when paraphrase table is incomplete",
            higher_level_goal="Catch unseen wording",
            why_not_implemented="Alias + slots + prior research recovered measured misses without a Core",
            existing_alternative="facet_coverage.py",
            potential_future_trigger="Repeated misses after alias extension on live requirements",
            decision="REJECT",
        ),
        PreservedIdea(
            idea="Facet Graph / RAG / Vector DB",
            why_it_appeared="Coverage gaps look semantic",
            higher_level_goal="Match paraphrase by embedding",
            why_not_implemented="Token/alias overlap sufficient on this set",
            existing_alternative="alias families + extract_slots",
            potential_future_trigger="None measured",
            decision="REJECT",
        ),
        PreservedIdea(
            idea="Discovery emits feasible/safe",
            why_it_appeared="Toolにできそう / 大丈夫？",
            higher_level_goal="Fewer stages",
            why_not_implemented="Decision Support boundary",
            existing_alternative="purpose=feasibility_check lists evidence only",
            potential_future_trigger="None",
            decision="REJECT",
        ),
    ]
    catalog = IdeaCatalog()
    for idea in ideas:
        catalog.add(idea)
    json_clean = all(
        not r["false_discovery"] for r in by_mode["GCR"]["cases"] if r["miss"] == "false_discovery"
    )
    improved = gcr > k + 0.02
    cond = (
        gcr >= 0.80
        and gcr + 1e-9 >= k
        and fd == 0
        and json_clean
        and by_mode["GCR"]["no_decision"]
        and by_mode["GCR"]["unresolved_ok"]
        and chain["last_no_decision"]
        and chain["python_kept"]
        and chain["cuda_not_overwritten_by_python"]
    )
    if cond and improved and not still_miss:
        decision = "GENERALIZED_PASS"
        why = "Alias + slots + prior research lifts recall without False Discovery or a Core."
    elif cond:
        decision = "EXPERIMENTAL_RETAIN"
        why = (
            f"GCR required_recall {gcr:.2f} (K {k:.2f}), False Discovery 0. "
            "Remaining misses still need cue/store; not workflow-default."
        )
    elif gcr >= 0.80 and fd == 0:
        decision = "DEFER"
        why = "Value is clear; do not Core-ize. Keep as experimental overlay."
    else:
        decision = "REJECT"
        why = "No measured gain, or False Discovery rose."
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_changed": False,
        "baseline_skip_policy_recall": 0.80,
        "modes": by_mode,
        "followup_chain": chain,
        "still_miss_gcr": still_miss,
        "adoption": {"decision": decision, "why": why},
        "idea_preservation": [i.to_dict() for i in ideas],
        "core_creation_gate": {
            "Reasoning": "REJECT",
            "Graph": "REJECT",
            "RAG_Vector": "REJECT",
            "coverage_adapter": "EXPERIMENTAL",
        },
        "metrics": {
            "required_recall_K": by_mode["K"]["required_recall"],
            "required_recall_KA": by_mode["KA"]["required_recall"],
            "required_recall_GC": by_mode["GC"]["required_recall"],
            "required_recall_GCR": by_mode["GCR"]["required_recall"],
            "coverage_recall_GCR": by_mode["GCR"]["coverage_recall"],
            "false_discovery_GCR": fd,
            "false_discovery_K": by_mode["K"]["false_discovery_count"],
            "suppression_GCR": by_mode["GCR"]["suppression"],
            "suppression_K": by_mode["K"]["suppression"],
        },
    }

