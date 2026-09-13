"""R2：実Researchを含む記憶選択。Experimental のみ。Core ではない。"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    add_official_vs_third_party_conflict,
    apply_requirement,
    certainty_reply,
    seed_from_record,
    spec_from_session,
)
from ai_tool.experimental.development_assistance.memory_slice import compare_llm_payloads, dump_all_for_llm
from ai_tool.experimental.development_assistance.phase_r2_ingest import add_noise_records, ingest_core_store
from ai_tool.experimental.development_assistance.pointer_resolution import classify_pointer
from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f

FOREIGN = {"ursim", "ros", "nodejs", "control_authority", "dashboard"}
CURSOR_FIELDS = (
    "tool_name",
    "purpose",
    "runtime",
    "dependencies",
    "api_notes",
    "unknowns",
    "constraints",
    "license",
)
LOCAL_ONLY = (
    "session_facets",
    "conflicts",
    "research_id",
    "bind",
    "history",
)


def _ok(flag: bool) -> str:
    return "PASS" if flag else "FAIL"


def _copy_store(src: ResearchStore) -> ResearchStore:
    out = ResearchStore()
    for rec in src.records:
        out.add(copy.deepcopy(rec))
    return out


def _store_n(core: ResearchStore, n: int) -> ResearchStore:
    store = _copy_store(core)
    extra = max(0, n - len(store.records))
    if extra:
        add_noise_records(store, extra)
    return store


def _schema_audit(rec: ResearchRecord) -> dict[str, Any]:
    data = rec.to_dict()
    have = set(data.keys())
    wanted = {
        "record_id": "research_id で足りる",
        "session_id": "Session 側。Record に混ぜない",
        "subject / target": "topic + environment_facts.label",
        "facet": "facet_records（ingest 直後は空 → 機械導出）",
        "version": "version_facts",
        "environment": "environment_facts",
        "evidence": "facet_records[].evidence",
        "source": "sources",
        "timestamp": "checked_at",
        "status": "Session FacetSlot.evidence。Record のトップには無い",
        "unknown": "unknowns",
        "conflict": "conflicts",
        "historical/current": "Session history / FacetSlot。Record に混ぜない",
    }
    return {
        "existing_fields": sorted(have),
        "mapping": wanted,
        "schema_change": "none",
        "note": "記憶と検索結果と現在要求は、Record / run / Session で分ける。",
    }


def _scale_row(store: ResearchStore, rec_a: ResearchRecord) -> dict[str, Any]:
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    bind = classify_pointer(
        "前に調べた技術AをPython 3.13で使えるか調べて。",
        store=store,
        session=state.as_session_dict(),
    )
    cmp_ = compare_llm_payloads(
        store,
        bound_research_id=rec_a.research_id,
        session_facet_ids=list(state.facets.keys()),
        missing_facet_ids=[],
        expected_ids=["python_version", "os", "cuda", "license"],
    )
    foreign = [f for f in cmp_["selected_ids"] if f in FOREIGN]
    dumped = dump_all_for_llm(store)
    return {
        "n": len(store.records),
        "all_memory_facet_count": dumped["facet_count"],
        "bind_ok": bind.status == "BOUND" and bind.bound_research_id == rec_a.research_id,
        "llm_slice_facet_count": cmp_["llm_slice_facet_count"],
        "contamination": cmp_["cross_record_contamination"],
        "foreign": foreign,
        "reduction": cmp_["reduction"],
        "selected_ids": cmp_["selected_ids"],
    }


def run_r2_research_selection() -> dict[str, Any]:
    first_failures: list[str] = []
    core, ingest_reports = ingest_core_store()
    rec_a = next(r for r in core.records if r.research_id == "RR-A")
    rec_b = next(r for r in core.records if r.research_id == "RR-B")
    rec_c = next(r for r in core.records if r.research_id == "RR-C")

    empty_facets = [r["facet_count_before_derive"] for r in ingest_reports]
    if any(n == 0 for n in empty_facets):
        first_failures.append(
            "ingest直後の facet_records は空。既存 build_research_record だけでは "
            "LLM slice の Facet 数を測れない。derive_facet_records を Experimental Adapter として追加した。"
        )
    if "3." not in str((rec_a.environment_facts or {}).get("python") or ""):
        first_failures.append(
            "TDA の Python 抽出が Version を落とした。enrich_environment_from_candidates でも復元できなかった。"
        )

    store100 = _store_n(core, 100)
    rec_a100 = next(r for r in store100.records if r.research_id == "RR-A")

    # R2-1 実Research bind/diff/select
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a100)
    req = "前に調べた技術AをPython 3.13で使えるか調べて。"
    out = apply_requirement(state, req, store100)
    py = state.facets["python_version"]
    r21 = {
        "ingest": ingest_reports,
        "requirement": req,
        "bind": out["pointer"],
        "python": py.to_dict(),
        "os": state.facets["os"].to_dict() if "os" in state.facets else None,
        "cuda": state.facets["cuda"].to_dict() if "cuda" in state.facets else None,
        "license": state.facets["license"].to_dict() if "license" in state.facets else None,
        "missing": out["missing"],
        "reusable": out["reusable"],
        "product_api_on_record": any(f.get("facet_id") == "product_api" for f in rec_a100.facet_records),
        "searches": out["searches_estimate"],
        "full_reresearch": out["full_reresearch"],
        "copied": py.copied_from_old,
        "history_312": any(h.get("facet_id") == "python_version" and h.get("value") == "3.12" for h in state.history),
    }
    r21_ok = (
        out["pointer"]["status"] == "BOUND"
        and out["pointer"]["bound_research_id"] == "RR-A"
        and py.value == "3.13"
        and py.evidence == "UNKNOWN"
        and not py.copied_from_old
        and state.facets.get("os")
        and state.facets["os"].evidence == "confirmed"
        and state.facets.get("cuda")
        and state.facets["cuda"].evidence == "confirmed"
        and state.facets.get("license")
        and state.facets["license"].evidence == "confirmed"
        and out["searches_estimate"] == 1
        and not out["full_reresearch"]
        and r21["history_312"]
        and r21["product_api_on_record"]
    )
    if not r21_ok:
        first_failures.append("R2-1 実Research の bind/diff/select が期待と不一致")

    # R2-2 混入
    used_ids = {s["research_id"] for s in compare_llm_payloads(
        store100,
        bound_research_id="RR-A",
        session_facet_ids=list(state.facets.keys()),
        missing_facet_ids=[],
    )["slice"]["selected"]}
    isolation = {
        "python": py.to_dict(),
        "os_not_linux": state.facets["os"].value != "linux",
        "cuda_not_124": state.facets["cuda"].value != "12.4",
        "no_ursim": "ursim" not in state.facets,
        "no_nodejs": "nodejs" not in state.facets,
        "b_unused": rec_b.research_id not in used_ids,
        "selected_research_ids": sorted(used_ids),
        "b_python": str((rec_b.environment_facts or {}).get("python")),
        "c_topic": rec_c.topic,
    }
    r22_ok = (
        isolation["os_not_linux"]
        and isolation["cuda_not_124"]
        and isolation["no_ursim"]
        and isolation["no_nodejs"]
        and used_ids <= {"RR-A"}
    )

    # R2-3 機械的 diff
    diffs = []
    cases = [
        ("Python 3.12 → 3.13", "Python 3.13で使えるか調べて。", {"python_version"}),
        ("CUDA 12.3 → 12.4", "CUDAは12.4の環境で。", {"cuda"}),
        ("Windows → Linux", "Linuxにして。", {"os"}),
        ("Dockerあり → なし", "Dockerは不要。", {"docker"}),
        ("同時変更", "Python 3.13とCUDA 12.4でLinuxにして。", {"python_version", "cuda", "os"}),
    ]
    diff_ok_all = True
    for title, text, expect in cases:
        st = DevelopmentSessionState()
        seed_from_record(st, rec_a100)
        if "Docker" in title:
            apply_requirement(st, "Dockerを使う場合はどう？", store100)
        before = set(st.facets.keys())
        got = apply_requirement(st, text, store100)
        changed = set(got["changed"])
        kept = before <= set(st.facets.keys())
        only = expect <= changed and not got["full_reresearch"]
        row = {
            "title": title,
            "changed": sorted(changed),
            "missing": got["missing"],
            "kept_previous": kept,
            "full_reresearch": got["full_reresearch"],
        }
        diffs.append(row)
        if not (only and kept):
            diff_ok_all = False

    # R2-4 Unknown / Conflict
    cstate = DevelopmentSessionState()
    seed_from_record(cstate, rec_a100)
    add_official_vs_third_party_conflict(cstate)
    certain = certainty_reply("では3.13で確実に動く？", cstate)
    apply_requirement(cstate, "Python 3.13で使えるか調べて。", store100)
    r24 = {
        "py_312_history": any(h.get("value") == "3.12" for h in cstate.history),
        "py_313": cstate.facets["python_version"].to_dict(),
        "conflicts": cstate.conflicts,
        "winner_none": all(c.get("winner") is None for c in cstate.conflicts),
        "certainty": certain,
    }
    r24_ok = (
        r24["py_313"]["evidence"] == "UNKNOWN"
        and not r24["py_313"]["copied_from_old"]
        and r24["winner_none"]
        and certain is not None
        and certain["answer"] == "UNKNOWN"
        and certain["feasible"] is None
    )

    # R2-5 LLM 削減
    scale = []
    for n in (5, 20, 50, 100):
        st = _store_n(core, n)
        ra = next(r for r in st.records if r.research_id == "RR-A")
        scale.append(_scale_row(st, ra))
    r25_ok = all(
        r["bind_ok"] and r["contamination"] == 0 and not r["foreign"] and r["llm_slice_facet_count"] <= 10
        for r in scale
    ) and scale[-1]["all_memory_facet_count"] > scale[0]["all_memory_facet_count"]
    slice_flat = all(r["llm_slice_facet_count"] == scale[0]["llm_slice_facet_count"] for r in scale)

    # R2-6 保存形式
    schema = _schema_audit(rec_a)
    r26_ok = schema["schema_change"] == "none"

    # R2-7 Session handoff
    chain = DevelopmentSessionState()
    seed_from_record(chain, rec_a100)
    chain_reqs = [
        "技術Aについて調べて。",
        "Python 3.12で使えるか調べて。",
        "Windows環境ならどう？",
        "CUDA 12.3ならどう？",
        "Python 3.13で使えるか調べて。",
        "CUDAは12.4の環境で。",
        "Pythonは3.12に戻して。",
    ]
    steps = []
    for req in chain_reqs:
        got = apply_requirement(chain, req, store100)
        steps.append(
            {
                "requirement": req,
                "keys": sorted(chain.facets.keys()),
                "missing": got["missing"],
                "searches": got["searches_estimate"],
                "full": got["full_reresearch"],
                "python": chain.facets["python_version"].to_dict(),
            }
        )
    r27_ok = (
        chain.facets["python_version"].value == "3.12"
        and chain.facets["python_version"].evidence == "confirmed"
        and chain.facets["cuda"].value == "12.4"
        and "license" in chain.facets
        and all(not s["full"] for s in steps)
        and any(h.get("evidence") == "historical" for h in chain.history)
    )

    # R2-8 曖昧参照
    empty: dict[str, Any] = {}
    with_a = chain.as_session_dict()
    pointers = {
        "前の技術": classify_pointer("前の技術について続けて。", store=store100, session=with_a).to_dict(),
        "その技術": classify_pointer("その技術について続けて。", store=store100, session=with_a).to_dict(),
        "Windowsの方": classify_pointer("Windowsの方", store=store100, session=empty).to_dict(),
        "Pythonの方": classify_pointer("Pythonの方", store=store100, session=empty).to_dict(),
        "別の方法": classify_pointer("別の方法なら？", store=store100, session=with_a).to_dict(),
        "その環境": classify_pointer("その環境ならどう？", store=store100, session=with_a).to_dict(),
        "前に調べた技術A": classify_pointer(
            "前に調べた技術AをPython 3.13で使えるか調べて。",
            store=store100,
            session=with_a,
        ).to_dict(),
    }
    r28_ok = (
        pointers["前の技術"]["status"] == "UNRESOLVED"
        and pointers["その技術"]["status"] == "UNRESOLVED"
        and pointers["Windowsの方"]["status"] == "UNRESOLVED"
        and pointers["Pythonの方"]["status"] == "UNRESOLVED"
        and pointers["別の方法"]["status"] == "UNRESOLVED"
        and pointers["その環境"]["status"] == "BOUND"
        and pointers["前に調べた技術A"]["status"] == "BOUND"
        and pointers["前の技術"].get("clarification_required") is True
        and not any(p.get("guessed") for p in pointers.values())
    )

    items_18 = {
        "R2-1": _ok(r21_ok),
        "R2-2": _ok(r22_ok),
        "R2-3": _ok(diff_ok_all),
        "R2-4": _ok(r24_ok),
        "R2-5": _ok(r25_ok and slice_flat),
        "R2-6": _ok(r26_ok),
        "R2-7": _ok(r27_ok),
        "R2-8": _ok(r28_ok),
    }
    pass_18 = all(v == "PASS" for v in items_18.values())

    r29: dict[str, Any] = {"skipped": True, "reason": "R2-1〜R2-8 がすべて PASS でない"}
    r210: dict[str, Any] = {"skipped": True, "reason": "R2-1〜R2-8 がすべて PASS でない"}
    r29_ok = False
    r210_ok = False
    if pass_18:
        wf_off = run_standard_workflow("JSONファイルを読み込んで内容を返すToolを作りたい", llm_enabled=False)
        wf = run_standard_workflow(
            "前に調べた技術AをPython 3.13で使えるか調べて。",
            store=core,
            session={"last_research_id": "RR-A", "bound_label": "A", "last_python": "3.12"},
            llm_enabled=False,
            facet_discovery="conditional",
            coverage_overlay=True,
            facet_routing="relevant",
        )
        reuse_mode = (wf.reuse_assessment or {}).get("mode")
        connected = reuse_mode in {"partial_reuse", "full_reuse"}
        r29 = {
            "skipped": False,
            "default_discovery": wf_off.facet_discovery,
            "experimental_discovery": wf.facet_discovery,
            "reuse_mode": reuse_mode,
            "bind_wired_into_reuse": connected,
            "decision_support": wf.decision_support is not None,
            "leak": [k for k in ("feasible", "safe", "correct") if k in (wf.coverage or {}) or k in (wf.discovery_decision or {})],
            "note": (
                "既定は facet_discovery=off のまま。"
                "session bind は Reuse に未接続。接続には Experimental Adapter が必要。"
            ),
        }
        r29_ok = wf_off.facet_discovery == "off" and not r29["leak"]
        spec = spec_from_session(state, "その技術Aを実装して。", store100)
        r210 = {
            "skipped": False,
            "implemented": False,
            "spec_available": bool(spec),
            "to_cursor": list(CURSOR_FIELDS),
            "stay_local_agent": list(LOCAL_ONLY),
            "cursor": ["ファイル操作", "コード編集", "コード生成", "実行", "テスト", "Git 等"],
            "local_agent": [
                "Session",
                "ResearchRecord",
                "Memory",
                "Facet",
                "bind",
                "diff",
                "select",
                "Reuse",
                "Research",
                "Requirement整理",
            ],
            "envelope_keys": sorted((spec or {}).keys()) if spec else [],
        }
        r210_ok = bool(spec) and r210["implemented"] is False

    items = {
        **items_18,
        "R2-9": (
            "PARTIAL_PASS"
            if pass_18 and r29_ok and not r29.get("bind_wired_into_reuse")
            else (_ok(r29_ok) if pass_18 else "SKIP")
        ),
        "R2-10": _ok(r210_ok) if pass_18 else "SKIP",
    }
    fails = [k for k, v in items.items() if v == "FAIL"]
    mechanical = all(items_18[k] == "PASS" for k in ("R2-1", "R2-2", "R2-3", "R2-5"))
    if items.get("R2-1") == "FAIL" or items.get("R2-2") == "FAIL":
        overall = "FAIL"
    elif pass_18 and r29.get("bind_wired_into_reuse") is False:
        overall = "PARTIAL_PASS"
    elif fails:
        overall = "PARTIAL_PASS"
    elif mechanical:
        overall = "PARTIAL_PASS"
    else:
        overall = "FAIL"

    phase_f = run_phase_f(llm_enabled=False)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "phase_f_decision": phase_f.get("decision"),
        "judgment": overall,
        "experimental_mechanical": "PASS" if mechanical and items_18["R2-1"] == "PASS" else "FAIL",
        "item_results": items,
        "fails": fails,
        "first_failures": first_failures,
        "ingest_reports": ingest_reports,
        "r21": r21,
        "r22": isolation,
        "r23": diffs,
        "r24": r24,
        "r25": {"scale": scale, "slice_flat": slice_flat},
        "r26": schema,
        "r27": {"steps": steps, "final_python": chain.facets["python_version"].to_dict()},
        "r28": pointers,
        "r29": r29,
        "r210": r210,
        "metrics": {
            "memory_5": scale[0]["all_memory_facet_count"],
            "memory_20": scale[1]["all_memory_facet_count"],
            "memory_50": scale[2]["all_memory_facet_count"],
            "memory_100": scale[3]["all_memory_facet_count"],
            "llm_slice_5": scale[0]["llm_slice_facet_count"],
            "llm_slice_100": scale[3]["llm_slice_facet_count"],
            "reduction_100": scale[3]["reduction"],
            "ingest_facet_before": empty_facets,
            "searches_r21": r21["searches"],
        },
        "core_creation_gate": {
            "Reasoning": "REJECT",
            "Graph": "REJECT",
            "RAG": "REJECT",
            "KnowledgeBase": "REJECT",
            "dump_all_to_llm": "REJECT",
            "Production接続": "REJECT_NOW",
            "Cursor本番接続": "REJECT_NOW",
        },
    }
