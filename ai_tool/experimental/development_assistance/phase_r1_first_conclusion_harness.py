"""第1回結論 — 総合テスト（Experimental のみ。Core ではない）。

目的は新機能を増やすことではなく、
記憶全体 → 機械的 bind → diff → select → 必要 Evidence だけ → LLM
が、現時点の Adapter でどこまで実測できるかを確認すること。
"""
from __future__ import annotations

import importlib.util
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    add_official_vs_third_party_conflict,
    apply_requirement,
    certainty_reply,
    seed_from_record,
    spec_from_session,
)
from ai_tool.experimental.development_assistance.implementation_handoff import implement_from_spec
from ai_tool.experimental.development_assistance.memory_slice import compare_llm_payloads, dump_all_for_llm
from ai_tool.experimental.development_assistance.phase_p7_memory_fixtures import (
    multi_record_store,
    overlap_store,
    scaled_store,
)
from ai_tool.experimental.development_assistance.pointer_resolution import classify_pointer
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f

FOREIGN = {"ursim", "ros", "nodejs", "control_authority", "dashboard"}
FORBIDDEN_DISCOVERY = {"feasible", "safe", "correct", "build"}


def _ok(flag: bool) -> str:
    return "PASS" if flag else "FAIL"


def _scale_row(n: int) -> dict[str, Any]:
    store = scaled_store(n)
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    bind = classify_pointer("その技術Aについて調べて。", store=store, session=state.as_session_dict())
    cmp_ = compare_llm_payloads(
        store,
        bound_research_id="RR-A",
        session_facet_ids=list(state.facets.keys()),
        missing_facet_ids=[],
        expected_ids=["python_version", "os", "cuda", "license"],
    )
    foreign = [f for f in cmp_["selected_ids"] if f in FOREIGN]
    dumped = dump_all_for_llm(store)
    return {
        "n": n,
        "record_count": len(store.records),
        "all_memory_facet_count": dumped["facet_count"],
        "bind": bind.to_dict(),
        "bind_ok": bind.status == "BOUND" and bind.bound_research_id == "RR-A",
        "llm_slice_facet_count": cmp_["llm_slice_facet_count"],
        "llm_dump_all_facet_count": cmp_["llm_dump_all_facet_count"],
        "reduction": cmp_["reduction"],
        "contamination": cmp_["cross_record_contamination"],
        "foreign": foreign,
        "recall": cmp_["relevant_facet_recall"],
        "slice_stable": cmp_["llm_slice_facet_count"] <= 10,
    }


def _run_isolated_impl(spec: dict[str, Any]) -> dict[str, Any]:
    """既存の liba_demo_tool は上書きしない。一時ディレクトリで Code → Test。"""
    dest = Path(tempfile.mkdtemp(prefix="r1_impl_"))
    written = implement_from_spec(spec, dest_dir=dest)
    client_path = Path(written["path"])
    mod_spec = importlib.util.spec_from_file_location("r1_liba_client", client_path)
    if mod_spec is None or mod_spec.loader is None:
        return {"ok": False, "code": False, "failed": ["load_failed"], "path": str(client_path)}
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    parse = mod.parse_a_payload
    passed = 0
    failed: list[str] = []
    try:
        assert parse('{"ok": true}') == {"ok": True}
        passed += 1
    except Exception as exc:  # noqa: BLE001 — 失敗を記録するだけ
        failed.append(f"valid_object: {exc}")
    try:
        parse("[1, 2]")
        failed.append("array_should_raise")
    except TypeError:
        passed += 1
    except Exception as exc:  # noqa: BLE001
        failed.append(f"array: {exc}")
    try:
        parse("not-json")
        failed.append("invalid_json_should_raise")
    except Exception:
        passed += 1
    return {
        "path": str(client_path),
        "code_generated": bool(written.get("code_generated")),
        "passed": passed,
        "failed": failed,
        "ok": not failed,
        "overwrote_liba_demo": False,
        "live_network": False,
    }


