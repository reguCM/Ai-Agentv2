"""Phase O — continuous development session (O-1 … O-8).

Uses existing TDA structure only. Small Experimental adapters fill
ResearchRecord → Spec → Code → Test. Does not change Production or
standard_workflow facet_discovery default.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.experimental.development_assistance.facet_discovery import _DECISION_KEYS
from ai_tool.experimental.development_assistance.implementation_handoff import (
    evaluate_tool_change,
    implement_from_spec,
    is_change_eval_intent,
    is_implementation_intent,
    list_judgment_needs,
    run_tool_tests,
)
from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import (
    record_a,
    typed_record,
)
from ai_tool.experimental.development_assistance.python_version_delta import parse_python_version_delta
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.session_research_handoff import recover_spec_if_missing
from ai_tool.experimental.development_assistance.spec_to_experimental_tool import DEFAULT_DEST
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f

STEPS: list[dict[str, Any]] = [
    {
        "id": "O-1",
        "requirement": "ある技術Aについて、利用できるAPIと基本的な使い方を調べたい。",
        "expected_required_families": ["api"],
        "forbidden_required": ["cuda", "docker", "license", "ursim", "python_version"],
        "notes": "first research; fixture ingest after empty store",
    },
    {
        "id": "O-2",
        "requirement": "その技術AをPython 3.12で使えるか調べて。",
        "expected_required_families": ["python_version"],
        "forbidden_required": ["cuda", "license", "docker", "ursim"],
        "keep": ["api"],
        "python": "3.12",
    },
    {
        "id": "O-3",
        "requirement": "Windows環境ならどう？",
        "expected_required_families": ["os"],
        "forbidden_required": ["docker", "ursim", "cuda"],
        "keep": ["python_version"],
        "os": "windows",
        "python": "3.12",
    },
    {
        "id": "O-4",
        "requirement": "Dockerを使う場合はどう？",
        "expected_required_families": ["docker"],
        "forbidden_required": ["ursim"],
        "keep": ["python_version", "os"],
        "distinguish_generic_docker": True,
        "python": "3.12",
        "os": "windows",
    },
    {
        "id": "O-5",
        "requirement": "では、これをToolとして作れそう？",
        "expected_required_families": ["environment"],
        "forbidden_required": ["ursim"],
        "no_discovery_verdict": True,
        "max_required": 12,
    },
    {
        "id": "O-6",
        "requirement": "では、そのToolを実際に作ってテストして。",
        "implementation": True,
        "forbidden_required": ["ursim"],
    },
    {
        "id": "O-7",
        "requirement": "Python 3.12ではなくPython 3.13の場合だけ確認し直して。",
        "expected_required_families": ["python_version"],
        "forbidden_required": ["ursim"],
        "keep": ["docker", "os"],
        "python_to": "3.13",
        "python_from": "3.12",
    },
    {
        "id": "O-8",
        "requirement": "Python 3.13へ変更した結果、作成したToolに何か変更が必要？",
        "change_eval": True,
        "forbidden_required": ["ursim"],
        "python": "3.13",
        "no_auto_code_change": True,
    },
]


def _family(fid: str) -> str:
    x = (fid or "").lower()
    if x in {"api", "api_availability", "availability"}:
        return "api"
    if x in {"python_version", "python"}:
        return "python_version"
    if x in {"os", "windows"}:
        return "os"
    if x in {"environment"}:
        return "environment"
    return x


def _ids(cov: dict[str, Any], key: str) -> list[str]:
    return list(cov.get(key) or [])


def _stage_map(result) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for s in result.stages:
        rec = s if isinstance(s, dict) else s.to_dict()
        out[rec.get("stage") or ""] = rec
    return out


def _decision_leak(blob: Any) -> list[str]:
    found: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _DECISION_KEYS and k not in {"reject", "decision"}:
                    found.append(str(k))
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(blob)
    return list(dict.fromkeys(found))


def _update_session(session: dict[str, Any], result, spec: dict[str, Any] | None) -> None:
    slots = (result.coverage or {}).get("slots") or {}
    if slots.get("python"):
        session["last_python"] = slots["python"]
    if slots.get("os"):
        session["last_os"] = slots["os"]
        session["last_environment"] = slots["os"]
    if slots.get("cuda"):
        session["last_cuda"] = slots["cuda"]
    cov = result.coverage or {}
    if cov.get("target_research_id"):
        session["last_research_id"] = cov["target_research_id"]
    session["last_coverage"] = cov
    if spec:
        session["last_spec"] = spec
    acc_r = set(session.get("accumulated_required") or [])
    acc_c = set(session.get("accumulated_candidate") or [])
    acc_u = set(session.get("accumulated_unknown") or [])
    acc_r.update(_ids(cov, "required"))
    acc_c.update(_ids(cov, "candidates"))
    acc_u.update(_ids(cov, "unknown"))
    session["accumulated_required"] = sorted(acc_r)
    session["accumulated_candidate"] = sorted(acc_c)
    session["accumulated_unknown"] = sorted(acc_u)


def _ingest_fixture(store: ResearchStore, session: dict[str, Any]) -> dict[str, Any]:
    payload = record_a(python="Python 3.12", extra_python_versions=("3.12",))
    payload["unknowns"] = list(payload.get("unknowns") or []) + [
        "Docker runtime not recorded on A",
        "Python 3.13: no official information",
    ]
    rec = typed_record(payload)
    store.add(rec)
    session["last_research_id"] = rec.research_id
    session["research_ingest"] = "fixture_RR-A"
    return {
        "label": "RECORD",
        "research_id": rec.research_id,
        "live_web": False,
        "reason": "tda=None; offline fixture stands in for completed research of technology A",
    }


def _snapshot(step: dict[str, Any], result, extra: dict[str, Any]) -> dict[str, Any]:
    cov = result.coverage or {}
    stages = _stage_map(result)
    disc = stages.get("Facet Discovery") or {}
    route = stages.get("Relevant Facet Routing") or {}
    required = _ids(cov, "required")
    candidates = _ids(cov, "candidates")
    unknown = _ids(cov, "unknown")
    forbidden = [f for f in (step.get("forbidden_required") or []) if f in required]
    exp = list(step.get("expected_required_families") or [])
    fam = {_family(x) for x in required}
    recall = (len(set(exp) & fam) / len(exp)) if exp else None
    discovery_blob = {
        "decision": result.discovery_decision,
        "coverage_keys": list(cov.keys()),
        "stage": disc,
    }
    leak = _decision_leak(discovery_blob)
    return {
        "id": step["id"],
        "requirement": step["requirement"],
        "goal": result.goals,
        "gate": result.gate,
        "discovery": {
            "policy": result.discovery_decision,
            "invoked": bool((result.discovery_decision or {}).get("invoked")),
            "skipped": bool(disc.get("skipped")),
            "stop_reason": result.stop_reason,
        },
        "required_facet": required,
        "candidate_facet": candidates,
        "unknown": unknown,
        "unresolved": list(cov.get("unresolved") or []),
        "keep_facets": list(cov.get("keep_facets") or []),
        "changed_facets": list(cov.get("changed_facets") or []),
        "routing": {
            "facet_ids": list(result.relevant_slice.get("facet_ids") or []),
            "skipped": bool(route.get("skipped")),
            "outcome": route.get("outcome"),
        },
        "reuse": result.reuse_assessment,
        "web_searches": result.web_searches,
        "searches_estimate": cov.get("searches_estimate"),
        "decision_support_input": {
            "coverage": (result.decision_support or {}).get("coverage"),
            "hints": (result.decision_support or {}).get("comparison_hints"),
            "has_feasible_key": "feasible" in (result.decision_support or {}),
        },
        "spec_draft": extra.get("spec"),
        "implementation_request": extra.get("implementation_request"),
        "implementation_result": extra.get("implementation_result"),
        "test_result": extra.get("test_result"),
        "handoff": extra.get("handoff"),
        "adapter": extra.get("adapter"),
        "python_delta": extra.get("python_delta"),
        "judgment_needs": extra.get("judgment_needs"),
        "change_eval": extra.get("change_eval"),
        "research_record_ids": extra.get("research_record_ids"),
        "ingest": extra.get("ingest"),
        "recall": recall,
        "forbidden_in_required": forbidden,
        "discovery_decision_leak": leak,
        "ursim_in_required": "ursim" in required,
        "ursim_in_routing": "ursim" in list(result.relevant_slice.get("facet_ids") or []),
        "slots": cov.get("slots") or {},
    }


def _lost_kept(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {s["id"]: s for s in snapshots}
    o2 = by_id.get("O-2") or {}
    o3 = by_id.get("O-3") or {}
    o4 = by_id.get("O-4") or {}
    o7 = by_id.get("O-7") or {}
    py_kept = []
    for sid in ("O-3", "O-4", "O-5", "O-6"):
        s = by_id.get(sid) or {}
        ids = set(s.get("required_facet") or []) | set(s.get("candidate_facet") or []) | set(s.get("keep_facets") or [])
        py_kept.append({"step": sid, "python_present": "python_version" in ids})
    os_kept = []
    for sid in ("O-4", "O-5", "O-6", "O-7"):
        s = by_id.get(sid) or {}
        ids = set(s.get("required_facet") or []) | set(s.get("candidate_facet") or []) | set(s.get("keep_facets") or [])
        os_kept.append({"step": sid, "os_present": "os" in ids})
    docker_in_o7_required = "docker" in (o7.get("required_facet") or [])
    return {
        "python_312_slot_o2": (o2.get("slots") or {}).get("python") == "3.12",
        "python_presence_after_o2": py_kept,
        "os_presence_after_o3": os_kept,
        "windows_slot_o3": (o3.get("slots") or {}).get("os") == "windows",
        "docker_required_o4": "docker" in (o4.get("required_facet") or []),
        "docker_not_invented_o3": "docker" not in (o3.get("required_facet") or []),
        "o7_did_not_rerequire_docker": not docker_in_o7_required,
    }


def _walls(snapshots: list[dict[str, Any]], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    walls: list[dict[str, Any]] = []
    by_id = {s["id"]: s for s in snapshots}
    o1 = by_id.get("O-1") or {}
    o6 = by_id.get("O-6") or {}
    o7 = by_id.get("O-7") or {}
    workflow_spec_o1 = bool(o1.get("spec_draft")) and not (
        ((o1.get("adapter") or {}).get("session_handoff") or {}).get("recovered")
    )
    walls.append(
        {
            "id": "A",
            "at": "O-5",
            "text": "Discovery は判定せず、判断に必要な情報の列挙は Experimental Adapter が行う。",
            "kind": "既存構造の不足",
            "bridged": True,
        }
    )
    walls.append(
        {
            "id": "B",
            "at": "O-1+",
            "text": "空 store / 「その技術A」では Workflow 単体で Tool Spec に届かない。session ResearchRecord から回復した。",
            "kind": "既存構造の不足",
            "bridged": True,
            "workflow_spec_without_adapter": workflow_spec_o1,
        }
    )
    walls.append(
        {
            "id": "C",
            "at": "O-6",
            "text": "Tool Spec の既定は「user implements manually」。Code 生成は Experimental Adapter。",
            "kind": "既存構造の不足",
            "bridged": bool((o6.get("implementation_result") or {}).get("code_generated")),
        }
    )
    walls.append(
        {
            "id": "D",
            "at": "O-6",
            "text": "Test 結果は Workflow には戻らない。session.last_test_result へ Adapter が記録する。",
            "kind": "既存構造の不足",
            "bridged": bool((o6.get("test_result") or {}).get("ok")),
        }
    )
    delta = o7.get("python_delta") or {}
    as_is = (o7.get("slots") or {}).get("python")
    if delta.get("replacement_detected") and as_is == delta.get("replaced_from"):
        walls.append(
            {
                "id": "E",
                "at": "O-7",
                "text": "「3.12ではなく3.13」が first-match で 3.12 のまま扱われる。変更 Facet の再確認がずれる。",
                "kind": "既存構造の不足",
            }
        )
    if not metrics.get("context_retention", {}).get("python_312_slot_o2"):
        walls.append(
            {
                "id": "F",
                "at": "O-2",
                "text": "Python 3.12 が slot に入らなかった。",
                "kind": "既存構造の不足",
            }
        )
    py_after = metrics.get("context_retention", {}).get("python_presence_after_o2") or []
    if py_after and not all(p.get("python_present") for p in py_after):
        walls.append(
            {
                "id": "F",
                "at": "O-3+",
                "text": "session には last_python を残せるが、Coverage の Facet 一覧からは Python / OS が消える（follow 語が無い要求）。",
                "kind": "既存構造の不足",
            }
        )
    leaked = [s["id"] for s in snapshots if s.get("discovery_decision_leak")]
    if leaked:
        walls.append(
            {
                "id": "H",
                "at": ",".join(leaked),
                "text": "Discovery 出力に feasible/safe/correct 系キーが混入した。",
                "kind": "既存構造の不足",
            }
        )
    guessed = [s["id"] for s in snapshots if s.get("ursim_in_required") or s.get("ursim_in_routing")]
    if guessed:
        walls.append(
            {
                "id": "G",
                "at": ",".join(guessed),
                "text": "Generic Docker / 技術A から URSim を推測した。",
                "kind": "既存構造の不足",
            }
        )
    return walls


def run_phase_o_continuous() -> dict[str, Any]:
    store = ResearchStore()
    session: dict[str, Any] = {}
    snapshots: list[dict[str, Any]] = []
    client_path = DEFAULT_DEST / "client.py"
    hash_before_o8 = ""

    for step in STEPS:
        req = step["requirement"]
        result = run_standard_workflow(
            req,
            store=store,
            session=session,
            llm_enabled=False,
            facet_discovery="conditional",
            coverage_overlay=True,
            facet_routing="relevant",
        )
        extra: dict[str, Any] = {
            "research_record_ids": [r.research_id for r in store.records],
        }

        if step["id"] == "O-1" and not store.records:
            extra["ingest"] = _ingest_fixture(store, session)
            extra["research_record_ids"] = [r.research_id for r in store.records]

        recovered = recover_spec_if_missing(
            req,
            spec=result.spec_draft,
            candidates=list(result.candidates or []),
            store=store,
            session=session,
        )
        spec = recovered.get("spec")
        extra["spec"] = spec
        extra["adapter"] = {
            "session_handoff": recovered,
            "label": recovered.get("label") or "REUSE",
        }
        _update_session(session, result, spec if isinstance(spec, dict) else None)

        if step.get("no_discovery_verdict") or "作れそう" in req:
            extra["judgment_needs"] = list_judgment_needs(req, result.coverage, spec if isinstance(spec, dict) else None)

        if is_implementation_intent(req):
            extra["implementation_request"] = True
            if isinstance(spec, dict):
                written = implement_from_spec(spec)
                tests = run_tool_tests()
                extra["implementation_result"] = written
                extra["test_result"] = tests
                extra["handoff"] = {
                    "research_to_spec": bool(spec),
                    "spec_to_code": bool(written.get("code_generated")),
                    "code_to_test": bool(tests.get("ok")),
                    "fields": written.get("handoff_fields"),
                }
                session["last_test_result"] = tests
                session["tool_path"] = written.get("path")
                session["tool_runtime"] = written.get("runtime_python")
                session["tool_hash"] = written.get("sha256_16")
            else:
                extra["implementation_result"] = {"code_generated": False, "reason": "no spec"}
                extra["handoff"] = {"research_to_spec": False, "spec_to_code": False}

        if step["id"] == "O-7":
            extra["python_delta"] = parse_python_version_delta(req).to_dict()

        if step["id"] == "O-8" or is_change_eval_intent(req):
            hash_before_o8 = str(session.get("tool_hash") or "")
            hash_after = hash_before_o8
            if client_path.exists():
                hash_after = hashlib.sha256(
                    client_path.read_text(encoding="utf-8").encode("utf-8")
                ).hexdigest()[:16]
            eval_ = evaluate_tool_change(
                req,
                spec=session.get("last_spec") if isinstance(session.get("last_spec"), dict) else None,
                session=session,
                tool_hash_before=hash_before_o8,
                tool_hash_after=hash_after,
            )
            extra["change_eval"] = eval_
            extra["test_feedback_present"] = session.get("last_test_result")
            extra["code_auto_modified"] = bool(eval_.get("auto_modified"))

        extra["handoff_to_next"] = {
            "last_python": session.get("last_python"),
            "last_os": session.get("last_os"),
            "last_research_id": session.get("last_research_id"),
            "has_spec": bool(session.get("last_spec")),
            "has_test": bool(session.get("last_test_result")),
        }
        snapshots.append(_snapshot(step, result, extra))

    retention = _lost_kept(snapshots)
    searches = [int(s.get("web_searches") or 0) for s in snapshots]
    follow = snapshots[1:]
    reuse_hits = 0
    for s in follow:
        mode = (s.get("reuse") or {}).get("mode")
        if (s.get("web_searches") or 0) == 0 and mode in {"full_reuse", "partial_reuse"}:
            reuse_hits += 1
        elif (s.get("web_searches") or 0) == 0 and s["id"] in {"O-6"}:
            reuse_hits += 1
    recalls = [s["recall"] for s in snapshots if s.get("recall") is not None]
    false_disc = sum(1 for s in snapshots if s.get("forbidden_in_required") or s.get("ursim_in_required"))
    unknown_kept = any("docker" in (s.get("unknown") or []) for s in snapshots if s["id"] in {"O-1", "O-2", "O-3"})
    o7 = next(s for s in snapshots if s["id"] == "O-7")
    o8 = next(s for s in snapshots if s["id"] == "O-8")
    o6 = next(s for s in snapshots if s["id"] == "O-6")
    delta = o7.get("python_delta") or {}
    version_isolation_as_is = (o7.get("slots") or {}).get("python") == "3.13"
    version_isolation_adapter = delta.get("selected") == "3.13" and delta.get("replacement_detected")
    impl_ok = bool((o6.get("handoff") or {}).get("spec_to_code"))
    test_ok = bool((o6.get("test_result") or {}).get("ok"))
    test_feedback = bool((o8.get("test_feedback_present") or o8.get("change_eval")))
    phase_f = run_phase_f(llm_enabled=False)

    metrics = {
        "required_recall_mean": (sum(recalls) / len(recalls)) if recalls else None,
        "required_recall_by_step": {s["id"]: s.get("recall") for s in snapshots},
        "irrelevant_suppression": 1.0 if false_disc == 0 else max(0.0, 1.0 - false_disc / len(snapshots)),
        "false_discovery_steps": false_disc,
        "reuse_efficiency": (reuse_hits / len(follow)) if follow else 0.0,
        "search_total": sum(searches),
        "search_by_step": {s["id"]: s.get("web_searches") for s in snapshots},
        "search_reduction_vs_naive_2_per_step": 1.0 - (sum(searches) / (2 * len(snapshots))),
        "context_retention": retention,
        "version_isolation_as_is": version_isolation_as_is,
        "version_isolation_adapter": version_isolation_adapter,
        "unknown_preservation_docker_until_named": unknown_kept or retention["docker_not_invented_o3"],
        "implementation_handoff": impl_ok,
        "test_ok": test_ok,
        "test_feedback": test_feedback,
        "o8_auto_modified": bool((o8.get("change_eval") or {}).get("auto_modified")),
        "o8_change_needed": (o8.get("change_eval") or {}).get("change_needed"),
    }
    walls = _walls(snapshots, metrics)

    # O-5 needs: pull from last stored session via re-compute
    o5_result_needs = list_judgment_needs(
        STEPS[4]["requirement"],
        next(s for s in snapshots if s["id"] == "O-5").get("decision_support_input", {}).get("coverage") or {},
        next(s for s in snapshots if s["id"] == "O-5").get("spec_draft"),
    )

    adapter_needed = True
    judgment = "PARTIAL_PASS"
    if not impl_ok or not test_ok:
        judgment = "BLOCKED"
    if any(w["id"] == "H" for w in walls):
        judgment = "BLOCKED"

    next_should = [
        "会話ポインタ「その技術A」を session.last_research_id へ bind する小さな Adapter（Core ではない）",
        "「AではなくB」の Version 置換を first-match より優先する小さな Adapter",
        "Test 結果を session に戻す手番（Workflow 既定は変えない）",
    ]
    next_should_not = [
        "Reasoning Core / Graph / RAG / Vector DB / Knowledge Base",
        "Discovery に feasible / safe / correct / build を載せる",
        "Production の Tool 化や Registry 接続",
        "Generic Docker から URSim を推測する規則",
        "Python 3.12 の証拠を 3.13 に流用する規則",
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "phase_f_decision": phase_f.get("decision"),
        "phase_f_c3": (phase_f.get("core_discovery") or {}).get("c3_implemented"),
        "labels": {
            "session_handoff": "EXPERIMENTAL",
            "spec_to_code": "EXPERIMENTAL",
            "fixture_ingest": "RECORD",
            "o8_code_edit": "REJECT",
            "new_core": "REJECT",
        },
        "steps": snapshots,
        "metrics": metrics,
        "walls": walls,
        "o5_judgment_needs": o5_result_needs,
        "o5_required_count": len(next(s for s in snapshots if s["id"] == "O-5").get("required_facet") or []),
        "judgment": judgment,
        "adapter_needed": adapter_needed,
        "what_passed": {
            "o1_goal_gate_discovery": bool((snapshots[0].get("goal") or {}).get("level_0") or snapshots[0].get("gate")),
            "o1_research_record": bool(snapshots[0].get("research_record_ids")),
            "o2_python_required": snapshots[1].get("recall"),
            "o4_generic_docker_not_ursim": not snapshots[3].get("ursim_in_required") and not snapshots[3].get("ursim_in_routing"),
            "o5_no_feasible": not (snapshots[4].get("decision_support_input") or {}).get("has_feasible_key"),
            "o6_code": impl_ok,
            "o6_test": test_ok,
            "o8_no_auto_edit": not metrics["o8_auto_modified"],
        },
        "next_should_build": next_should,
        "next_should_not_build": next_should_not,
        "failure_split": {
            "既存構造の不足": [w for w in walls if w.get("kind") == "既存構造の不足"],
            "実装環境の不足": [w for w in walls if w.get("kind") == "実装環境の不足"],
            "Research不足": [
                "O-1 の ResearchRecord は live Web ではなく fixture RECORD。tda を渡していない。"
            ],
            "仕様不足": [
                "Tool Spec の provenance は execution-verified ではない。実 LibA の API は未検証。"
            ],
        },
        "core_creation_gate": {
            "Reasoning": "REJECT",
            "Graph": "REJECT",
            "RAG": "REJECT",
            "KnowledgeBase": "REJECT",
        },
    }


def facet_trace(result: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = result or run_phase_o_continuous()
    rows = []
    for s in result["steps"]:
        rows.append(
            {
                "step": s["id"],
                "required": s.get("required_facet"),
                "candidate": s.get("candidate_facet"),
                "unknown": s.get("unknown"),
                "keep": s.get("keep_facets"),
                "python_slot": (s.get("slots") or {}).get("python"),
                "os_slot": (s.get("slots") or {}).get("os"),
                "searches": s.get("web_searches"),
                "reuse": (s.get("reuse") or {}).get("mode"),
            }
        )
    return rows
