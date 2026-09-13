"""NH12-1 case inventory and dataset packing utilities (research-only)."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

FRAMEWORK = Path(__file__).resolve().parents[3]
V0 = FRAMEWORK.parents[3]
LLM_BENCH = FRAMEWORK.parents[5]
WEB = V0 / "analysis" / "web_effect_review"
SQD = WEB / "search_quality_diagnosis"
TRACE = WEB / "search_path_trace"
RUN50 = V0 / "results" / "run_v0_50"
OBS_BATCH = LLM_BENCH / "capability_route_obs" / "collect_batch_remaining"
CASES_SNAPSHOT = RUN50 / "cases_snapshot.json"

NH11_SOURCE_IDS = {
    "A06",
    "C02",
    "C03",
    "B05",
    "A04",
    "A03",
    "E02",
    "E04",
    "WB02",
    "C04",
    "P02a",
    "A01",
    "fail_empty_hits",
}

# 30 new cases: type diversity, not in NH11
NH12_SELECTED: list[dict[str, Any]] = [
    {"case_id": "A02", "cohort": "R", "type_tags": ["empty_result", "handoff"], "source": "run_v0_50"},
    {"case_id": "A05", "cohort": "R", "type_tags": ["empty_result", "runtime_error"], "source": "run_v0_50"},
    {"case_id": "B01", "cohort": "R", "type_tags": ["handoff", "runtime_error"], "source": "run_v0_50"},
    {"case_id": "B02", "cohort": "R", "type_tags": ["handoff", "正常系"], "source": "run_v0_50"},
    {"case_id": "B03", "cohort": "R", "type_tags": ["code_path_ambiguity", "evidence"], "source": "run_v0_50"},
    {"case_id": "B06", "cohort": "R", "type_tags": ["code_path_ambiguity"], "source": "run_v0_50"},
    {"case_id": "C01", "cohort": "R", "type_tags": ["empty_result", "code_path_ambiguity"], "source": "run_v0_50"},
    {"case_id": "C05", "cohort": "R", "type_tags": ["ranking_filter", "handoff"], "source": "run_v0_50"},
    {"case_id": "D01", "cohort": "R", "type_tags": ["code_path_ambiguity"], "source": "run_v0_50"},
    {"case_id": "D03", "cohort": "R", "type_tags": ["code_path_ambiguity"], "source": "run_v0_50"},
    {"case_id": "D05", "cohort": "R", "type_tags": ["code_path_ambiguity", "evidence"], "source": "run_v0_50"},
    {"case_id": "E01", "cohort": "R", "type_tags": ["empty_result", "evidence"], "source": "run_v0_50"},
    {"case_id": "E03", "cohort": "R", "type_tags": ["empty_result"], "source": "run_v0_50"},
    {"case_id": "E05", "cohort": "R", "type_tags": ["wrong_output", "empty_result"], "source": "run_v0_50"},
    {"case_id": "F01", "cohort": "R", "type_tags": ["empty_result", "runtime_error"], "source": "run_v0_50"},
    {"case_id": "F02", "cohort": "R", "type_tags": ["empty_result", "wrong_output"], "source": "run_v0_50"},
    {"case_id": "F04", "cohort": "R", "type_tags": ["evidence", "ranking_filter"], "source": "run_v0_50"},
    {"case_id": "F05", "cohort": "R", "type_tags": ["wrong_output"], "source": "run_v0_50"},
    {"case_id": "G01", "cohort": "R", "type_tags": ["正常系", "handoff"], "source": "run_v0_50"},
    {"case_id": "G04", "cohort": "R", "type_tags": ["正常系"], "source": "run_v0_50"},
    {"case_id": "G06", "cohort": "R", "type_tags": ["runtime_error", "tool_gap"], "source": "run_v0_50"},
    {"case_id": "H01", "cohort": "R", "type_tags": ["複数問題", "handoff", "evidence"], "source": "run_v0_50"},
    {"case_id": "H02", "cohort": "R", "type_tags": ["複数問題", "handoff"], "source": "run_v0_50"},
    {"case_id": "H03", "cohort": "R", "type_tags": ["複数問題", "code_path_ambiguity"], "source": "run_v0_50"},
    {"case_id": "P02b", "cohort": "R", "type_tags": ["empty_result", "paraphrase"], "source": "run_v0_50"},
    {
        "case_id": "composite_file_and_web",
        "cohort": "R",
        "type_tags": ["複数問題", "handoff"],
        "source": "obs_batch",
    },
    {
        "case_id": "needs_new_tool_hint",
        "cohort": "R",
        "type_tags": ["runtime_error", "tool_gap"],
        "source": "obs_batch",
    },
    {
        "case_id": "agent_file_read",
        "cohort": "R",
        "type_tags": ["正常系", "code_path_ambiguity"],
        "source": "obs_batch",
    },
    {
        "case_id": "web_word_but_explain_tool",
        "cohort": "R",
        "type_tags": ["code_path_ambiguity"],
        "source": "obs_batch",
    },
    {
        "case_id": "web_needed_news",
        "cohort": "R",
        "type_tags": ["handoff", "empty_result"],
        "source": "obs_batch",
    },
]

TYPE_DEFICIT_NOTE = {
    "state": "実ログ不足: State遷移専用ログは利用可能素材に無い。無理な合成ケースは作らない。",
}


def mask_text(s: str) -> str:
    s = s or ""
    s = re.sub(r"[A-Za-z]:\\\\[^\s\"']+", "[PATH]", s)
    s = re.sub(r"[A-Za-z]:/[^\s\"']+", "[PATH]", s)
    s = re.sub(r"D:\\\\AI-Agent[^\s\"']*", "[REPO]", s)
    s = re.sub(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*\S+", r"\1=[REDACTED]", s)
    s = re.sub(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED]", s)
    return s


def trunc(obj: Any, n: int = 1800) -> str:
    t = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2)
    t = mask_text(t)
    return t if len(t) <= n else t[:n] + "\n...[truncated]"


def load_json(p: Path) -> Any:
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def caproute_path(case_id: str, source: str) -> Path:
    if source == "obs_batch":
        return OBS_BATCH / case_id / "capability_route.jsonl"
    return RUN50 / case_id / "capability_route.jsonl"


def read_caproute(case_id: str, source: str = "run_v0_50") -> dict[str, Any]:
    p = caproute_path(case_id, source)
    if not p.exists():
        return {}
    lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    out: dict[str, Any] = {"events": []}
    for ev in lines:
        kind = ev.get("kind")
        if kind == "capability_route_observation":
            out["request"] = ev.get("request")
            tried = ev.get("agent_tools_tried") or []
            out["tools_tried"] = [
                {
                    "tool": t.get("tool_name"),
                    "outcome": t.get("search_web_outcome"),
                    "hit_count": t.get("hit_count"),
                    "error": t.get("error"),
                    "args_preview": (t.get("arguments_digest") or {}).get("preview"),
                }
                for t in tried
            ]
            out["web"] = ev.get("web_search")
        out["events"].append({"kind": kind, "ts": ev.get("ts")})
    return out


def read_trace(case_id: str) -> dict[str, Any]:
    p = TRACE / "examples" / case_id / "trace.json"
    if p.exists():
        return load_json(p) or {}
    st = SQD / "stage_trace" / f"{case_id}.json"
    if st.exists():
        return load_json(st) or {}
    return {}


def case_trace_row(case_id: str) -> dict[str, str]:
    csv_path = TRACE / "case_trace.csv"
    if not csv_path.exists():
        return {}
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("case_id") == case_id:
                return dict(row)
    return {}


def snapshot_request(case_id: str) -> str | None:
    snap = load_json(CASES_SNAPSHOT)
    if not snap:
        return None
    for c in snap.get("cases") or []:
        if c.get("id") == case_id:
            return c.get("request")
    return None


def inventory_row(case_id: str, source: str = "run_v0_50") -> dict[str, Any]:
    trace_p = TRACE / "examples" / case_id / "trace.json"
    stage_p = SQD / "stage_trace" / f"{case_id}.json"
    cap_p = caproute_path(case_id, source)
    exec_p = (
        (OBS_BATCH if source == "obs_batch" else RUN50) / case_id / "execution_identity.jsonl"
    )
    stdout_p = (OBS_BATCH if source == "obs_batch" else RUN50) / case_id / "stdout.txt"
    in_nh11 = case_id in NH11_SOURCE_IDS
    selected = any(s["case_id"] == case_id for s in NH12_SELECTED)
    return {
        "case_id": case_id,
        "source_path": str(cap_p) if cap_p.exists() else str(cap_p.with_suffix(".missing")),
        "source_kind": source,
        "cohort": "baseline_nh11" if in_nh11 else ("R" if selected else None),
        "type_tags": next((s["type_tags"] for s in NH12_SELECTED if s["case_id"] == case_id), []),
        "has_trace": trace_p.exists() or stage_p.exists(),
        "has_ranking_trace": (TRACE / "examples" / case_id / "hits_after_ranking.json").exists(),
        "has_raw_api": (TRACE / "examples" / case_id / "raw_api_results.json").exists(),
        "has_agent_log": stdout_p.exists(),
        "has_execution_identity": exec_p.exists(),
        "has_caproute": cap_p.exists(),
        "known_cause": "true" if case_id in {"A06", "C02", "C03", "E04", "A03", "WB02", "P02b"} else "unknown",
        "sensitive_data_risk": "low",
        "in_nh11_baseline": in_nh11,
        "selected": selected,
        "selection_reason": (
            "NH11 baseline（再実行しない）"
            if in_nh11
            else ("NH12-1 新規選択" if selected else "未選択")
        ),
    }


def build_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cid in sorted(NH11_SOURCE_IDS):
        src = "obs_batch" if cid == "fail_empty_hits" else "run_v0_50"
        rows.append(inventory_row(cid, src))
    for d in RUN50.iterdir():
        if d.is_dir() and d.name not in NH11_SOURCE_IDS:
            rows.append(inventory_row(d.name, "run_v0_50"))
    for d in OBS_BATCH.iterdir():
        if d.is_dir() and d.name not in NH11_SOURCE_IDS:
            if not any(r["case_id"] == d.name for r in rows):
                rows.append(inventory_row(d.name, "obs_batch"))
    return rows


def pack_case(spec: dict[str, Any]) -> dict[str, Any]:
    case_id = spec["case_id"]
    cohort = spec["cohort"]
    types = spec["type_tags"]
    source = spec.get("source", "run_v0_50")
    trace = read_trace(case_id)
    cap = read_caproute(case_id, source)
    row = case_trace_row(case_id)
    request = trace.get("request") or cap.get("request") or snapshot_request(case_id) or case_id
    stages = trace.get("stages") or {}
    drop = trace.get("drop_notes") or ([row.get("drop_notes")] if row.get("drop_notes") else [])

    runtime_parts: list[str] = []
    if stages:
        runtime_parts.append("[OBSERVED] stages=" + json.dumps(stages, ensure_ascii=False))
    if drop:
        runtime_parts.append("[OBSERVED] drop_notes=" + "; ".join(str(x) for x in drop if x))
    if row:
        runtime_parts.append(
            "[OBSERVED] case_trace: return={r} content_nonempty={c} content_empty={e}".format(
                r=row.get("return件数"),
                c=row.get("内容あり件数_return"),
                e=row.get("内容なし件数_return"),
            )
        )
    if cap.get("tools_tried"):
        runtime_parts.append("[OBSERVED] agent_tools_tried=" + trunc(cap["tools_tried"], 900))
    exec_p = (OBS_BATCH if source == "obs_batch" else RUN50) / case_id / "execution_identity.jsonl"
    if exec_p.exists():
        runtime_parts.append("[OBSERVED] execution_identity_digest=" + trunc(exec_p.read_text(encoding="utf-8")[:600], 600))
    if not runtime_parts:
        runtime_parts.append("なし（実測ログ未提供）")

    code_excerpt = (
        "search_web → general_web_search 公開経路。"
        "backends: duckduckgo / wikipedia-ja / wikipedia-en。"
        "Wiki snippet=OpenSearch payload[2]。二次 GET で本文埋め無し。"
        "ranking: score>0 優先 → [:return_limit]。"
        "Agent: result を json.dumps して messages へ handoff。stdout summarize は表示専用。"
    )

    raw_preview = ""
    if trace.get("raw_api"):
        raw_preview = trunc(
            {
                k: {
                    "http_status": (v or {}).get("http_status"),
                    "raw_count": (v or {}).get("raw_count"),
                    "snippet_nonempty": (v or {}).get("snippet_nonempty"),
                    "snippet_empty": (v or {}).get("snippet_empty"),
                    "items_preview": ((v or {}).get("items") or [])[:2],
                }
                for k, v in (trace.get("raw_api") or {}).items()
                if isinstance(v, dict)
            },
            1200,
        )

    material_gaps: list[str] = []
    if not trace and not row:
        material_gaps.append("trace/stage_trace 欠落")
    if not cap:
        material_gaps.append("capability_route 欠落")

    materials = {
        "problem_summary": mask_text(
            f"実ログ診断ケース {case_id}: {request}。"
            f"search_web 品質/経路の確認（Shadow Mode。実行・修正なし）。"
        ),
        "code_excerpt": code_excerpt,
        "runtime_log": mask_text("\n".join(runtime_parts)),
        "raw_api_digest": raw_preview or "なし",
        "state_context": "State/Evidence 変更要求はない（本ケースは search_web 品質観測）。",
        "prior_analysis": "人間既知原因は本 Cohort では提示しない（R）。",
        "case_trace_row": trunc(row, 600) if row else "なし",
        "material_gaps": material_gaps or [],
    }

    return {
        "case_id": f"{cohort}_{case_id}",
        "source_case_id": case_id,
        "cohort": cohort,
        "scenario": "nh12_real_shadow_expansion",
        "types": types,
        "shadow_mode": True,
        "production_side_effects": "NONE",
        "auto_fix_allowed": False,
        "materials": materials,
        "human_known_cause": None,
        "sources": {
            "trace": str(TRACE / "examples" / case_id / "trace.json"),
            "caproute": str(caproute_path(case_id, source)),
            "case_trace_csv": str(TRACE / "case_trace.csv"),
            "source_kind": source,
        },
    }


def build_selected_cases() -> list[dict[str, Any]]:
    return [pack_case(spec) for spec in NH12_SELECTED]
