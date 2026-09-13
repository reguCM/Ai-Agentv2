"""Recovery Strategy 変換（A～E）。"""
from __future__ import annotations

import copy
import json
from typing import Any

from tools.file.workspace.search_files import search_files
from tools.system.context_monitor.recovery import get_configured_context, next_context_step
from tools.system.context_monitor.recovery_harness import (
    EXPECTED_TOOL,
    _WIDE_USER,
    build_fixed_payload_messages,
)

STRATEGY_RETRY_SAME = "retry_same_context"
STRATEGY_REDUCE_RESULT = "reduce_tool_result"
STRATEGY_NARROW_SCOPE = "narrow_search_scope"
STRATEGY_INCREASE_CTX = "increase_context"
STRATEGY_EXPLICIT_INSTR = "retry_with_explicit_tool_instruction"

COMPARE_STRATEGIES = (
    STRATEGY_RETRY_SAME,
    STRATEGY_REDUCE_RESULT,
    STRATEGY_NARROW_SCOPE,
    STRATEGY_INCREASE_CTX,
    STRATEGY_EXPLICIT_INSTR,
)


def reduce_search_payload(
    payload: dict[str, Any],
    *,
    max_matches: int = 10,
) -> dict[str, Any]:
    """Strategy B: Tool Result を削減。"""
    reduced = copy.deepcopy(payload)
    original_count = payload.get("match_count") or len(payload.get("matches") or [])
    matches = list(payload.get("matches") or [])[:max_matches]
    reduced["matches"] = matches
    reduced["match_count"] = len(matches)
    reduced["truncated"] = original_count > len(matches) or bool(payload.get("truncated"))
    reduced["recovery_strategy"] = STRATEGY_REDUCE_RESULT
    reduced["recovery_meta"] = {
        "original_match_count": original_count,
        "reduced_to": len(matches),
        "max_matches": max_matches,
    }
    return reduced


def narrow_search_payload(
    query: str = "read_file",
    *,
    search_paths: list[str] | None = None,
) -> tuple[dict[str, Any], str]:
    """Strategy C: 検索範囲を狭める。最も件数が少ない path を選ぶ。"""
    paths = search_paths or ["registry", "tools/system", "tools/system/gpu"]
    best: dict[str, Any] | None = None
    best_path = paths[0]
    best_count = 10**9
    attempts: list[dict[str, Any]] = []

    for path in paths:
        result = search_files(query, path=path)
        if isinstance(result, dict) and result.get("ok") is not False:
            count = int(result.get("match_count") or 0)
            attempts.append({"path": path, "match_count": count, "truncated": result.get("truncated")})
            if count < best_count:
                best = result
                best_path = path
                best_count = count

    if best is None:
        best = search_files(query, path="registry")
        best_path = "registry"

    enriched = copy.deepcopy(best)
    enriched["recovery_strategy"] = STRATEGY_NARROW_SCOPE
    enriched["recovery_meta"] = {"selected_path": best_path, "attempts": attempts}
    return enriched, best_path


def payload_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "result_count": payload.get("match_count"),
        "payload_bytes": len(text.encode("utf-8")),
        "truncated": payload.get("truncated"),
        "search_base": payload.get("base"),
    }


def apply_strategy(
    strategy: str,
    *,
    search_payload: dict[str, Any],
    configured_context: int,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Strategy を適用し messages / meta / runtime_context / strategy_params を返す。
    """
    if policy is None:
        from tools.system.context_monitor.recovery import load_recovery_policy

        policy = load_recovery_policy()
    params = (policy.get("strategy_params") or {}).get(strategy) or {}
    runtime_context = configured_context
    payload = search_payload
    extra_user: str | None = None
    strategy_params: dict[str, Any] = {"strategy": strategy}

    if strategy == STRATEGY_RETRY_SAME:
        strategy_params["note"] = "same messages and context"

    elif strategy == STRATEGY_REDUCE_RESULT:
        max_m = int(params.get("max_matches") or 10)
        payload = reduce_search_payload(search_payload, max_matches=max_m)
        strategy_params["max_matches"] = max_m
        strategy_params.update(payload.get("recovery_meta") or {})

    elif strategy == STRATEGY_NARROW_SCOPE:
        paths = params.get("search_paths") or ["registry", "tools/system", "tools/system/gpu"]
        query = params.get("query") or "read_file"
        payload, selected = narrow_search_payload(query, search_paths=list(paths))
        strategy_params["selected_path"] = selected
        strategy_params.update(payload.get("recovery_meta") or {})

    elif strategy == STRATEGY_INCREASE_CTX:
        candidate = next_context_step(configured_context, policy)
        if candidate is None:
            raise ValueError("no higher context in ladder")
        runtime_context = int(candidate)
        strategy_params["candidate_context"] = runtime_context

    elif strategy == STRATEGY_EXPLICIT_INSTR:
        extra_user = str(
            params.get("instruction")
            or "Native Tool Call として read_file を呼び出してください。"
        )
        strategy_params["instruction_added"] = True

    else:
        raise ValueError(f"unknown strategy: {strategy}")

    messages, meta = build_fixed_payload_messages(payload)
    if extra_user:
        messages = list(messages) + [{"role": "user", "content": extra_user}]

    strategy_params.update(payload_metrics(payload))
    return {
        "strategy": strategy,
        "messages": messages,
        "meta": meta,
        "runtime_context": runtime_context,
        "configured_context": configured_context,
        "strategy_params": strategy_params,
        "search_payload": payload,
        "user_request": _WIDE_USER,
        "expected_tool": EXPECTED_TOOL,
    }
