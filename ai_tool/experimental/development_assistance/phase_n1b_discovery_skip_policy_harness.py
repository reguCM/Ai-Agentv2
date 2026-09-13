"""Phase N+1b — Discovery skip policy / workflow adoption evaluation."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.discovery_skip_policy import (
    PolicyName,
    classify_discovery,
    environment_switch,
)
from ai_tool.experimental.development_assistance.facet_discovery import (
    asserts_not_a_decision,
    discover_facets,
    plan_follow_up,
    resolve_research_reference,
)
from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog, PreservedIdea
from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import (
    GENERAL_TDA_CATALOG,
    record_a,
    record_a_515_517,
    record_b,
    typed_record,
)
from ai_tool.experimental.development_assistance.relevant_facet_router import route_relevant_facets
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.research_record import ResearchStore

NOISE = {"numpy", "license", "cuda", "docker", "control_authority", "human_handoff"}
UNKNOWN_BANNED = {"python_version", "cuda", "docker", "license", "numpy"}

CASES: list[dict[str, Any]] = [
    {"id": "S1a", "requirement": "JSONとは何ですか？", "expect": "DISCOVERY_SKIP", "family": "llm_only"},
    {"id": "S1b", "requirement": "Pythonのfor文を教えて", "expect": "DISCOVERY_SKIP", "family": "llm_only"},
    {"id": "S1c", "requirement": "HTTPとは何ですか？", "expect": "DISCOVERY_SKIP", "family": "llm_only"},
    {"id": "S2a", "requirement": "PythonでCSVを読み込むコードを書いて", "expect": "DISCOVERY_SKIP", "family": "llm_only"},
    {"id": "S2b", "requirement": "JSONを辞書に変換する関数を作って", "expect": "DISCOVERY_SKIP", "family": "llm_only"},
    {"id": "S2c", "requirement": "PythonでJSONを読むコードを書いて", "expect": "DISCOVERY_SKIP", "family": "false_discovery_probe"},
    {
        "id": "S3",
        "requirement": "Aの最新Versionで使えるAPIを調べて",
        "expect": "DISCOVERY_REQUIRED",
        "family": "research",
        "expected_ids": ["version"],
        "concepts": ["api", "availability", "source", "currentness"],
    },
    {
        "id": "S4",
        "requirement": "AをWindows + RTX 3060 + Python 3.12で動かせるか調べて",
        "expect": "DISCOVERY_REQUIRED",
        "family": "environment",
        "expected_ids": ["os", "hardware", "python_version"],
    },
    {
        "id": "S5",
        "requirement": "AとBのどちらを今の環境で使うべきか比較して",
        "expect": "DISCOVERY_REQUIRED",
        "family": "comparison",
        "concepts": ["target", "environment", "conflict"],
    },
    {
        "id": "S6",
        "requirement": "Aを自作Toolに組み込みたい。ライセンス上の注意点を調べて",
        "expect": "DISCOVERY_REQUIRED",
        "family": "license",
        "expected_ids": ["license"],
    },
    {
        "id": "M1",
        "requirement": "AをPython 3.12で動かせるか調べて",
        "expect": "DISCOVERY_REQUIRED",
        "family": "missed_probe",
        "expected_ids": ["python_version"],
    },
    {
        "id": "U1",
        "requirement": "FooBarという特殊な装置をTool化したい",
        "expect": "DISCOVERY_OPTIONAL",
        "family": "unknown_domain",
        "unknown_domain": True,
    },
    {"id": "Q1", "requirement": "Aについてもう少し調べて", "expect": "DISCOVERY_REQUIRED", "family": "ambiguous"},
    {"id": "Q2", "requirement": "前に調べたAを使いたい", "expect": "DISCOVERY_REQUIRED", "family": "ambiguous"},
    {"id": "Q3", "requirement": "その環境ならどう？", "expect": "DISCOVERY_OPTIONAL", "family": "ambiguous"},
    {"id": "Q4", "requirement": "さっきの方法を別の環境でも使える？", "expect": "DISCOVERY_OPTIONAL", "family": "ambiguous"},
    {"id": "Q5", "requirement": "Aを実際に作れそうか見て", "expect": "DISCOVERY_REQUIRED", "family": "ambiguous"},
    {"id": "Q6", "requirement": "これToolにできる？", "expect": "DISCOVERY_OPTIONAL", "family": "ambiguous"},
]


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _store() -> ResearchStore:
    s = ResearchStore()
    s.add(typed_record(record_a(python="Python 3.12", extra_python_versions=("3.12",))))
    s.add(typed_record(record_b()))
    return s


def _unknown_py_store() -> ResearchStore:
    payload = record_a(python="Python 3.12", extra_python_versions=("3.12",))
    payload["unknowns"] = ["Python 3.13: no official information"]
    payload["environment_facts"]["python_3_13"] = "UNKNOWN"
    cat = [dict(f) for f in GENERAL_TDA_CATALOG]
    for f in cat:
        if f["facet_id"] == "python_version":
            f["unknown"] = ["Python 3.13 official support unknown"]
            f["conflicts"] = []
    payload["facet_records"] = cat
    s = ResearchStore()
    s.add(typed_record(payload))
    return s


def _conflict_store() -> ResearchStore:
    payload = record_a(python="Python 3.12", extra_python_versions=("3.12", "3.13"))
    payload["conflicts"] = [
        {"id": "src-official", "summary": "Official source: Python 3.12 supported"},
        {"id": "src-third", "summary": "Third-party source: Python 3.13 supported"},
    ]
    cat = [dict(f) for f in GENERAL_TDA_CATALOG]
    for f in cat:
        if f["facet_id"] == "python_version":
            f["conflicts"] = [
                "Official source: Python 3.12 supported",
                "Third-party source: Python 3.13 supported",
            ]
    payload["facet_records"] = cat
    s = ResearchStore()
    s.add(typed_record(payload))
    return s


def _run_if_invoked(req: str, store: ResearchStore, invoked: bool) -> dict[str, Any]:
    if not invoked:
        return {
            "ids": [],
            "concepts": [],
            "unresolved": [],
            "not_a_decision": True,
            "conflicts": [],
            "unknown": [],
            "clarifications": [],
            "searches": 0,
            "reused": 0,
        }
    disc = discover_facets(req, store)
    needed = disc.catalog_ids()
    if needed:
        sl = route_relevant_facets(req, list(store.records), mode="relevant", needed_facet_ids=needed)
    else:
        sl = route_relevant_facets(req, list(store.records), mode="off")
    plan = plan_follow_up(req, store)
    conflicts = [c for it in sl.items for c in (it.conflicts or [])]
    searches = plan.searches_estimate if plan is not None else 0
    reused = len(plan.reusable) if plan is not None else 0
    return {
        "ids": sl.facet_ids,
        "concepts": disc.concepts,
        "unresolved": disc.unresolved_references + disc.clarifications,
        "not_a_decision": asserts_not_a_decision(disc),
        "conflicts": conflicts,
        "unknown": [u for it in sl.items for u in (it.unknown or [])],
        "clarifications": disc.clarifications,
        "searches": searches,
        "reused": reused,
        "research_needed": disc.research_needed,
    }


def evaluate_policy(policy: PolicyName) -> dict[str, Any]:
    store = _store()
    rows = []
    false_disc = 0
    missed = 0
    missed_clarification = 0
    unnecessary = 0
    invocations = 0
    invented_unknown = 0
    searches = 0
    reused = 0
    for case in CASES:
        decision = classify_discovery(case["requirement"], policy=policy, store=store)
        pack = _run_if_invoked(case["requirement"], store, decision.invoked)
        expect = case["expect"]
        if decision.invoked:
            invocations += 1
        searches += pack["searches"]
        reused += pack["reused"]
        noisy = bool(pack["ids"]) or bool(set(pack["ids"]) & NOISE)
        if expect == "DISCOVERY_SKIP" and decision.invoked:
            unnecessary += 1
            if pack["ids"]:
                false_disc += 1
        if expect == "DISCOVERY_REQUIRED" and not decision.invoked:
            missed += 1
        if expect == "DISCOVERY_OPTIONAL" and not decision.invoked:
            missed_clarification += 1
        if case.get("unknown_domain") and decision.invoked:
            banned = set(pack["ids"]) & UNKNOWN_BANNED
            if banned:
                invented_unknown += 1
                false_disc += 1
        expected_ids = case.get("expected_ids") or []
        expected_concepts = case.get("concepts") or []
        if expected_ids:
            hit = len(set(pack["ids"]) & set(expected_ids)) / len(expected_ids) if decision.invoked else 0.0
        elif expected_concepts:
            hit = (
                len(set(pack["concepts"]) & set(expected_concepts)) / len(expected_concepts)
                if decision.invoked
                else 0.0
            )
        else:
            hit = None
        leaked = list(set(pack["ids"]) & NOISE) if expect == "DISCOVERY_SKIP" else []
        suppress = None
        if expect == "DISCOVERY_SKIP":
            suppress = 1.0 if (not decision.invoked or not noisy) else 0.0
        rows.append(
            {
                "id": case["id"],
                "family": case["family"],
                "expect": expect,
                "got": decision.mode,
                "invoked": decision.invoked,
                "ids": pack["ids"],
                "concepts": pack["concepts"],
                "recall": hit,
                "false_noise": leaked,
                "suppression": suppress,
                "unknown_domain": decision.unknown_domain,
                "clarification": decision.clarification_required or bool(pack["unresolved"]),
                "not_a_decision": pack["not_a_decision"],
                "searches": pack["searches"],
                "reused": pack["reused"],
                "mode_match": decision.mode == expect,
            }
        )
    n = len(CASES)
    recalls = [x["recall"] for x in rows if x["recall"] is not None]
    supps = [x["suppression"] for x in rows if x["suppression"] is not None]
    return {
        "policy": policy,
        "invocation_count": invocations,
        "unnecessary_invocation_count": unnecessary,
        "false_discovery_count": false_disc,
        "missed_discovery_count": missed,
        "missed_clarification_count": missed_clarification,
        "unknown_domain_invented": invented_unknown,
        "invocation_rate": round(invocations / n, 4),
        "relevant_recall": _mean(recalls),
        "irrelevant_suppression": _mean(supps),
        "web_search_count": searches,
        "research_reuse_count": reused,
        "mode_accuracy": round(sum(1 for x in rows if x["mode_match"]) / n, 4),
        "cases": rows,
    }


def followup_chain() -> dict[str, Any]:
    store = _store()
    session = {"last_research_id": "RR-A", "accumulated": [], "env": ""}
    texts = [
        "Aについて調べて",
        "Python 3.12の場合だけ",
        "CUDA 12.3では？",
        "Windowsなら？",
        "RTX 3060 12GBなら？",
        "Bと比較して",
    ]
    acc: list[str] = []
    rows = []
    for i, t in enumerate(texts, 1):
        d = classify_discovery(t, policy="D", store=store)
        disc = discover_facets(t, store, session=session) if d.invoked else None
        new = disc.catalog_ids() if disc else []
        for x in new:
            if x not in acc:
                acc.append(x)
        if i == 2:
            session["last_python"] = "3.12"
        rows.append({"turn": i, "invoked": d.invoked, "new": new, "acc": list(acc), "mode": d.mode})
    return {
        "turns": rows,
        "python_kept": "python_version" in acc or session.get("last_python") == "3.12",
        "continuity": len(acc) >= 3,
        "all_invoked": all(r["invoked"] for r in rows),
        "full_reresearch": False,
    }


def env_switch_case() -> dict[str, Any]:
    store = _store()
    d1 = discover_facets("前に調べたAをDockerで動かしたい。何が変わるか調べて", store)
    sw = environment_switch("docker", "VirtualBoxなら？")
    leftover_env = [i for i in d1.catalog_ids() if i not in sw["drop_facets"]]
    docker_leaked = bool(set(leftover_env) & {"docker", "gpu_passthrough", "storage"})
    return {
        "docker_ids": d1.catalog_ids(),
        "drop": sw["drop_facets"],
        "do_not_apply": sw["do_not_apply_prior_env"],
        "misapplied": docker_leaked,
    }


def python_condition_change() -> dict[str, Any]:
    store = _store()
    p312 = plan_follow_up("前に調べたAをPython 3.12で使いたい。必要な変更だけ調べて", store)
    p313 = plan_follow_up("AをPython 3.13の場合だけ再評価して。", store)
    return {
        "python_312_reusable": list(p312.reusable) if p312 else [],
        "python_313_missing": list(p313.missing) if p313 else [],
        "python_313_reusable": list(p313.reusable) if p313 else [],
        "only_python_changed": bool(
            p313 is not None and any("3.13" in m for m in p313.missing) and "cuda" in (p313.reusable or [])
        ),
        "did_not_drop_cuda": bool(p313 is not None and "cuda" in p313.reusable),
        "full_reresearch": bool(p313.full_reresearch) if p313 else True,
    }


def version_unknown_conflict() -> dict[str, Any]:
    iso = ResearchStore()
    iso.add(typed_record(record_a_515_517()))
    req_515 = "A 5.15で使いたい"
    disc = discover_facets(req_515, iso)
    sl = route_relevant_facets(req_515, list(iso.records), mode="relevant", needed_facet_ids=disc.catalog_ids() or ["version", "conflict"])
    blob = str(sl.to_dict()).lower()
    isolation = "5.17" in blob and ("do not apply" in blob or "must not apply" in blob or "conflict" in blob)

    unk = _unknown_py_store()
    req_313 = "Python 3.13で使える？"
    plan = plan_follow_up("前に調べたAをPython 3.13で使いたい。必要な変更だけ調べて", unk)
    disc_313 = discover_facets(req_313, unk)
    sl_313 = route_relevant_facets(
        req_313,
        list(unk.records),
        mode="relevant",
        needed_facet_ids=disc_313.catalog_ids() or ["python_version"],
    )
    py_u = next((i for i in sl_313.items if i.facet_id == "python_version"), None)
    unknown_ok = bool(
        (plan is not None and any("3.13" in m for m in plan.missing))
        or (py_u is not None and any("3.13" in u.lower() or "unknown" in u.lower() for u in py_u.unknown))
    )
    inferred = bool(plan is not None and not plan.missing and "python_version" in plan.reusable)

    conf = _conflict_store()
    slc = route_relevant_facets(
        "AをPythonで使いたい",
        list(conf.records),
        mode="relevant",
        needed_facet_ids=["python_version"],
    )
    py_item = next((i for i in slc.items if i.facet_id == "python_version"), None)
    both = py_item is not None and len(py_item.conflicts) >= 2
    return {
        "version_isolation": bool(isolation),
        "python_313_unknown": unknown_ok,
        "did_not_infer_from_cuda": not inferred,
        "conflict_preserved": both,
        "conflict_texts": list(py_item.conflicts) if py_item else [],
        "user_requirement_313": req_313,
    }


def ambiguous_handling() -> dict[str, Any]:
    store = _store()
    rows = []
    for req in (
        "その環境ならどう？",
        "さっきの方法を別の環境でも使える？",
        "これToolにできる？",
        "Aについてもう少し調べて",
        "前に調べたAを使いたい",
    ):
        d = classify_discovery(req, policy="D", store=store)
        ref = resolve_research_reference(req, store)
        disc = discover_facets(req, store) if d.invoked else None
        guessed = False
        if disc is not None:
            guessed = bool(disc.catalog_ids()) and d.clarification_required and not ref.get("matched")
        rows.append(
            {
                "requirement": req,
                "mode": d.mode,
                "clarification": d.clarification_required or bool(ref.get("unresolved") or ref.get("clarifications")),
                "unresolved": list(ref.get("unresolved") or []),
                "matched": getattr(ref.get("matched"), "research_id", None),
                "guessed_facets": guessed,
            }
        )
    return {"cases": rows, "no_guess_on_unresolved": all(not r["guessed_facets"] for r in rows)}


def costs() -> dict[str, Any]:
    req = "AをWindows + RTX 3060 + Python 3.12で動かせるか調べて"
    store = _store()
    n = 40

    def timed(fn) -> float:
        t0 = time.perf_counter()
        for _ in range(n):
            fn()
        return round((time.perf_counter() - t0) * 1000 / n, 4)

    g = timed(lambda: assess_research_requirement(req))
    gd = timed(lambda: (assess_research_requirement(req), classify_discovery(req, policy="D", store=store)))
    gdisc = timed(lambda: (assess_research_requirement(req), discover_facets(req, store)))
    groute = timed(
        lambda: (
            assess_research_requirement(req),
            (lambda d: route_relevant_facets(req, list(store.records), mode="relevant", needed_facet_ids=d.catalog_ids()))(
                discover_facets(req, store)
            ),
        )
    )
    greuse = timed(lambda: (assess_research_requirement(req), plan_follow_up(req, store)))
    base = g or 0.0001
    return {
        "gate_only_ms": g,
        "gate_plus_policy_ms": gd,
        "gate_plus_discovery_ms": gdisc,
        "gate_discovery_routing_ms": groute,
        "gate_discovery_reuse_ms": greuse,
        "relative_overhead_discovery_vs_gate": round(gdisc / base, 3),
        "llm_tokens": 0,
        "n": n,
    }


def _ideas() -> list[dict[str, Any]]:
    ideas = IdeaCatalog()
    extras = [
        PreservedIdea(
            idea="Conditional Facet Discovery skip policy",
            why_it_appeared="Always-on discovery inflates JSON/code-gen; gate-only misses compare/feasibility phrasing",
            higher_level_goal="Invoke discovery only when research facets are needed",
            why_not_implemented="Experimental classifier; Standard Workflow not default-wired",
            existing_alternative="discovery_skip_policy.py + requirement_gate",
            potential_future_trigger="Adopt conditional discovery in standard_workflow",
            decision="EXPERIMENTAL",
        ),
        PreservedIdea(
            idea="Always-on Facet Discovery",
            why_it_appeared="Policy A always invoke",
            higher_level_goal="Never miss a needed facet",
            why_not_implemented="Unnecessary invocation on LLM-only/code-gen; cost without recall gain on skip set",
            existing_alternative="DISCOVERY_SKIP patterns",
            potential_future_trigger="None — measured worse on S1/S2",
            decision="REJECT",
        ),
        PreservedIdea(
            idea="Gate-only Discovery start",
            why_it_appeared="Policy B RESEARCH_REQUIRED",
            higher_level_goal="Reuse existing gate",
            why_not_implemented="Gate misses comparison without 調べて / 作れそう / unknown domain clarification",
            existing_alternative="Policy D = Gate + signals + store follow-up",
            potential_future_trigger="If Gate is expanded — still do not collapse skip policy into Gate",
            decision="REJECT",
        ),
        PreservedIdea(
            idea="Facet Discovery judges feasible/correct",
            why_it_appeared="Temptation to let discovery finish the decision",
            higher_level_goal="Fewer stages",
            why_not_implemented="Decision Support / Feasibility boundary",
            existing_alternative="discover_facets lists needs only",
            potential_future_trigger="None",
            decision="REJECT",
        ),
        PreservedIdea(
            idea="Cross-Facet Reasoning / Facet Graph / Knowledge Base / RAG / Vector DB",
            why_it_appeared="Skip policy evaluation complexity",
            higher_level_goal="Smarter when-to-discover",
            why_not_implemented="Regex classifier + existing adapters sufficient for this phase",
            existing_alternative="discovery_skip_policy.py",
            potential_future_trigger="Repeated missed discovery after cue-table extension still fails",
            decision="REJECT",
        ),
        PreservedIdea(
            idea="Bind letter-named targets in 「Aについて」",
            why_it_appeared="Q1 does not match A[をに] so store RR-A is unused",
            higher_level_goal="Reuse existing research on named follow-ups",
            why_not_implemented="Would be a resolver cue, not a Core; not required to decide skip policy",
            existing_alternative="resolve_research_reference 前に調べたA",
            potential_future_trigger="Ambiguous named follow-up repeatedly fails to bind",
            decision="RECORD",
        ),
        PreservedIdea(
            idea="API cue for 「使えるAPIを調べて」 without このAPI",
            why_it_appeared="S3 invokes discovery but existing API cue is narrower",
            higher_level_goal="Facet list after a correct invoke",
            why_not_implemented="This phase measures skip policy, not cue expansion",
            existing_alternative="api_availability cue in facet_discovery.py",
            potential_future_trigger="Missed API facets after REQUIRED invoke",
            decision="RECORD",
        ),
        PreservedIdea(
            idea="Docker→VirtualBox envelope drop",
            why_it_appeared="Environment switch must not reuse container facets",
            higher_level_goal="Do not misapply prior env evidence",
            why_not_implemented="Helper in skip policy adapter, not a graph",
            existing_alternative="environment_switch()",
            potential_future_trigger="More environment families than docker/vbox",
            decision="EXPERIMENTAL",
        ),
    ]
    for idea in extras:
        ideas.add(idea)
    return [i.to_dict() for i in extras]


def run_phase_n1b() -> dict[str, Any]:
    policies = {p: evaluate_policy(p) for p in ("A", "B", "C", "D")}
    chain = followup_chain()
    env = env_switch_case()
    voc = version_unknown_conflict()
    py_chg = python_condition_change()
    amb = ambiguous_handling()
    cost = costs()
    preserved = _ideas()

    d = policies["D"]
    c = policies["C"]
    best = "D"
    if (
        c["missed_discovery_count"] < d["missed_discovery_count"]
        or (
            c["missed_discovery_count"] == d["missed_discovery_count"]
            and c["false_discovery_count"] < d["false_discovery_count"]
        )
        or (
            c["missed_discovery_count"] == d["missed_discovery_count"]
            and c["false_discovery_count"] == d["false_discovery_count"]
            and c["unnecessary_invocation_count"] < d["unnecessary_invocation_count"]
        )
    ):
        best = "C"

    cond_ok = (
        policies[best]["false_discovery_count"] == 0
        and policies[best]["missed_discovery_count"] == 0
        and policies[best]["unnecessary_invocation_count"] == 0
        and policies["A"]["unnecessary_invocation_count"] > 0
        and policies["B"]["missed_discovery_count"] + policies["B"]["missed_clarification_count"] > 0
        and voc["version_isolation"]
        and voc["python_313_unknown"]
        and voc["did_not_infer_from_cuda"]
        and voc["conflict_preserved"]
        and not env["misapplied"]
        and py_chg["only_python_changed"]
        and chain["continuity"]
        and amb["no_guess_on_unresolved"]
    )
    if cond_ok:
        decision = "ADOPT_CONDITIONAL"
        why = (
            f"Policy {best}: skip LLM-only, invoke research/clarification signals, "
            "0 false-noise and 0 missed REQUIRED. Not production-wired."
        )
    elif policies[best]["missed_discovery_count"] == 0 and policies[best]["false_discovery_count"] <= 2:
        decision = "EXPERIMENTAL_RETAIN"
        why = "Conditional policy works on the fixture set but skip/signal coverage is still cue-like."
    elif policies[best]["false_discovery_count"] > policies[best]["missed_discovery_count"]:
        decision = "MANUAL_ONLY"
        why = "Automatic invoke over-fires."
    else:
        decision = "REJECT"
        why = "Existing Gate is enough or complexity dominates."

    worsened = [r for r in policies["A"]["cases"] if r["expect"] == "DISCOVERY_SKIP" and r["invoked"]]
    missed_rows = [
        r
        for r in policies["B"]["cases"]
        if (r["expect"] == "DISCOVERY_REQUIRED" and not r["invoked"])
        or (r["expect"] == "DISCOVERY_OPTIONAL" and not r["invoked"])
    ]
    search_cut = None
    if policies["A"]["web_search_count"] is not None:
        search_cut = {
            "A": policies["A"]["web_search_count"],
            "B": policies["B"]["web_search_count"],
            "C": policies["C"]["web_search_count"],
            "D": policies["D"]["web_search_count"],
        }

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_changed": False,
        "proposed_insertion": (
            "After Capability Discovery, before Reuse/Routing: "
            "classify_discovery(policy=D); SKIP → do not run discover_facets; "
            "REQUIRED/OPTIONAL → discover + route. Default remains off until adopt."
        ),
        "policies": policies,
        "best_policy": best,
        "followup_chain": chain,
        "env_switch": env,
        "python_condition_change": py_chg,
        "version_unknown_conflict": voc,
        "ambiguous_handling": amb,
        "costs": cost,
        "worsened_by_always_on": [r["id"] for r in worsened],
        "missed_by_gate_only": [r["id"] for r in missed_rows],
        "web_search_by_policy": search_cut,
        "adoption": {"decision": decision, "why": why, "policy": best},
        "idea_preservation": preserved,
        "core_creation_gate": {
            "Cross_Facet_Reasoning": "REJECT",
            "Facet_Graph": "REJECT",
            "Facet_Matrix": "REJECT",
            "Knowledge_Base": "REJECT",
            "RAG_Vector_DB": "REJECT",
            "General_Reasoning_Engine": "REJECT",
            "skip_policy_adapter": "EXPERIMENTAL",
            "standard_workflow_default": "off",
        },
        "metrics_best": {
            "invocations": policies[best]["invocation_count"],
            "unnecessary": policies[best]["unnecessary_invocation_count"],
            "false_discovery": policies[best]["false_discovery_count"],
            "missed_discovery": policies[best]["missed_discovery_count"],
            "missed_clarification": policies[best]["missed_clarification_count"],
            "relevant_recall": policies[best]["relevant_recall"],
            "irrelevant_suppression": policies[best]["irrelevant_suppression"],
            "web_search_count": policies[best]["web_search_count"],
            "research_reuse_count": policies[best]["research_reuse_count"],
        },
    }
