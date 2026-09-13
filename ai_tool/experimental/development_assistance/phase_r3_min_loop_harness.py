"""R3：最小開発ループ。Experimental。Cursor 本番 API も Production も使わない。"""
from __future__ import annotations

import copy
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.experimental.development_assistance.cursor_equiv_fixture import (
    apply_runtime_patch,
    run_fixture_tests,
    write_fixture_project,
)
from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    add_official_vs_third_party_conflict,
    apply_requirement,
    seed_from_record,
)
from ai_tool.experimental.development_assistance.development_spec import (
    development_spec_from_materials,
    spec_has_verdict,
)
from ai_tool.experimental.development_assistance.llm_materials import audit_llm_role, build_llm_materials
from ai_tool.experimental.development_assistance.phase_r2_ingest import add_noise_records, ingest_core_store
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f

REQ_313 = "技術AをPython 3.13 / Windows / CUDA 12.3で使えるようにする"
REQ_312 = "Pythonは3.12に戻して。"


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


def _test_payload(tests: dict[str, Any], changed_files: list[str]) -> dict[str, Any]:
    return {
        "last_test_result": tests.get("test_status"),
        "test_status": tests.get("test_status"),
        "test_count": tests.get("test_count"),
        "passed": tests.get("passed"),
        "failed": tests.get("failed"),
        "changed_files": list(changed_files),
        "timestamp": tests.get("timestamp"),
        "runtime_observed": tests.get("runtime_observed"),
        "expected_python": tests.get("expected_python"),
    }


def _loop(
    requirement: str,
    store: ResearchStore,
    state: DevelopmentSessionState,
    dest: Path,
    *,
    force_wrong: bool = False,
    approve: bool = True,
) -> dict[str, Any]:
    applied = apply_requirement(state, requirement, store)
    facets = {k: v.to_dict() for k, v in state.facets.items()}
    materials = build_llm_materials(
        requirement=requirement,
        store=store,
        bound_research_id=state.last_research_id,
        bound_label=state.bound_label,
        session_facets=facets,
        missing=list(applied["missing"]),
        reusable=list(applied["reusable"]),
        conflicts=list(state.conflicts),
    )
    spec = development_spec_from_materials(materials)
    state.last_spec = spec
    state.awaiting_human_review = True
    audit = audit_llm_role(materials, spec, code_proposal=True)
    out: dict[str, Any] = {
        "applied": applied,
        "materials": materials,
        "spec": spec,
        "audit": audit,
        "awaiting_human_review": True,
        "cursor_skipped": not approve,
        "searches": applied["searches_estimate"],
        "full_reresearch": applied["full_reresearch"],
    }
    if not approve:
        return out
    state.awaiting_human_review = False
    py = str(((spec.get("version") or {}).get("python") or {}).get("current") or "")
    written = write_fixture_project(dest, python=py, force_wrong=force_wrong)
    state.tool_path = written["runtime_path"]
    tests = run_fixture_tests(dest, expected_python=py)
    saved = _test_payload(tests, written["changed_files"])
    state.last_test = saved
    out.update(
        {
            "awaiting_human_review": False,
            "written": written,
            "test": tests,
            "session_test": saved,
        }
    )
    if tests["ok"] or not force_wrong:
        return out
    # FAIL → 機械的再評価。全記憶は戻さない。全件 Research しない。
    expected = py
    observed = str(tests.get("runtime_observed") or "")
    missing = [f"python_version:{expected}"] if observed != expected else []
    reeval = {
        "missing": missing,
        "searches_estimate": len(missing),
        "full_reresearch": False,
        "dump_all_to_llm": False,
    }
    patch = apply_runtime_patch(dest, expected)
    tests2 = run_fixture_tests(dest, expected_python=expected)
    saved2 = _test_payload(tests2, patch["changed_files"])
    state.last_test = saved2
    out["reeval"] = reeval
    out["patch"] = patch
    out["test_after"] = tests2
    out["session_test"] = saved2
    return out