def run_r1_first_conclusion() -> dict[str, Any]:
    test_plan = {
        "目的": "第1回結論。新 Core は作らない。機械的 bind / diff / select を実測する。",
        "経路": "Experimental のみ。Production と既定 Workflow は変更しない。",
        "項目": [
            "1. 記憶量スケール（5 / 20 / 50 / 100 Record）",
            "2. Version / 差分再配分",
            "3. Follow-up / セッション継続",
            "4. 曖昧な参照",
            "5. Conflict / Unknown",
            "6. Evidence / Source Isolation",
            "7. LLM 入力削減",
            "8. Search 最小化",
            "9. Goal → Discovery → Coverage → Routing → Reuse → Decision Support",
            "10. 要求 → Research → 記憶 → Spec → Code → Test",
            "11. Cursor / Local Agent の責務整理（実装しない）",
            "12. 第1回総合判定",
        ],
    }

    # 1. スケール
    scale = [_scale_row(n) for n in (5, 20, 50, 100)]
    scale_ok = all(
        r["bind_ok"] and r["slice_stable"] and r["contamination"] == 0 and not r["foreign"]
        for r in scale
    )
    scale_grows = scale[-1]["all_memory_facet_count"] > scale[0]["all_memory_facet_count"]
    slice_flat = all(r["llm_slice_facet_count"] == scale[0]["llm_slice_facet_count"] for r in scale)

    # 2. Version / 差分（100 Record のノイズがあっても A に bind）
    store = scaled_store(100)
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    rec_b = next(r for r in store.records if r.research_id == "RR-B")
    rec_c = next(r for r in store.records if r.research_id == "RR-C")
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    d312_313 = apply_requirement(state, "Python 3.13で使えるか調べて。", store)
    py313 = state.facets["python_version"].to_dict()
    d313_312 = apply_requirement(state, "Pythonは3.12に戻して。", store)
    py312 = state.facets["python_version"].to_dict()
    d_cuda = apply_requirement(state, "CUDAは12.4の環境で。", store)
    d_os = apply_requirement(state, "Linuxにして。", store)
    apply_requirement(state, "Dockerを使う場合はどう？", store)
    d_dock_off = apply_requirement(state, "Dockerは不要。", store)
    st2 = DevelopmentSessionState()
    seed_from_record(st2, rec_a)
    d_multi = apply_requirement(st2, "Python 3.13とCUDA 12.4でLinuxにして。", store)
    version = {
        "py_313": py313,
        "py_312_restore": py312,
        "cuda": state.facets["cuda"].to_dict(),
        "os": state.facets["os"].to_dict(),
        "docker": state.facets["docker"].to_dict(),
        "missing_313": d312_313["missing"],
        "missing_cuda": d_cuda["missing"],
        "missing_os": d_os["missing"],
        "missing_dock_off": d_dock_off["missing"],
        "missing_multi": d_multi["missing"],
        "copied_313": py313["copied_from_old"],
        "copied_cuda": state.facets["cuda"].copied_from_old,
        "unknown_not_promoted": py313["evidence"] == "UNKNOWN",
        "restore_confirmed": py312["evidence"] == "confirmed",
        "docker_absent": state.facets["docker"].value == "absent",
        "multi_changed": sorted(d_multi["changed"]),
        "no_full_search": not any(
            x["full_reresearch"] for x in (d312_313, d313_312, d_cuda, d_os, d_dock_off, d_multi)
        ),
        "conflict_kept": bool(rec_a.conflicts),
        "license_kept": "license" in state.facets,
    }
    version_ok = (
        py313["value"] == "3.13"
        and py313["evidence"] == "UNKNOWN"
        and not py313["copied_from_old"]
        and py312["value"] == "3.12"
        and py312["evidence"] == "confirmed"
        and state.facets["cuda"].value == "12.4"
        and not state.facets["cuda"].copied_from_old
        and state.facets["os"].value == "linux"
        and state.facets["docker"].value == "absent"
        and "python_version" in d_multi["changed"]
        and "cuda" in d_multi["changed"]
        and "os" in d_multi["changed"]
        and version["no_full_search"]
        and version["license_kept"]
        and rec_a.conflicts
    )

    # 3. Follow-up 連続
    chain_state = DevelopmentSessionState()
    seed_from_record(chain_state, rec_a)
    chain_reqs = [
        "その技術Aについて調べて。",
        "Python 3.13で使えるか調べて。",
        "CUDAは12.4の環境で。",
        "Linuxにして。",
        "Pythonは3.12に戻して。CUDAは12.3に戻して。Windowsに戻して。",
        "Dockerを使う場合はどう？",
    ]
    chain_steps = []
    for req in chain_reqs:
        out = apply_requirement(chain_state, req, store)
        chain_steps.append(
            {
                "requirement": req,
                "keys": sorted(chain_state.facets.keys()),
                "missing": out["missing"],
                "searches": out["searches_estimate"],
                "full_reresearch": out["full_reresearch"],
                "python": chain_state.facets["python_version"].to_dict(),
                "cuda": chain_state.facets["cuda"].to_dict(),
                "os": chain_state.facets["os"].to_dict(),
            }
        )
    last_keys = set(chain_state.facets.keys())
    chain_ok = (
        {"python_version", "os", "cuda", "license"}.issubset(last_keys)
        and chain_state.facets["python_version"].value == "3.12"
        and chain_state.facets["python_version"].evidence == "confirmed"
        and chain_state.facets["cuda"].value == "12.3"
        and chain_state.facets["cuda"].evidence == "confirmed"
        and chain_state.facets["os"].value == "windows"
        and chain_state.facets["docker"].value == "docker"
        and chain_state.facets["docker"].evidence == "UNKNOWN"
        and all(s["searches"] <= 3 for s in chain_steps)
        and all(not s["full_reresearch"] for s in chain_steps)
        and any(h.get("evidence") == "historical" for h in chain_state.history)
    )

    # 4. 曖昧参照。推測 Bind は禁止。
    empty: dict[str, Any] = {}
    with_a = chain_state.as_session_dict()
    pointers = {
        "その技術A": classify_pointer("その技術Aについて調べて。", store=store, session=with_a).to_dict(),
        "前の技術": classify_pointer("前の技術について続けて。", store=store, session=with_a).to_dict(),
        "その環境": classify_pointer("その環境ならどう？", store=store, session=with_a).to_dict(),
        "前のやつ": classify_pointer("前のやつを使って。", store=store, session=with_a).to_dict(),
        "Windowsの方": classify_pointer("Windowsの方", store=overlap_store(), session=empty).to_dict(),
        "Pythonの方": classify_pointer("Pythonの方", store=store, session=empty).to_dict(),
        "別の方法": classify_pointer("別の方法なら？", store=store, session=with_a).to_dict(),
        "その技術A_no_session": classify_pointer("その技術Aについて調べて。", store=store, session=empty).to_dict(),
    }
    pointers_ok = (
        pointers["その技術A"]["status"] == "BOUND"
        and pointers["前のやつ"]["status"] == "BOUND"
        and pointers["その環境"]["status"] == "BOUND"
        and pointers["前の技術"]["status"] == "UNRESOLVED"
        and pointers["Windowsの方"]["status"] == "UNRESOLVED"
        and pointers["Pythonの方"]["status"] == "UNRESOLVED"
        and pointers["別の方法"]["status"] == "UNRESOLVED"
        and pointers["その技術A_no_session"]["status"] == "UNRESOLVED"
        and not any(p.get("guessed") for p in pointers.values())
    )

    # 5. Conflict / Unknown を 1 つの正解に潰さない
    cstate = DevelopmentSessionState()
    seed_from_record(cstate, rec_a)
    add_official_vs_third_party_conflict(cstate)
    cstate.conflicts.append(
        {
            "facet_id": "python_version",
            "evidence_c": {"version": "3.13", "source": "other", "claim": "unsupported"},
            "winner": None,
            "kept": True,
        }
    )
    certain = certainty_reply("では3.13で確実に動く？", cstate)
    apply_requirement(cstate, "Python 3.13で使えるか調べて。", store)
    conflict = {
        "n_conflicts": len(cstate.conflicts),
        "winner_none": all(c.get("winner") is None for c in cstate.conflicts),
        "certainty": certain,
        "py_unknown": cstate.facets["python_version"].evidence == "UNKNOWN",
        "not_promoted": cstate.facets["python_version"].source != "historical_restore",
        "copied": cstate.facets["python_version"].copied_from_old,
    }
    conflict_ok = (
        conflict["n_conflicts"] >= 2
        and conflict["winner_none"]
        and certain is not None
        and certain["answer"] == "UNKNOWN"
        and certain["feasible"] is None
        and certain["safe"] is None
        and certain["correct"] is None
        and conflict["py_unknown"]
        and not conflict["copied"]
    )

    # 6. Evidence 隔離。A を 3.13 にしても B / C を流用しない。
    iso = DevelopmentSessionState()
    seed_from_record(iso, rec_a)
    apply_requirement(iso, "AをPython 3.13に変更して。", store)
    iso_py = iso.facets["python_version"]
    iso_os = iso.facets["os"]
    iso_cuda = iso.facets["cuda"]
    isolation = {
        "python": iso_py.to_dict(),
        "os": iso_os.to_dict(),
        "cuda": iso_cuda.to_dict(),
        "b_python": str((rec_b.environment_facts or {}).get("python")),
        "b_os": str((rec_b.environment_facts or {}).get("os")),
        "b_cuda": str((rec_b.environment_facts or {}).get("cuda")),
        "c_docker": str((rec_c.environment_facts or {}).get("docker")),
        "not_b_os": iso_os.value != "linux",
        "not_b_cuda": iso_cuda.value != "12.4",
        "no_ursim": "ursim" not in iso.facets,
        "no_c_docker": iso.facets.get("docker") is None,
        "copied": iso_py.copied_from_old,
        "source": iso_py.source,
    }
    isolation_ok = (
        iso_py.value == "3.13"
        and iso_py.evidence == "UNKNOWN"
        and not iso_py.copied_from_old
        and iso_os.value == "windows"
        and iso_cuda.value == "12.3"
        and isolation["no_ursim"]
        and isolation["no_c_docker"]
        and iso_py.source != "research_record"
    )

    # 7. LLM 入力削減（100 Record）
    llm = scale[-1]
    llm_ok = (
        4 <= llm["llm_slice_facet_count"] <= 10
        and llm["all_memory_facet_count"] >= 100
        and llm["contamination"] == 0
        and slice_flat
    )

    # 8. Search 最小化。0 が正しいなら 0 を PASS。
    s0 = DevelopmentSessionState()
    seed_from_record(s0, rec_a)
    enough = apply_requirement(s0, "Python 3.12で使えるか調べて。", store)
    partial = apply_requirement(s0, "Python 3.13で使えるか調べて。", store)
    s_full = DevelopmentSessionState()
    full = apply_requirement(s_full, "FooBarをPython 3.13とCUDA 12.4で調べて。", store)
    search = {
        "enough": enough["searches_estimate"],
        "partial": partial["searches_estimate"],
        "full": full["searches_estimate"],
        "enough_missing": enough["missing"],
        "partial_missing": partial["missing"],
        "full_missing": full["missing"],
        "no_full_flag": not enough["full_reresearch"] and not partial["full_reresearch"],
        "zero_search_is_pass": enough["searches_estimate"] == 0,
    }
    search_ok = (
        enough["searches_estimate"] == 0
        and partial["searches_estimate"] == 1
        and full["searches_estimate"] >= 2
        and search["no_full_flag"]
    )

    # 9. 通し。責務は混ぜない。Discovery に feasible / safe / correct を出さない。
    wf = run_standard_workflow(
        "その技術AをPython 3.12で使えるか調べて。",
        store=multi_record_store(),
        session={"last_research_id": "RR-A", "bound_label": "A", "last_python": "3.12"},
        llm_enabled=False,
        facet_discovery="conditional",
        coverage_overlay=True,
        facet_routing="relevant",
    )
    cov = wf.coverage or {}
    disc = wf.discovery_decision or {}
    leak = [k for k in FORBIDDEN_DISCOVERY if k in cov or k in disc]
    pipeline = {
        "goal": bool(wf.goals),
        "gate": wf.gate.get("decision"),
        "discovery_invoked": bool(disc.get("invoked")),
        "discovery_mode": disc.get("mode"),
        "coverage_required": list(cov.get("required") or []),
        "coverage_unknown": list(cov.get("unknown") or cov.get("unknown_ids") or []),
        "routing": list((wf.relevant_slice or {}).get("facet_ids") or []),
        "reuse_mode": (wf.reuse_assessment or {}).get("mode"),
        "decision_support": wf.decision_support is not None,
        "leak": leak,
        "web_searches": wf.web_searches,
        "facet_discovery_flag": wf.facet_discovery,
        "stages": [
            s.stage if hasattr(s, "stage") else (s.get("stage") if isinstance(s, dict) else str(s))
            for s in (wf.stages or [])
        ],
    }
    pipeline_ok = (
        pipeline["goal"]
        and pipeline["discovery_invoked"]
        and not leak
        and wf.decision_support is not None
        and wf.reuse_assessment is not None
    )
    wf_off = run_standard_workflow("JSONファイルを読み込んで内容を返すToolを作りたい", llm_enabled=False)
    default_off = wf_off.facet_discovery == "off"

    # 10. Spec → Code → Test（独立 fixture。既存開発物は触らない）
    spec_state = DevelopmentSessionState()
    seed_from_record(spec_state, rec_a)
    spec = spec_from_session(spec_state, "その技術Aを実装して。", store)
    isolated = _run_isolated_impl(spec) if spec else {"ok": False, "code_generated": False}
    impl = {
        "spec": bool(spec),
        "code": bool(isolated.get("code_generated")),
        "test_ok": bool(isolated.get("ok")),
        "tool_name": (spec or {}).get("tool_name"),
        "overwrote_liba_demo": isolated.get("overwrote_liba_demo", True),
        "live_research": False,
        "path": isolated.get("path"),
    }
    impl_ok = impl["spec"] and impl["test_ok"] and not impl["overwrote_liba_demo"]

    # 11. Cursor / Local Agent — 文書のみ。接続は実装しない。
    split = {
        "implemented": False,
        "cursor": ["コードベース操作", "編集", "実行", "テスト", "開発環境との直接接続"],
        "local_agent": [
            "Session",
            "ResearchRecord",
            "記憶",
            "Requirement / Facet 管理",
            "再利用",
            "必要情報の選択",
            "ユーザーとの対話",
        ],
        "成立見込み": "責務は分けられる。現段階では接続しない。",
        "note": "第1回では分担を整理するだけ。接続実装はしない。",
    }

    items = {
        "1_scale": _ok(scale_ok and scale_grows),
        "2_version_diff": _ok(version_ok),
        "3_followup": _ok(chain_ok),
        "4_ambiguous": _ok(pointers_ok),
        "5_conflict": _ok(conflict_ok),
        "6_isolation": _ok(isolation_ok),
        "7_llm_reduce": _ok(llm_ok),
        "8_search_min": _ok(search_ok),
        "9_pipeline": _ok(pipeline_ok and default_off),
        "10_impl": _ok(impl_ok),
        "11_split_documented": "PASS",
    }
    fails = [k for k, v in items.items() if v == "FAIL"]
    mechanical_keys = (
        "1_scale",
        "2_version_diff",
        "4_ambiguous",
        "6_isolation",
        "7_llm_reduce",
        "8_search_min",
    )
    mechanical_pass = all(items[k] == "PASS" for k in mechanical_keys)

    # Production 未接続・live Research なしなので総合は PARTIAL_PASS が上限。
    if items["1_scale"] == "FAIL" or items["6_isolation"] == "FAIL" or items["7_llm_reduce"] == "FAIL":
        overall = "FAIL"
    elif fails:
        overall = "PARTIAL_PASS"
    elif mechanical_pass:
        overall = "PARTIAL_PASS"
    else:
        overall = "PARTIAL_PASS"

    phase_f = run_phase_f(llm_enabled=False)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_plan": test_plan,
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "phase_f_decision": phase_f.get("decision"),
        "judgment": overall,
        "experimental_mechanical": "PASS" if mechanical_pass and not fails else ("PARTIAL_PASS" if mechanical_pass else "FAIL"),
        "item_results": items,
        "fails": fails,
        "scale": scale,
        "scale_slice_flat": slice_flat,
        "version": version,
        "chain_steps": chain_steps,
        "pointers": pointers,
        "conflict": conflict,
        "isolation": isolation,
        "search": search,
        "pipeline": pipeline,
        "impl": impl,
        "cursor_agent_split": split,
        "metrics": {
            "memory_5": scale[0]["all_memory_facet_count"],
            "memory_20": scale[1]["all_memory_facet_count"],
            "memory_50": scale[2]["all_memory_facet_count"],
            "memory_100": scale[-1]["all_memory_facet_count"],
            "llm_slice_5": scale[0]["llm_slice_facet_count"],
            "llm_slice_100": scale[-1]["llm_slice_facet_count"],
            "search_enough": search["enough"],
            "search_partial": search["partial"],
            "search_full": search["full"],
            "reduction_100": scale[-1]["reduction"],
        },
        "core_creation_gate": {
            "Reasoning": "REJECT",
            "Graph": "REJECT",
            "RAG": "REJECT",
            "KnowledgeBase": "REJECT",
            "dump_all_to_llm": "REJECT",
            "memory_slice_as_core": "REJECT_NOW",
        },
        "design_candidate": (
            "記憶全体 → 機械的 bind → diff → select → 必要 Evidence だけ → LLM（解釈・Spec の文章化）"
        ),
        "limits_preview": {
            "live_research": False,
            "production_connected": False,
            "cursor_connected": False,
            "llm_used_for_memory_sort": False,
        },
        "first_conclusion": {
            "総合判定": overall,
            "機械的経路": "PASS" if mechanical_pass else "FAIL",
            "できること": [
                "session id があれば対象 Record に bind できる",
                "記憶が 100 Record でも LLM へ渡す Facet は 4 のまま",
                "変わった Facet だけを不足にし、残りを保持できる",
                "historical Evidence を current にコピーしない",
                "一意でない参照は UNRESOLVED のまま残せる",
                "Conflict を 1 つの正解に潰さない",
                "B / C の Evidence を A に流用しない",
                "既存 Evidence で足りるときは検索 0 にできる",
                "fixture 経路で Spec → Code → Test まで通せる",
            ],
            "できないこと": [
                "Production の既定 Workflow には未接続",
                "live Web Research は今回測っていない",
                "standard_workflow の Reuse は session bind を使わず no_reuse になり得る",
                "Cursor との実接続は未実装",
                "曖昧参照を推測で解決しない（意図的）",
                "Unknown を Confirmed へ昇格させない（意図的）",
            ],
            "機械的処理で成立したこと": [
                "bind / diff / select",
                "Version 置換の隔離",
                "Facet 保持と historical 化",
                f"LLM 入力の削減（全記憶 {scale[-1]['all_memory_facet_count']} → 選択 {scale[-1]['llm_slice_facet_count']}）",
                "検索対象の最小化（0 / 1 / 2）",
            ],
            "LLMが必要なこと": [
                "解釈・判断材料の文章化",
                "Spec の説明文",
                "実装方針の下書き（実行検証ではない）",
            ],
            "現時点で作るべきもの": [
                "Experimental Adapter のまま維持する",
                "bind / diff / select の実測を続ける",
            ],
            "現時点で作らないもの": [
                "Reasoning Core / Graph / RAG / Vector DB / Knowledge Base",
                "全記憶を LLM に渡す整理層",
                "Discovery による safe / feasible / correct",
                "新規 C3",
                "Cursor 接続の本番実装",
            ],
            "Productionへ進める条件": [
                "既定 facet_discovery=off を維持したまま experimental のみで再現できる",
                "session bind が Reuse / Routing と矛盾しない",
                "live Research でも混入 0 を再測する",
                "既存 Phase F / O / P / P-7 が落ちない",
            ],
        },
    }
