"""
PROJECT_AGENT capability_route 観測（実行権限・ルーティングではない）。

目的:
- Agent が「既存公開Toolで継続 / 新規Tool必要 / 判断不能」と見なしたかを記録する
- Web検索の「判断」と「実際の実行・結果」を分けて残し、後から比較できるようにする
- Web実行前の回答候補（pre_web_answer_candidate）を同一 observation_id で残し、
  最終回答との品質差を後から人間が比較できるようにする
- Stage 2: 判断→実行→回答表面結果を同一 observation_id で比較記録する

禁止（本モジュールは行わない）:
- RESEARCH_PIPELINE 起動
- handoff / register / Tool 実行許可
- agent_tool_gate / Research Safety の変更・迂回
- Clarity status の変更
- Web の許可・Gate・Pipeline ルートへの接続
- 「Webあり／なしのどちらが正しいか」「Web検索が有益だったか」の自動判定
- Stage 3 誤判定の確定分類 / Stage 4 判定方式の自動改善
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.system.execution_identity import (
    PROJECT_AGENT,
    digest_result,
    record_event,
)

ROUTE_AGENT_CONTINUE = "agent_continue"
ROUTE_NEEDS_NEW_TOOL = "needs_new_tool"
ROUTE_UNCERTAIN = "uncertain"

VALID_ROUTES = frozenset(
    {ROUTE_AGENT_CONTINUE, ROUTE_NEEDS_NEW_TOOL, ROUTE_UNCERTAIN}
)

_NEW_TOOL_HINTS = (
    "新しいtool",
    "新規tool",
    "toolを作",
    "tool作成",
    "toolを追加",
    "機能追加",
    "プログラム作成",
    "実装して",
    "registryに",
    "create_tool",
)

_WEB_HINTS = (
    "web",
    "ウェブ",
    "検索",
    "調べ",
    "検索して",
    "ネット",
    "インターネット",
    "最新",
    "現在",
    "ニュース",
    "情報源",
    "url",
    "http",
)

_DEFAULT_OBS_REL = Path("logs") / "capability_route.jsonl"

# 観測ログ用の本文上限（人間比較用。正誤判定には使わない）
_PRE_WEB_CONTENT_MAX = 8000
_HIT_DIGEST_MAX = 5
_HIT_TITLE_MAX = 120
_HIT_URL_MAX = 200
_HIT_SNIPPET_MAX = 160


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip_text(value: Any, max_len: int) -> tuple[str, bool]:
    text = str(value or "")
    if len(text) <= max_len:
        return text, False
    return text[:max_len], True


def observation_log_path() -> Path:
    raw = (os.environ.get("AI_AGENT_CAPABILITY_ROUTE_LOG") or "").strip()
    if raw:
        return Path(raw)
    return _repo_root() / _DEFAULT_OBS_REL


def new_observation_id() -> str:
    return f"caproute-{uuid.uuid4().hex[:12]}"


def list_agent_public_tool_names(registry: dict | None) -> list[str]:
    names = []
    for tool in (registry or {}).get("tools") or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("visibility") != "agent":
            continue
        name = str(tool.get("name") or "").strip()
        if name:
            names.append(name)
    return sorted(set(names))


def related_tool_names(related_tools: list | None) -> list[str]:
    names = []
    for item in related_tools or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            names.append(name)
    return names


def _norm_request(request: str) -> str:
    return str(request or "").strip().lower()


def _request_hints_new_tool(request: str) -> bool:
    text = _norm_request(request)
    return any(h in text for h in _NEW_TOOL_HINTS)


def _request_hints_web(request: str) -> bool:
    text = _norm_request(request)
    if any(h in text for h in _WEB_HINTS):
        return True
    # 英単語境界ざっくり
    return bool(re.search(r"\b(search|web|google|bing)\b", text))


def classify_search_web_outcome(result: Any) -> str:
    """
    実行結果の分類（判断ではない）。
    blocked / empty_hits / hits / error / other
    """
    if not isinstance(result, dict):
        return "other"
    if result.get("blocked_by_agent_tool_gate"):
        return "blocked"
    if result.get("error"):
        return "error"
    hits = result.get("hits")
    if isinstance(hits, list):
        if len(hits) == 0:
            return "empty_hits"
        return "hits"
    return "other"


def digest_search_web_hits(result: Any) -> list[dict[str, Any]]:
    """
    search_web 結果のヒット要約のみ。最終回答ではない。
    """
    if not isinstance(result, dict):
        return []
    hits = result.get("hits")
    if not isinstance(hits, list):
        return []
    out: list[dict[str, Any]] = []
    for hit in hits[:_HIT_DIGEST_MAX]:
        if not isinstance(hit, dict):
            continue
        title, _ = _clip_text(hit.get("title"), _HIT_TITLE_MAX)
        url, _ = _clip_text(hit.get("url"), _HIT_URL_MAX)
        snippet_src = hit.get("snippet") or hit.get("description") or ""
        snippet, _ = _clip_text(snippet_src, _HIT_SNIPPET_MAX)
        out.append({"title": title, "url": url, "snippet": snippet})
    return out


def build_tool_trial(
    tool_name: str,
    arguments: Any = None,
    result: Any = None,
) -> dict[str, Any]:
    name = str(tool_name or "").strip()
    trial: dict[str, Any] = {
        "tool_name": name,
        "arguments_digest": digest_result(arguments if arguments is not None else {}),
        "blocked_by_agent_tool_gate": bool(
            isinstance(result, dict) and result.get("blocked_by_agent_tool_gate")
        ),
    }
    if name == "search_web":
        trial["search_web_outcome"] = classify_search_web_outcome(result)
        if isinstance(result, dict):
            hits = result.get("hits")
            trial["hit_count"] = len(hits) if isinstance(hits, list) else None
            trial["error"] = result.get("error")
            trial["hit_digest"] = digest_search_web_hits(result)
            trial["query"] = str(result.get("query") or "")[:200] or None
            ws = result.get("web_status")
            if isinstance(ws, dict):
                trial["web_status_overall"] = ws.get("overall")
                trial["web_status_failure_cause"] = ws.get("failure_cause")
    else:
        if isinstance(result, dict) and result.get("ok") is False:
            trial["ok"] = False
        elif isinstance(result, dict) and "ok" in result:
            trial["ok"] = bool(result.get("ok"))
        else:
            trial["ok"] = None
        if name == "read_url_text" and isinstance(result, dict):
            ws = result.get("web_status")
            if isinstance(ws, dict):
                trial["web_status_overall"] = ws.get("overall")
                trial["web_status_failure_cause"] = ws.get("failure_cause")
    return trial


def build_web_search_results_digest(trials: list[dict] | None) -> dict[str, Any]:
    """
    Web検索Toolの生結果ダイジェスト。最終回答（final_answer）とは別物。
    有益判定は行わない。
    """
    calls = [
        t
        for t in (trials or [])
        if isinstance(t, dict) and t.get("tool_name") == "search_web"
    ]
    call_rows: list[dict[str, Any]] = []
    for trial in calls:
        call_rows.append(
            {
                "outcome": trial.get("search_web_outcome"),
                "hit_count": trial.get("hit_count"),
                "error": trial.get("error"),
                "query": trial.get("query"),
                "hit_digest": list(trial.get("hit_digest") or []),
                "blocked_by_agent_tool_gate": bool(
                    trial.get("blocked_by_agent_tool_gate")
                ),
            }
        )
    return {
        "called": bool(calls),
        "call_count": len(calls),
        "outcomes": [c.get("outcome") for c in call_rows if c.get("outcome")],
        "calls": call_rows,
        "not_final_answer": True,
        "observation_only": True,
        "note": (
            "Raw search_web result digests only. Distinct from final_answer. "
            "No automatic judgment of web usefulness or correctness."
        ),
    }


def heuristic_capability_route(
    *,
    request: str,
    related_tools: list | None,
    agent_public_tools: list[str] | None,
) -> dict[str, Any]:
    """
    観測用ヒューリスティック。実行権限を与えない。
    Registry visibility=agent と related_tools・要求文言のみ。
    """
    public = list(agent_public_tools or [])
    related = related_tool_names(related_tools)
    related_public = [n for n in related if n in set(public)]
    wants_new = _request_hints_new_tool(request)
    reasons: list[str] = []

    if wants_new and not related_public:
        route = ROUTE_NEEDS_NEW_TOOL
        reasons.append("request_hints_new_tool")
        reasons.append("no_related_agent_public_tools")
        confidence = "low"
    elif wants_new and related_public:
        route = ROUTE_UNCERTAIN
        reasons.append("request_hints_new_tool")
        reasons.append("related_agent_public_tools_present")
        confidence = "low"
    elif related_public:
        route = ROUTE_AGENT_CONTINUE
        reasons.append("related_agent_public_tools_present")
        confidence = "low"
    elif public:
        route = ROUTE_UNCERTAIN
        reasons.append("agent_public_tools_exist_but_no_related_match")
        confidence = "low"
    else:
        route = ROUTE_UNCERTAIN
        reasons.append("no_agent_public_tools")
        confidence = "low"

    return {
        "route": route,
        "reason": "; ".join(reasons),
        "confidence": confidence,
        "method": "heuristic_v1",
        "observation_only": True,
        "related_public_tool_names": related_public,
    }


def heuristic_web_search_judgment(
    *,
    request: str,
    related_tools: list | None,
    agent_public_tools: list[str] | None,
) -> dict[str, Any]:
    """Web検索が適切そうか／候補として認識したか（実行前・実行事実とは別）。"""
    public = set(agent_public_tools or [])
    related = related_tool_names(related_tools)
    recognized = "search_web" in public
    in_related = "search_web" in related
    judged = _request_hints_web(request) or in_related
    reasons = []
    if _request_hints_web(request):
        reasons.append("request_hints_web")
    if in_related:
        reasons.append("search_web_in_related_tools")
    if recognized:
        reasons.append("search_web_is_agent_public")
    else:
        reasons.append("search_web_not_agent_public")
    return {
        "judged_appropriate": bool(judged),
        "recognized_as_candidate": bool(recognized),
        "in_related_tools": bool(in_related),
        "reason": "; ".join(reasons) if reasons else "none",
        "observation_only": True,
    }


def build_web_search_execution_summary(trials: list[dict] | None) -> dict[str, Any]:
    calls = [
        t
        for t in (trials or [])
        if isinstance(t, dict) and t.get("tool_name") == "search_web"
    ]
    outcomes = [t.get("search_web_outcome") for t in calls if t.get("search_web_outcome")]
    return {
        "called": bool(calls),
        "call_count": len(calls),
        "outcomes": outcomes,
        "note": "execution facts only; not a capability judgment",
    }


def build_capability_route_observation(
    *,
    request: str,
    registry: dict | None,
    related_tools: list | None = None,
    agent_tools_tried: list | None = None,
    observation_id: str | None = None,
    entrypoint: str = "agent.py",
    extra: dict | None = None,
) -> dict[str, Any]:
    obs_id = observation_id or new_observation_id()
    public = list_agent_public_tool_names(registry)
    related = list(related_tools or [])
    trials = [dict(t) for t in (agent_tools_tried or []) if isinstance(t, dict)]

    route_j = heuristic_capability_route(
        request=request,
        related_tools=related,
        agent_public_tools=public,
    )
    web_j = heuristic_web_search_judgment(
        request=request,
        related_tools=related,
        agent_public_tools=public,
    )
    web_exec = build_web_search_execution_summary(trials)

    payload: dict[str, Any] = {
        "kind": "capability_route_observation",
        "observation_only": True,
        "does_not_grant_tool_execution": True,
        "does_not_start_pipeline": True,
        "does_not_bypass_agent_tool_gate": True,
        "observation_id": obs_id,
        "ts": _now_iso(),
        "execution_actor": PROJECT_AGENT,
        "entrypoint": entrypoint,
        "request": str(request or ""),
        "capability_route": {
            "route": route_j["route"],
            "reason": route_j["reason"],
            "confidence": route_j.get("confidence"),
            "method": route_j.get("method"),
            "observation_only": True,
        },
        "related_tools": [
            {
                "name": item.get("name"),
                "score": item.get("score"),
                "category": item.get("category"),
                "subcategory": item.get("subcategory"),
            }
            if isinstance(item, dict)
            else {"name": str(item)}
            for item in related
        ],
        "agent_public_tools": public,
        "agent_tools_tried": trials,
        "web_search": {
            "judgment": web_j,
            "execution": web_exec,
            "comparison_note": (
                "Compare judgment.judged_appropriate / recognized_as_candidate "
                "with execution.called / outcomes. Do not treat judgment as execution."
            ),
        },
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def append_observation_file(payload: dict, path: Path | None = None) -> Path:
    target = path or observation_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, default=str)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return target


def record_capability_route_observation(payload: dict) -> dict[str, Any]:
    """
    JSONL（capability_route）と execution_identity の両方へ観測イベントを残す。
    実行・Pipeline・Gate には影響しない。
    """
    path = append_observation_file(payload)
    record_event(
        {
            "event": "capability_route_observed",
            "execution_actor": PROJECT_AGENT,
            "entrypoint": payload.get("entrypoint") or "agent.py",
            "observation_id": payload.get("observation_id"),
            "capability_route": (payload.get("capability_route") or {}).get("route"),
            "capability_route_reason": (payload.get("capability_route") or {}).get(
                "reason"
            ),
            "web_search_judgment_appropriate": (
                (payload.get("web_search") or {}).get("judgment") or {}
            ).get("judged_appropriate"),
            "web_search_called": (
                (payload.get("web_search") or {}).get("execution") or {}
            ).get("called"),
            "observation_only": True,
            "capability_route_log": str(path),
        }
    )
    return {"ok": True, "path": str(path), "observation_id": payload.get("observation_id")}


# ---------------------------------------------------------------------------
# pre_web_answer_candidate: Web実行前（または未実行時）の回答候補観測
# Gate / Pipeline / Web許可には接続しない。有益性の自動判定もしない。
# ---------------------------------------------------------------------------


def build_pre_web_answer_candidate(
    *,
    request: str,
    content: Any,
    observation_id: str | None = None,
    entrypoint: str = "agent.py",
    generation_error: str | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    """
    PROJECT_AGENT が Web 検索結果なしで生成しうる回答候補の観測レコード。
    Web 未実行時も同一スキーマで記録する。正誤・有益性は判定しない。
    """
    obs_id = observation_id or new_observation_id()
    raw = "" if content is None else str(content)
    clipped, truncated = _clip_text(raw, _PRE_WEB_CONTENT_MAX)
    surface = classify_final_answer_surface(clipped)
    payload: dict[str, Any] = {
        "kind": "pre_web_answer_candidate",
        "observation_only": True,
        "does_not_grant_tool_execution": True,
        "does_not_start_pipeline": True,
        "does_not_bypass_agent_tool_gate": True,
        "does_not_authorize_web_search": True,
        "not_web_usefulness_judgment": True,
        "not_stage3_misjudgment": True,
        "not_stage4_method_change": True,
        "observation_id": obs_id,
        "ts": _now_iso(),
        "execution_actor": PROJECT_AGENT,
        "entrypoint": entrypoint,
        "request": str(request or ""),
        "pre_web_answer_candidate": {
            "content": clipped,
            "content_truncated": truncated,
            "char_count": len(raw),
            "surface": surface,
            "web_search_not_used": True,
            "generation_error": generation_error,
            "note": (
                "Answer candidate without web search results. "
                "For human before/after comparison only. "
                "Not a judgment of whether web search is needed or beneficial."
            ),
        },
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def record_pre_web_answer_candidate(payload: dict) -> dict[str, Any]:
    """pre_web_answer_candidate を JSONL + identity に残す。権限非接続。"""
    path = append_observation_file(payload)
    candidate = payload.get("pre_web_answer_candidate") or {}
    surface = candidate.get("surface") or {}
    record_event(
        {
            "event": "pre_web_answer_candidate_observed",
            "execution_actor": PROJECT_AGENT,
            "entrypoint": payload.get("entrypoint") or "agent.py",
            "observation_id": payload.get("observation_id"),
            "char_count": candidate.get("char_count"),
            "surface_status": surface.get("status"),
            "generation_error": bool(candidate.get("generation_error")),
            "observation_only": True,
            "does_not_authorize_web_search": True,
            "not_web_usefulness_judgment": True,
            "capability_route_log": str(path),
        }
    )
    return {"ok": True, "path": str(path), "observation_id": payload.get("observation_id")}


# ---------------------------------------------------------------------------
# Stage 2: 観測（判断・実行）と最終回答の表面結果を比較記録する
# Stage 3（誤判定分類）・Stage 4（判定方式改善）はまだ行わない
# ---------------------------------------------------------------------------

ANSWER_EMPTY = "empty"
ANSWER_DECLINED_UNCONFIRMED = "declined_unconfirmed"
ANSWER_PRESENT = "present"

OUTCOME_SUCCESS_CANDIDATE = "success_candidate"
OUTCOME_FAILURE_CANDIDATE = "failure_candidate"
OUTCOME_INCONCLUSIVE = "inconclusive"

_ANSWER_DECLINE_MARKERS = (
    "確認できなかった",
    "確認できませんでした",
    "未確認",
    "わかりません",
    "分かりません",
    "不明です",
    "取得できませんでした",
    "見つかりませんでした",
    "情報を得られませんでした",
)


def classify_final_answer_surface(content: Any) -> dict[str, Any]:
    """
    最終回答の表面分類のみ。真の正誤・構想§15の成功確定ではない。
    Stage 2 の比較材料。Gate/権限には使わない。
    """
    text = str(content or "").strip()
    signals: list[str] = []
    if not text:
        return {
            "status": ANSWER_EMPTY,
            "outcome_proxy": OUTCOME_FAILURE_CANDIDATE,
            "signals": ["empty_content"],
            "char_count": 0,
            "observation_only": True,
            "not_ground_truth": True,
        }
    signals.append("non_empty_content")
    lowered = text.lower()
    declined = any(m in text for m in _ANSWER_DECLINE_MARKERS) or any(
        m in lowered for m in ("i don't know", "cannot confirm", "unable to confirm")
    )
    if declined:
        signals.append("decline_or_unconfirmed_marker")
        return {
            "status": ANSWER_DECLINED_UNCONFIRMED,
            "outcome_proxy": OUTCOME_INCONCLUSIVE,
            "signals": signals,
            "char_count": len(text),
            "observation_only": True,
            "not_ground_truth": True,
        }
    return {
        "status": ANSWER_PRESENT,
        "outcome_proxy": OUTCOME_SUCCESS_CANDIDATE,
        "signals": signals,
        "char_count": len(text),
        "observation_only": True,
        "not_ground_truth": True,
    }


def _primary_web_outcome(outcomes: list | None) -> str | None:
    items = [str(x) for x in (outcomes or []) if x]
    if not items:
        return None
    for preferred in ("error", "blocked", "empty_hits", "hits", "other"):
        if preferred in items:
            return preferred
    return items[-1]


def derive_web_compare_pattern(
    *,
    judged_appropriate: bool | None,
    called: bool,
    primary_outcome: str | None,
    answer_status: str,
    answer_outcome_proxy: str,
) -> str:
    """
    後集計用の短いパターン名。Stage 3 の誤判定ラベルではない。
    """
    judged = bool(judged_appropriate)
    if not judged:
        if called:
            return "web_not_judged_but_called"
        return "web_not_judged_not_called"

    if not called:
        if answer_status == ANSWER_EMPTY:
            return "web_judged_not_called_answer_empty"
        if answer_outcome_proxy == OUTCOME_SUCCESS_CANDIDATE:
            return "web_judged_not_called_answer_present"
        return "web_judged_not_called_answer_other"

    outcome = primary_outcome or "unknown"
    if outcome == "hits":
        if answer_outcome_proxy == OUTCOME_SUCCESS_CANDIDATE:
            return "web_judged_called_hits_answer_success_candidate"
        if answer_status == ANSWER_EMPTY:
            return "web_judged_called_hits_answer_empty"
        if answer_status == ANSWER_DECLINED_UNCONFIRMED:
            return "web_judged_called_hits_answer_declined"
        return "web_judged_called_hits_answer_other"

    if outcome == "empty_hits":
        if answer_outcome_proxy == OUTCOME_SUCCESS_CANDIDATE:
            return "web_judged_called_empty_hits_answer_success_candidate"
        if answer_status == ANSWER_EMPTY or answer_outcome_proxy == OUTCOME_FAILURE_CANDIDATE:
            return "web_judged_called_empty_hits_answer_failure_candidate"
        if answer_status == ANSWER_DECLINED_UNCONFIRMED:
            return "web_judged_called_empty_hits_answer_declined"
        return "web_judged_called_empty_hits_answer_other"

    if outcome in ("error", "blocked"):
        return f"web_judged_called_{outcome}_answer_{answer_status}"

    return f"web_judged_called_{outcome}_answer_{answer_status}"


def build_capability_outcome_compare(
    *,
    capability_observation: dict | None,
    final_answer_content: Any,
    observation_id: str | None = None,
    entrypoint: str = "agent.py",
    extra: dict | None = None,
    pre_web_answer_candidate: dict | None = None,
    web_search_results: dict | None = None,
) -> dict[str, Any]:
    """
    Stage 2: 同一 observation_id で「判断 → 実行 → 回答表面結果」を比較記録する。
    pre_web_answer_candidate / web_search_results を同梱し、最終回答と区別する。
    誤判定分類（Stage 3）や判定改善（Stage 4）は行わない。
    Web 有益性の自動判定も行わない。
    """
    base = capability_observation or {}
    obs_id = (
        observation_id
        or base.get("observation_id")
        or new_observation_id()
    )
    web = base.get("web_search") or {}
    judgment = web.get("judgment") or {}
    execution = web.get("execution") or {}
    answer = classify_final_answer_surface(final_answer_content)
    judged = judgment.get("judged_appropriate")
    called = bool(execution.get("called"))
    outcomes = list(execution.get("outcomes") or [])
    primary = _primary_web_outcome(outcomes)
    pattern = derive_web_compare_pattern(
        judged_appropriate=judged,
        called=called,
        primary_outcome=primary,
        answer_status=str(answer.get("status")),
        answer_outcome_proxy=str(answer.get("outcome_proxy")),
    )

    pre_web_block = None
    if isinstance(pre_web_answer_candidate, dict):
        # 専用イベント全文でも、候補サブオブジェクトでも受け付ける
        if "pre_web_answer_candidate" in pre_web_answer_candidate and isinstance(
            pre_web_answer_candidate.get("pre_web_answer_candidate"), dict
        ):
            pre_web_block = dict(pre_web_answer_candidate["pre_web_answer_candidate"])
        elif "content" in pre_web_answer_candidate or "surface" in pre_web_answer_candidate:
            pre_web_block = dict(pre_web_answer_candidate)

    results_block = web_search_results
    if results_block is None:
        results_block = build_web_search_results_digest(base.get("agent_tools_tried"))

    chain = {
        "pre_web_answer_candidate": pre_web_block,
        "web_judgment": {
            "judged_appropriate": judged,
            "recognized_as_candidate": judgment.get("recognized_as_candidate"),
            "reason": judgment.get("reason"),
        },
        "web_execution": {
            "called": called,
            "call_count": execution.get("call_count"),
            "outcomes": outcomes,
            "primary_outcome": primary,
        },
        # 検索結果そのもの（最終回答ではない）
        "web_search_results": results_block,
        "final_answer": answer,
    }

    payload: dict[str, Any] = {
        "kind": "capability_outcome_compare",
        "stage": 2,
        "observation_only": True,
        "does_not_grant_tool_execution": True,
        "does_not_start_pipeline": True,
        "does_not_bypass_agent_tool_gate": True,
        "not_web_usefulness_judgment": True,
        "not_stage3_misjudgment": True,
        "not_stage4_method_change": True,
        "observation_id": obs_id,
        "ts": _now_iso(),
        "execution_actor": PROJECT_AGENT,
        "entrypoint": entrypoint,
        "request": base.get("request"),
        "capability_route": base.get("capability_route"),
        "chain": chain,
        "compare_summary": {
            "web_pattern": pattern,
            "route": (base.get("capability_route") or {}).get("route"),
            "answer_outcome_proxy": answer.get("outcome_proxy"),
            "pre_web_surface_status": (pre_web_block or {}).get("surface", {}).get(
                "status"
            )
            if isinstance(pre_web_block, dict)
            else None,
            "web_search_called": called,
            "note": (
                "Surface comparison only. success_candidate/failure_candidate "
                "are not ground-truth task success. "
                "pre_web_answer_candidate vs final_answer is for human review; "
                "web usefulness is not auto-judged. "
                "Stage 3 misjudgment labels are not assigned here."
            ),
        },
        # Stage 3 用スロット（今回は埋めない）
        "misjudgment_classification": None,
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def record_capability_outcome_compare(payload: dict) -> dict[str, Any]:
    """Stage 2 比較結果を JSONL + execution_identity に残す。権限・Pipeline 非接続。"""
    path = append_observation_file(payload)
    summary = payload.get("compare_summary") or {}
    chain = payload.get("chain") or {}
    web_exec = chain.get("web_execution") or {}
    answer = chain.get("final_answer") or {}
    pre_web = chain.get("pre_web_answer_candidate") or {}
    record_event(
        {
            "event": "capability_outcome_compared",
            "execution_actor": PROJECT_AGENT,
            "entrypoint": payload.get("entrypoint") or "agent.py",
            "observation_id": payload.get("observation_id"),
            "stage": 2,
            "web_pattern": summary.get("web_pattern"),
            "route": summary.get("route"),
            "web_called": web_exec.get("called"),
            "web_primary_outcome": web_exec.get("primary_outcome"),
            "answer_status": answer.get("status"),
            "answer_outcome_proxy": answer.get("outcome_proxy"),
            "pre_web_surface_status": (pre_web.get("surface") or {}).get("status")
            if isinstance(pre_web, dict)
            else None,
            "observation_only": True,
            "not_web_usefulness_judgment": True,
            "not_stage3_misjudgment": True,
            "capability_route_log": str(path),
        }
    )
    return {"ok": True, "path": str(path), "observation_id": payload.get("observation_id")}