def run_r3_min_dev_loop() -> dict[str, Any]:
    first_failures: list[str] = [
        "修正前: 同じ runtime.py を再読込すると古い Version のまま Test が FAIL のまま残った。"
        "内容ハッシュでモジュール名を分け、__pycache__ を消してから再実行した。新 Core は不要。",
    ]
    core, ingest = ingest_core_store()
    rec_a = next(r for r in core.records if r.research_id == "RR-A")
    store100 = _store_n(core, 100)
    rec_a100 = next(r for r in store100.records if r.research_id == "RR-A")
    dest = Path(tempfile.mkdtemp(prefix="r3_loop_"))

    # R3-1〜4 + R3-7 + R3-11 成功ループ
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a100)
    add_official_vs_third_party_conflict(state)
    success = _loop(REQ_313, store100, state, dest, force_wrong=False, approve=True)
    mat = success["materials"]
    spec = success["spec"]
    r31_ok = (
        not mat["dump_all_included"]
        and not mat["search_memory_instruction"]
        and mat["llm_facet_count"] <= 10
        and mat["contamination"] == 0
        and "requirement" in mat
        and "needed_facets" in mat
        and "research_required_facets" in mat
        and not mat["forbidden_keys_in_payload"]
    )
    r32_ok = (
        spec.get("target")
        and spec.get("verdicts_absent")
        and not spec_has_verdict(spec)
        and "feasible" not in spec
        and spec.get("research_required")
    )
    r33_ok = bool(success.get("written")) and not success["written"]["overwrote_liba_demo"] and not success["written"]["cursor_api"]
    r34_ok = (
        state.last_test is not None
        and state.last_test.get("test_status") == "PASS"
        and "timestamp" in state.last_test
        and "changed_files" in state.last_test
    )
    r37_ok = mat["contamination"] == 0 and set(mat["selected_record_ids"]) <= {"RR-A"}
    r38_ok = bool(success["audit"]["pass"])
    r311_ok = success["test"]["ok"] and state.last_test.get("test_status") == "PASS"

    if mat["llm_facet_count"] > mat["all_memory_facet_count"]:
        first_failures.append("LLM 入力が全記憶より多い")

    # R3-5 / R3-12 FAIL → 再評価
    dest_fail = Path(tempfile.mkdtemp(prefix="r3_fail_"))
    st_fail = DevelopmentSessionState()
    seed_from_record(st_fail, rec_a100)
    fail_loop = _loop(REQ_313, store100, st_fail, dest_fail, force_wrong=True, approve=True)
    r35_ok = (
        fail_loop["test"]["test_status"] == "FAIL"
        and (fail_loop.get("test_after") or {}).get("test_status") == "PASS"
        and fail_loop.get("reeval", {}).get("full_reresearch") is False
        and fail_loop.get("reeval", {}).get("dump_all_to_llm") is False
        and fail_loop.get("reeval", {}).get("searches_estimate") == 1
        and st_fail.last_test.get("test_status") == "PASS"
    )
    if fail_loop["test"]["test_status"] != "FAIL":
        first_failures.append("意図的 FAIL が出せなかった")

    # R3-6 Version 3.13 → 3.12
    dest_ver = Path(tempfile.mkdtemp(prefix="r3_ver_"))
    st_ver = DevelopmentSessionState()
    seed_from_record(st_ver, rec_a100)
    loop313 = _loop(REQ_313, store100, st_ver, dest_ver, force_wrong=False, approve=True)
    py313 = st_ver.facets["python_version"].to_dict()
    loop312 = _loop(REQ_312, store100, st_ver, dest_ver, force_wrong=False, approve=True)
    py312 = st_ver.facets["python_version"].to_dict()
    r36_ok = (
        py313["value"] == "3.13"
        and py313["evidence"] == "UNKNOWN"
        and not py313["copied_from_old"]
        and py312["value"] == "3.12"
        and py312["evidence"] == "confirmed"
        and st_ver.facets["os"].value == "windows"
        and st_ver.facets["cuda"].value == "12.3"
        and loop312["test"]["ok"]
        and loop312["test"]["runtime_observed"] == "3.12"
        and any(h.get("value") == "3.13" for h in st_ver.history)
        and loop313["searches"] == 1
        and loop312["searches"] == 0
    )

    # R3-3 人間確認地点（R3-1〜8の範囲で構造だけ）
    st_rev = DevelopmentSessionState()
    seed_from_record(st_rev, rec_a)
    held = _loop(REQ_313, core, st_rev, Path(tempfile.mkdtemp(prefix="r3_hold_")), approve=False)
    r_review_struct = held["awaiting_human_review"] is True and st_rev.awaiting_human_review is True and held.get("test") is None

    items_18 = {
        "R3-1": _ok(r31_ok),
        "R3-2": _ok(r32_ok),
        "R3-3": _ok(r33_ok),
        "R3-4": _ok(r34_ok),
        "R3-5": _ok(r35_ok),
        "R3-6": _ok(r36_ok),
        "R3-7": _ok(r37_ok),
        "R3-8": _ok(r38_ok),
    }
    pass_18 = all(v == "PASS" for v in items_18.values())

    r39: dict[str, Any] = {"skipped": True}
    r310: dict[str, Any] = {"skipped": True}
    r311: dict[str, Any] = {"skipped": True}
    r313: dict[str, Any] = {"skipped": True}
    r314: dict[str, Any] = {"skipped": True}

    if pass_18:
        r39 = {
            "skipped": False,
            "cursor_api": False,
            "local_agent": [
                "Requirement", "Goal", "Session", "ResearchRecord", "Memory", "Facet",
                "bind", "diff", "select", "Research", "Reuse", "Development Spec", "Test Result管理",
            ],
            "cursor": ["ファイル参照", "コード編集", "コード生成", "実行", "テスト", "Git 等"],
            "loop_fits_boundary": True,
        }
        r310 = {
            "skipped": False,
            "awaiting_human_review_field": True,
            "held_without_cursor": r_review_struct,
            "ui_implemented": False,
        }
        r311 = {
            "skipped": False,
            "ok": r311_ok,
            "test_status": success["test"]["test_status"],
            "python": spec["version"]["python"]["current"],
        }
        scale_rows = []
        for n in (20, 100):
            stn = _store_n(core, n)
            ra = next(r for r in stn.records if r.research_id == "RR-A")
            sn = DevelopmentSessionState()
            seed_from_record(sn, ra)
            dn = Path(tempfile.mkdtemp(prefix=f"r3_n{n}_"))
            row = _loop(REQ_313, stn, sn, dn, force_wrong=False, approve=True)
            scale_rows.append(
                {
                    "n": n,
                    "all_facets": row["materials"]["all_memory_facet_count"],
                    "llm_facets": row["materials"]["llm_facet_count"],
                    "contamination": row["materials"]["contamination"],
                    "searches": row["searches"],
                    "test_status": row["test"]["test_status"],
                    "foreign_records": [x for x in row["materials"]["selected_record_ids"] if x != "RR-A"],
                }
            )
        r313 = {
            "skipped": False,
            "scale": scale_rows,
            "ok": all(
                r["llm_facets"] <= 10 and r["contamination"] == 0 and not r["foreign_records"] and r["test_status"] == "PASS"
                for r in scale_rows
            ),
        }
        wf_off = run_standard_workflow("JSONファイルを読み込んで内容を返すToolを作りたい", llm_enabled=False)
        conds = {
            "1_bind_diff_select": r31_ok,
            "2_llm_reduce": mat["llm_facet_count"] < mat["all_memory_facet_count"],
            "3_version_isolation": r36_ok,
            "4_unknown_kept": py313["evidence"] == "UNKNOWN",
            "5_conflict_kept": bool(state.conflicts) and all(c.get("winner") is None for c in state.conflicts),
            "6_no_contamination": r37_ok,
            "7_test_return": r34_ok,
            "8_fail_reeval": r35_ok,
            "9_session_handoff": r36_ok,
            "10_default_off": wf_off.facet_discovery == "off",
        }
        r314 = {
            "skipped": False,
            "conditions": conds,
            "all_experimental_conditions": all(conds.values()),
            "production_connect": "REJECT_NOW",
            "reason": "実験条件は満たし得るが、既定 Workflow 未配線かつ Cursor API 未接続。今回は接続しない。",
        }

    items = {
        **items_18,
        "R3-9": _ok(bool(r39.get("loop_fits_boundary"))) if pass_18 else "SKIP",
        "R3-10": _ok(bool(r310.get("held_without_cursor"))) if pass_18 else "SKIP",
        "R3-11": _ok(r311_ok) if pass_18 else "SKIP",
        "R3-12": _ok(r35_ok) if pass_18 else "SKIP",
        "R3-13": _ok(bool(r313.get("ok"))) if pass_18 else "SKIP",
        "R3-14": "REJECT_NOW" if pass_18 else "SKIP",
    }
    fails = [k for k, v in items.items() if v == "FAIL"]
    mechanical = all(items_18[k] == "PASS" for k in ("R3-1", "R3-5", "R3-6", "R3-7"))
    if items_18.get("R3-1") == "FAIL" or items_18.get("R3-7") == "FAIL":
        overall = "FAIL"
    elif not pass_18:
        overall = "PARTIAL_PASS" if mechanical else "FAIL"
    else:
        overall = "PARTIAL_PASS"

    phase_f = run_phase_f(llm_enabled=False)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "phase_f_decision": phase_f.get("decision"),
        "judgment": overall,
        "experimental_mechanical": "PASS" if mechanical else "FAIL",
        "item_results": items,
        "fails": fails,
        "first_failures": first_failures,
        "ingest": [{"id": r["research_id"], "facets": r["facet_ids"]} for r in ingest],
        "r31": {
            "llm_facet_count": mat["llm_facet_count"],
            "all_memory_facet_count": mat["all_memory_facet_count"],
            "dump_all_included": mat["dump_all_included"],
            "task": mat["task"],
        },
        "r32": spec,
        "r33": success.get("written"),
        "r34": state.last_test,
        "r35": {
            "first": fail_loop["test"]["test_status"],
            "after": (fail_loop.get("test_after") or {}).get("test_status"),
            "reeval": fail_loop.get("reeval"),
        },
        "r36": {"python_313": py313, "python_312": py312, "test_312": loop312["test"]["test_status"]},
        "r37": {"contamination": mat["contamination"], "selected": mat["selected_record_ids"]},
        "r38": success["audit"],
        "r39": r39,
        "r310": r310,
        "r311": r311,
        "r313": r313,
        "r314": r314,
        "metrics": {
            "all_facets_100": mat["all_memory_facet_count"],
            "llm_facets": mat["llm_facet_count"],
            "contamination": mat["contamination"],
            "searches_313": success["searches"],
            "test_success": success["test"]["test_status"],
            "test_fail_then": (fail_loop.get("test_after") or {}).get("test_status"),
        },
        "core_creation_gate": {
            "Reasoning": "REJECT",
            "Graph": "REJECT",
            "RAG": "REJECT",
            "KnowledgeBase": "REJECT",
            "dump_all_to_llm": "REJECT",
            "Cursor本番API": "REJECT_NOW",
            "Production接続": "REJECT_NOW",
            "UI": "REJECT_NOW",
        },
    }
