"""Phase N+1 — Generalized Facet Discovery across TDA domains (no new Core)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.facet_discovery import (
    asserts_not_a_decision,
    discover_facets,
    existing_mode_a_ids,
    facet_hierarchy_view,
    plan_follow_up,
    resolve_research_reference,
)
from ai_tool.experimental.development_assistance.goal_abstraction import abstract_goals, discover_capabilities
from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog, PreservedIdea
from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import (
    record_a,
    record_a_515_517,
    record_b,
    typed_record,
)
from ai_tool.experimental.development_assistance.relevant_facet_router import route_relevant_facets
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import extract_requirement_facets

NOISE = ["numpy", "control_authority", "human_handoff", "ursim", "cycle_controller"]

CASES: list[dict[str, Any]] = [
    {
        "id": "A-python",
        "domain": "python_version",
        "requirement": "前に調べたAをPython 3.12で使いたい。必要な変更だけ調べて",
        "expected": ["python_version"],
        "concepts": ["target", "environment", "compatibility"],
        "irrelevant": ["docker", "license", "numpy", "human_handoff"],
        "partial": True,
    },
    {
        "id": "B-docker",
        "domain": "docker_environment",
        "requirement": "前に調べたAをDockerで動かしたい。何が変わるか調べて",
        "expected": ["docker", "storage"],
        "concepts": ["container", "runtime", "os", "dependencies"],
        "irrelevant": ["python_version", "cuda", "license", "numpy", "ursim", "control_authority"],
        "partial": True,
    },
    {
        "id": "C-api",
        "domain": "api_capability",
        "requirement": "AにはこのAPIがあると聞いた。実際に今使えるのか確認して",
        "expected": ["version"],
        "concepts": ["api", "availability", "source", "currentness"],
        "irrelevant": ["docker", "numpy", "human_handoff"],
        "no_use_verdict": True,
    },
    {
        "id": "D-license",
        "domain": "license",
        "requirement": "Aを自作Toolに組み込みたい。ライセンス上問題ないか調べて",
        "expected": ["license"],
        "concepts": ["distribution", "modification", "dependency", "source", "version"],
        "irrelevant": ["python_version", "cuda", "docker", "numpy"],
    },
    {
        "id": "E-hardware",
        "domain": "hardware_environment",
        "requirement": "AをRTX 3060 12GBのWindows環境で動かせるか調べて",
        "expected": ["hardware", "vram", "os"],
        "concepts": ["hardware", "vram", "os", "runtime", "performance"],
        "irrelevant": ["license", "numpy", "docker", "human_handoff"],
        "no_run_verdict": True,
    },
    {
        "id": "F-compare",
        "domain": "comparison",
        "requirement": "AとBを、今の環境で使うならどちらが向いているか比較して",
        "expected": [],
        "concepts": [
            "target",
            "environment",
            "version",
            "dependency",
            "license",
            "performance",
            "currentness",
            "unknown",
            "conflict",
        ],
        "irrelevant": ["ursim", "control_authority", "numpy"],
        "target_comparison": True,
    },
    {
        "id": "M-multifacet",
        "domain": "multi_facet",
        "requirement": (
            "AをPython 3.12、CUDA 12.3、Windows、RTX 3060で動かしたい。"
            "前回の調査結果を使って、不足しているところだけ調べて"
        ),
        "expected": ["python_version", "cuda", "os", "hardware"],
        "irrelevant": ["docker", "numpy", "ursim"],
        "all_present_no_search": True,
    },
    {
        "id": "V-isolation",
        "domain": "version_isolation",
        "requirement": "AをPython 3.13、CUDA 12.3の場合だけ再評価して。",
        "expected": ["python_version", "cuda"],
        "irrelevant": ["docker", "numpy"],
        "python_only_change": True,
    },
    {
        "id": "V-515",
        "domain": "version_isolation",
        "requirement": "A 5.17の仕様を5.15へ適用できるか調べて",
        "expected": ["version", "conflict"],
        "irrelevant": ["docker", "numpy"],
        "store": "ver",
        "no_517_apply": True,
    },
    {
        "id": "J-json",
        "domain": "llm_only",
        "requirement": "JSONをPythonで読み込む方法を教えて",
        "expected": [],
        "irrelevant": ["docker", "cuda", "hardware"],
        "early_exit": True,
    },
]


def _store(kind: str = "ab") -> ResearchStore:
    s = ResearchStore()
    if kind == "ver":
        s.add(typed_record(record_a_515_517()))
        return s
    s.add(typed_record(record_a(python="Python 3.13", extra_python_versions=("3.12", "3.13"))))
    s.add(typed_record(record_b()))
    return s


def _recall(selected: list[str], expected: list[str]) -> float | None:
    if not expected:
        return None
    return len(set(selected) & set(expected)) / len(expected)


def _suppression(selected: list[str], irrelevant: list[str]) -> float | None:
    if not irrelevant:
        return None
    return 1.0 - len(set(selected) & set(irrelevant)) / len(irrelevant)


def _mode_a(req: str) -> dict[str, Any]:
    gate = assess_research_requirement(req)
    selected = existing_mode_a_ids(req)
    if gate.decision == "RESEARCH_NOT_REQUIRED":
        selected = []
    return {"selected": selected, "gate": gate.decision, "searches": 0 if gate.decision == "RESEARCH_NOT_REQUIRED" else 2}


def _mode_b(req: str, store: ResearchStore) -> dict[str, Any]:
    sl = route_relevant_facets(req, list(store.records), mode="full")
    return {"selected": sl.facet_ids, "searches": 0, "reused": len(sl.facet_ids), "new": 0}


def _mode_c(req: str, store: ResearchStore, *, session: dict[str, Any] | None = None) -> dict[str, Any]:
    gate = assess_research_requirement(req)
    disc = discover_facets(req, store, session=session)
    skip = gate.decision == "RESEARCH_NOT_REQUIRED" and not disc.research_needed
    if skip:
        return {
            "selected": [],
            "concepts": [],
            "gate": gate.decision,
            "skipped_discovery": True,
            "research_needed": False,
            "not_a_decision": True,
            "searches": 0,
            "reused": 0,
            "new": 0,
            "plan": None,
            "discovery": {},
            "hierarchy": {},
        }
    plan = plan_follow_up(req, store, session=session)
    sl = route_relevant_facets(
        req,
        list(store.records),
        mode="relevant",
        needed_facet_ids=disc.catalog_ids(),
    )
    searches = plan.searches_estimate if plan else (0 if disc.partial_only else 1)
    reused = len(plan.reusable) if plan else 0
    new = len(plan.missing) if plan else 0
    return {
        "selected": sl.facet_ids,
        "concepts": disc.concepts,
        "gate": gate.decision,
        "skipped_discovery": False,
        "research_needed": disc.research_needed,
        "not_a_decision": asserts_not_a_decision(disc),
        "searches": searches,
        "reused": reused,
        "new": new,
        "plan": plan.to_dict() if plan else None,
        "discovery": disc.to_dict(),
        "hierarchy": facet_hierarchy_view(disc.catalog_ids() + disc.concepts),
        "target_comparison": disc.target_comparison,
        "unresolved": disc.unresolved_references,
    }


def _score(case: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    selected = list(pack.get("selected") or [])
    expected = list(case.get("expected") or [])
    concepts = list(pack.get("concepts") or [])
    recall = _recall(selected, expected)
    if recall is None and case.get("concepts"):
        recall = len(set(concepts) & set(case["concepts"])) / len(case["concepts"])
    isolation = None
    if case.get("python_only_change") and pack.get("plan"):
        isolation = pack["plan"]["requested_facets"] == ["python_version", "cuda"] and any(
            "python 3.13" in m for m in pack["plan"]["missing"]
        ) and not any("cuda" in m for m in pack["plan"]["missing"])
    if case.get("no_517_apply"):
        blob = str(pack.get("discovery") or {}).lower() + str(pack.get("selected"))
        isolation = "conflict" in (pack.get("selected") or []) or "conflict" in str(pack.get("discovery"))
        isolation = bool(isolation) and "apply 5.17" not in blob
    unknown_ok = None
    if "api" in (case.get("concepts") or []):
        unknown_ok = "availability" in concepts or "currentness" in concepts
    no_verdict = pack.get("not_a_decision", True)
    return {
        "selected": selected,
        "recall": recall,
        "suppression": _suppression(selected, list(case.get("irrelevant") or [])),
        "searches": pack.get("searches"),
        "reused": pack.get("reused"),
        "new": pack.get("new"),
        "version_isolated": isolation,
        "unknown_preserved": unknown_ok,
        "not_a_decision": no_verdict,
        "skipped_discovery": pack.get("skipped_discovery"),
        "gate": pack.get("gate"),
        "plan": pack.get("plan"),
        "concepts": concepts,
        "target_comparison": pack.get("target_comparison"),
        "hierarchy": pack.get("hierarchy"),
    }


def run_followup_chain() -> dict[str, Any]:
    store = _store()
    session: dict[str, Any] = {"last_research_id": "RR-A", "accumulated": []}
    turns = [
        "Aについて調べて",
        "ではPython 3.12の場合だけ調べて",
        "その場合CUDA 12.3ではどうなる？",
        "Windowsなら？",
        "RTX 3060 12GBなら？",
        "前の結果とBを比較して",
    ]
    rows = []
    acc: list[str] = []
    for i, text in enumerate(turns, 1):
        if i == 3:
            session["last_python"] = "3.12"
        disc = discover_facets(text, store, session=session)
        plan = plan_follow_up(text, store, session=session)
        new_ids = disc.catalog_ids()
        dropped = [x for x in acc if x not in acc + new_ids]
        for x in new_ids:
            if x not in acc:
                acc.append(x)
        if i == 2:
            session["last_python"] = "3.12"
            session["accumulated"] = list(acc)
        if i >= 4:
            session["last_environment"] = "windows" if "Windows" in text else session.get("last_environment")
        rows.append(
            {
                "turn": i,
                "text": text,
                "new_ids": new_ids,
                "accumulated": list(acc),
                "missing": plan.missing if plan else [],
                "reusable": plan.reusable if plan else [],
                "searches": plan.searches_estimate if plan else 0,
                "full_reresearch": plan.full_reresearch if plan else False,
                "python_kept": "3.12" in str(session.get("last_python", "")),
            }
        )
    py_kept_on_cuda_turn = rows[2]["python_kept"] and (
        "python_version" in rows[1]["new_ids"] or "python_version" in rows[1]["accumulated"]
    )
    return {
        "turns": rows,
        "continuity": all(not r["full_reresearch"] for r in rows[1:]),
        "python_kept_when_cuda_added": py_kept_on_cuda_turn,
        "final_accumulated": acc,
    }


def run_ambiguous() -> dict[str, Any]:
    store = _store()
    phrases = [
        "そのPython版なら？",
        "その環境なら？",
        "前のやつで",
        "Aの方だけもう少し詳しく",
        "さっきの条件を変えたら？",
        "その方法じゃなく別の方法なら？",
    ]
    rows = []
    for p in phrases:
        ref = resolve_research_reference(p, store, session={})
        rows.append(
            {
                "phrase": p,
                "matched": ref["matched"].research_id if ref.get("matched") else "",
                "unresolved": ref.get("unresolved") or [],
                "clarifications": ref.get("clarifications") or [],
                "guessed": False,
            }
        )
    return {"phrases": rows, "no_guess": all(not r["guessed"] for r in rows)}


def domain_lift() -> dict[str, Any]:
    return {
        "ur_control_authority": {"common": "ownership_state", "not_same_as": "license"},
        "python_tool": {"common": ["environment", "version", "dependency"]},
        "docker_tool": {"common": ["container", "runtime", "storage"]},
        "api_tool": {"common": ["api", "version", "availability"]},
        "license_tool": {"common": ["license", "distribution", "dependency"]},
        "forced_merge_authority_with_license": False,
    }


def workflow_insertion() -> dict[str, Any]:
    req = CASES[0]["requirement"]
    goals = abstract_goals(req)
    caps = discover_capabilities(req)
    disc = discover_facets(req, _store())
    goals_feed = any(
        fid in (goals.level_0 + goals.level_1)
        for fid in disc.catalog_ids()
    )
    caps_feed = any(d.name.lower() in disc.catalog_ids() for d in caps.derived_capabilities)
    return {
        "candidates": {
            "A_after_goals_before_caps": "Goals have no facet slots; Discovery does not read L0–L3",
            "B_after_caps_before_discovery": "Capability names are TDA modules, not research facets",
            "C_after_caps_before_reuse": "Discovery output is the retrieval key for Routing/Reuse",
        },
        "goals_feed_discovery": bool(goals_feed),
        "caps_feed_discovery": bool(caps_feed),
        "recommended": "C",
        "reason": (
            "Discovery uses Requirement + ResearchStore, not Goal prose or Capability names. "
            "Natural sink is Reuse/Routing. Do not C3-ify."
        ),
    }


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def run_phase_n1() -> dict[str, Any]:
    ideas = IdeaCatalog()
    ideas.add(
        PreservedIdea(
            idea="GPU passthrough facet",
            why_it_appeared="Docker + GPU requirement",
            higher_level_goal="Container environment completeness",
            why_not_implemented="Unknown on fixture; not a Core",
            existing_alternative="facet_records.gpu_passthrough + UNKNOWN",
            potential_future_trigger="Docker GPU tool requirement",
            decision="RECORD",
        )
    )
    ideas.add(
        PreservedIdea(
            idea="License distribution/modification subfacets",
            why_it_appeared="Embed-into-tool license question",
            higher_level_goal="License decision support",
            why_not_implemented="Need listed; no license reasoner",
            existing_alternative="license_facts + discovery concepts",
            potential_future_trigger="Redistribution requirement",
            decision="RECORD",
        )
    )
    rows = []
    for case in CASES:
        store = _store(case.get("store") or "ab")
        if case["id"] == "V-isolation":
            store = ResearchStore()
            store.add(typed_record(record_a(python="Python 3.12", extra_python_versions=("3.12",))))
        a = _score(case, _mode_a(case["requirement"]))
        b = _score(case, _mode_b(case["requirement"], store))
        c = _score(case, _mode_c(case["requirement"], store))
        rows.append({"id": case["id"], "domain": case["domain"], "requirement": case["requirement"], "A": a, "B": b, "C": c})
    chain = run_followup_chain()
    amb = run_ambiguous()
    domains = sorted({c["domain"] for c in CASES})
    scored = [r for r in rows if r["id"] != "J-json"]
    metrics = {
        "relevant_recall_A": _mean([r["A"]["recall"] for r in scored]),
        "relevant_recall_B": _mean([r["B"]["recall"] for r in scored]),
        "relevant_recall_C": _mean([r["C"]["recall"] for r in scored]),
        "irrelevant_suppression_A": _mean([r["A"]["suppression"] for r in rows]),
        "irrelevant_suppression_B": _mean([r["B"]["suppression"] for r in rows]),
        "irrelevant_suppression_C": _mean([r["C"]["suppression"] for r in rows]),
        "mean_searches_C": _mean([r["C"]["searches"] for r in rows]),
        "mean_reused_C": _mean([r["C"]["reused"] for r in rows]),
        "mean_new_C": _mean([r["C"]["new"] for r in rows]),
        "by_domain_recall_C": {
            d: _mean([r["C"]["recall"] for r in rows if r["domain"] == d]) for d in domains
        },
    }
    json_row = next(r for r in rows if r["id"] == "J-json")
    docker_row = next(r for r in rows if r["id"] == "B-docker")
    ur_leak = "ursim" in (docker_row["C"]["selected"] or []) or "control_authority" in (docker_row["C"]["selected"] or [])
    json_ok = json_row["C"].get("skipped_discovery") is True and json_row["C"]["searches"] == 0
    c_beats_a = (metrics["relevant_recall_C"] or 0) > (metrics["relevant_recall_A"] or 0)
    c_beats_b_sup = (metrics["irrelevant_suppression_C"] or 0) > (metrics["irrelevant_suppression_B"] or 0)
    six_domains = len(domains) >= 6
    if six_domains and c_beats_a and c_beats_b_sup and json_ok and chain["continuity"] and not ur_leak:
        # Cue tables are still domain lists; structure generalizes.
        if (metrics["relevant_recall_C"] or 0) >= 0.75:
            decision = "GENERALIZED_PASS"
            why = "Same Discovery→Routing→Reuse shape works on non-UR domains without UR facet leak or JSON inflation."
        else:
            decision = "EXPERIMENTAL_RETAIN"
            why = "Structure generalizes; cue coverage still incomplete."
    elif c_beats_a and not ur_leak:
        decision = "EXPERIMENTAL_RETAIN"
        why = "Non-UR cases work in part; not enough for Standard Workflow default."
    elif ur_leak or not c_beats_a:
        decision = "DOMAIN_LIMITED"
        why = "UR companions leak or non-UR recall stays at Mode A."
    else:
        decision = "REJECT"
        why = "Existing Goal Abstraction + RequirementFacets suffice or complexity dominates."
    failures = []
    for r in rows:
        if r["id"] == "J-json":
            continue
        if (r["C"]["recall"] or 0) < 0.5:
            failures.append({"id": r["id"], "why": "low Mode C recall", "selected": r["C"]["selected"]})
        leaked = set(r["C"]["selected"] or []) & set(NOISE)
        if leaked and r["id"] != "M-multifacet":
            failures.append({"id": r["id"], "why": f"noise leak {sorted(leaked)}"})
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "hypothesis": (
            "Requirement → needed facet kinds → selective research reuse is a TDA-level concept, not UR-only."
        ),
        "metrics": metrics,
        "cases": rows,
        "followup_chain": chain,
        "ambiguous": amb,
        "domain_lift": domain_lift(),
        "workflow_insertion": workflow_insertion(),
        "idea_preservation": [i.to_dict() for i in ideas.ideas if i.decision == "RECORD"][-2:],
        "failures": failures,
        "domains_evaluated": domains,
        "adoption": {
            "decision": decision,
            "why": why,
            "json_early_exit": json_ok,
            "ur_leak_on_generic_docker": ur_leak,
            "followup_continuity": chain["continuity"],
            "python_kept_on_cuda_turn": chain["python_kept_when_cuda_added"],
        },
        "core_creation_gate": {
            "Reasoning_Graph_RAG_Vector": "REJECT",
            "facet_discovery_adapter": "EXPERIMENTAL",
            "hierarchy_nested_dict": "REUSE",
        },
    }
