#!/usr/bin/env python3
"""Help System H1 — discover / understand / select (no tool execution).

Uses Baseline AgentToolDiscoveryAdapter via sys.path. Does not copy Baseline.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

GOAL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]  # ai_tool/help -> repo root
DEFAULT_BASELINE = REPO_ROOT  # in-repo: discovery uses this checkout

USAGE = """Help System (/h) usage:
  /h                  Overview of Help System
  /h <query>          Search tools (case-insensitive)
  /h tool <tool_id>   Describe one tool (schemas, risk, availability, side_effect)
  /h help             Show this usage

Notes:
  - Outputs structured HelpResult only; never executes tools.
  - Distinct from HELP Packet (upper-AI escalation), which is out of scope.
"""

OVERVIEW = """Help System H1 — discover → understand → select

Audiences: agent (API) and human (/h commands).
Operations: list, search(query), describe(tool_id), parse_h(command), handle_h(command).
Discovery: Baseline AgentToolDiscoveryAdapter (read-only metadata).
Not HELP Packet: this is local tool help, not escalation-to-upper-AI.

""" + USAGE


def ensure_baseline_on_path() -> Path:
    """Put Baseline root on sys.path so ai_tool.* imports resolve."""
    env = os.environ.get("HELP_SYSTEM_BASELINE", "").strip()
    baseline = Path(env) if env else DEFAULT_BASELINE
    baseline = baseline.resolve()
    if not baseline.is_dir():
        raise FileNotFoundError(
            f"Repo/baseline not found: {baseline}. "
            "Set HELP_SYSTEM_BASELINE or run inside AI-Agent worktree."
        )
    # Prefer Baseline's ai_tool package
    bstr = str(baseline)
    if bstr in sys.path:
        sys.path.remove(bstr)
    sys.path.insert(0, bstr)
    return baseline


def _get_adapter():
    ensure_baseline_on_path()
    from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter

    return AgentToolDiscoveryAdapter()


def _empty_result(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ok": True,
        "operation": "list",
        "query": None,
        "tool_id": None,
        "parsed": None,
        "tools": [],
        "tool": None,
        "count": 0,
        "usage": None,
        "message": "",
        "error": None,
    }
    base.update(overrides)
    return base


def _summary_card(t: Any) -> dict[str, Any]:
    return {
        "tool_id": t.tool_id,
        "name": t.name,
        "description": t.description or "",
        "capabilities": list(t.capabilities or []),
        "risk_level": t.risk_level,
        "availability": t.availability,
        "side_effect": t.side_effect,
        "discovery_category": t.discovery_category,
        "agent_available": bool(t.agent_available),
    }


def _full_card(t: Any) -> dict[str, Any]:
    card = _summary_card(t)
    catalog = t.catalog_status
    if hasattr(catalog, "to_dict"):
        catalog_status = catalog.to_dict()
    elif isinstance(catalog, dict):
        catalog_status = catalog
    else:
        catalog_status = {
            "tool_status": getattr(catalog, "tool_status", None),
            "experiment_status": getattr(catalog, "experiment_status", None),
            "adoption_status": getattr(catalog, "adoption_status", None),
        }
    card.update(
        {
            "provider": t.provider,
            "source": t.source,
            "input_schema": dict(t.input_schema or {}),
            "output_schema": t.output_schema,
            "permissions": list(t.permissions or []),
            "unavailability_reason": t.unavailability_reason,
            "catalog_status": catalog_status,
        }
    )
    return card


def _match_query(t: Any, query: str) -> bool:
    q = (query or "").casefold()
    if not q:
        return False
    haystacks: list[str] = [
        str(t.tool_id or ""),
        str(t.name or ""),
        str(t.description or ""),
    ]
    for cap in t.capabilities or []:
        haystacks.append(str(cap))
    return any(q in h.casefold() for h in haystacks)


def list_tools(*, audit: bool = False) -> dict[str, Any]:
    adapter = _get_adapter()
    result = adapter.discover_tools(audit=audit)
    tools = [_summary_card(t) for t in result.tools]
    return _empty_result(
        ok=True,
        operation="list",
        tools=tools,
        count=len(tools),
        message=f"Listed {len(tools)} tool(s)",
    )


def search(query: str, *, audit: bool = False) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return _empty_result(
            ok=False,
            operation="search",
            query=q,
            error="search requires a non-empty query",
            message="search failed: empty query",
        )
    adapter = _get_adapter()
    result = adapter.discover_tools(audit=audit)
    matched = [_summary_card(t) for t in result.tools if _match_query(t, q)]
    return _empty_result(
        ok=True,
        operation="search",
        query=q,
        tools=matched,
        count=len(matched),
        message=f"Search {q!r}: {len(matched)} match(es)",
    )


def describe(tool_id: str, *, audit: bool = False) -> dict[str, Any]:
    tid = (tool_id or "").strip()
    if not tid:
        return _empty_result(
            ok=False,
            operation="describe",
            tool_id=tid,
            error="describe requires tool_id",
            message="describe failed: missing tool_id",
        )
    adapter = _get_adapter()
    # Prefer get_tool_descriptor; fall back to scan if needed
    tool = adapter.get_tool_descriptor(tid)
    if tool is None:
        return _empty_result(
            ok=False,
            operation="describe",
            tool_id=tid,
            error=f"tool not found: {tid}",
            message=f"describe failed: {tid} not found",
        )
    card = _full_card(tool)
    return _empty_result(
        ok=True,
        operation="describe",
        tool_id=tid,
        tool=card,
        count=0,
        message=f"Described {tid}",
    )


def parse_h(command: str) -> dict[str, Any]:
    """Parse /h grammar. Does not call discovery."""
    raw = command if command is not None else ""
    text = raw.strip()
    parsed: dict[str, Any] = {
        "kind": "invalid",
        "query": None,
        "tool_id": None,
        "raw": raw,
        "error": None,
    }

    if not text.startswith("/h"):
        parsed["error"] = "command must start with /h"
        return _empty_result(
            ok=False,
            operation="parse_h",
            parsed=parsed,
            error=parsed["error"],
            message="parse_h: invalid prefix",
        )

    rest = text[2:].strip()  # after /h
    if rest == "":
        parsed["kind"] = "overview"
        return _empty_result(
            ok=True,
            operation="parse_h",
            parsed=parsed,
            message="parse_h: overview",
        )

    if rest.casefold() == "help":
        parsed["kind"] = "help"
        return _empty_result(
            ok=True,
            operation="parse_h",
            parsed=parsed,
            message="parse_h: help",
        )

    # describe: "tool <tool_id>" (tool keyword case-insensitive)
    lower = rest.casefold()
    if lower == "tool" or lower.startswith("tool "):
        # split once on whitespace after tool
        parts = rest.split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            parsed["kind"] = "invalid"
            parsed["error"] = "missing tool_id after /h tool"
            return _empty_result(
                ok=False,
                operation="parse_h",
                parsed=parsed,
                error=parsed["error"],
                message="parse_h: invalid describe (missing tool_id)",
            )
        tool_id = parts[1].strip()
        parsed["kind"] = "describe"
        parsed["tool_id"] = tool_id
        return _empty_result(
            ok=True,
            operation="parse_h",
            parsed=parsed,
            tool_id=tool_id,
            message=f"parse_h: describe {tool_id}",
        )

    parsed["kind"] = "search"
    parsed["query"] = rest
    return _empty_result(
        ok=True,
        operation="parse_h",
        parsed=parsed,
        query=rest,
        message=f"parse_h: search {rest!r}",
    )


def handle_h(command: str, *, audit: bool = False) -> dict[str, Any]:
    parsed_result = parse_h(command)
    parsed = parsed_result.get("parsed") or {}
    kind = parsed.get("kind")

    if kind == "invalid":
        return _empty_result(
            ok=False,
            operation="invalid",
            parsed=parsed,
            usage=USAGE,
            error=parsed.get("error") or "invalid /h command",
            message=parsed_result.get("message") or "invalid /h",
        )

    if kind == "overview":
        listing = list_tools(audit=audit)
        return _empty_result(
            ok=True,
            operation="overview",
            parsed=parsed,
            tools=listing.get("tools") or [],
            count=listing.get("count") or 0,
            usage=OVERVIEW,
            message=f"overview: {listing.get('count') or 0} tool(s) available",
        )

    if kind == "help":
        return _empty_result(
            ok=True,
            operation="help",
            parsed=parsed,
            usage=USAGE,
            message="help usage",
        )

    if kind == "search":
        q = parsed.get("query") or ""
        out = search(q, audit=audit)
        out["parsed"] = parsed
        return out

    if kind == "describe":
        tid = parsed.get("tool_id") or ""
        out = describe(tid, audit=audit)
        out["parsed"] = parsed
        return out

    return _empty_result(
        ok=False,
        operation="invalid",
        parsed=parsed,
        error=f"unknown kind: {kind}",
        message="handle_h: unknown kind",
    )


def _cli_print(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    op = result.get("operation")
    print(f"ok={result.get('ok')} operation={op} count={result.get('count')}")
    if result.get("message"):
        print(result["message"])
    if result.get("error"):
        print(f"error: {result['error']}")
    if result.get("usage"):
        print(result["usage"])
    if result.get("tool"):
        t = result["tool"]
        print(
            f"tool: {t.get('tool_id')} risk={t.get('risk_level')} "
            f"availability={t.get('availability')} side_effect={t.get('side_effect')}"
        )
        print(f"  name: {t.get('name')}")
        print(f"  desc: {(t.get('description') or '')[:120]}")
    tools = result.get("tools") or []
    if tools and op in ("list", "search", "overview"):
        for t in tools[:30]:
            print(f"- {t.get('tool_id')}: {(t.get('description') or '')[:72]}")
        if len(tools) > 30:
            print(f"... and {len(tools) - 30} more")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Help System H1 CLI (structured HelpResult; no tool execution)"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        help=' /h command string, e.g. "/h gpu" or "/h tool local:read_file"',
    )
    parser.add_argument("--list", action="store_true", help="list all tools")
    parser.add_argument("--search", metavar="QUERY", help="search tools")
    parser.add_argument("--describe", metavar="TOOL_ID", help="describe one tool")
    parser.add_argument("--parse-h", metavar="CMD", dest="parse_h_cmd", help="parse only")
    parser.add_argument("--json", action="store_true", help="print HelpResult JSON")
    args = parser.parse_args(argv)

    try:
        if args.list:
            result = list_tools()
        elif args.search is not None:
            result = search(args.search)
        elif args.describe is not None:
            result = describe(args.describe)
        elif args.parse_h_cmd is not None:
            result = parse_h(args.parse_h_cmd)
        elif args.command is not None:
            result = handle_h(args.command)
        else:
            result = handle_h("/h help")
    except Exception as exc:  # noqa: BLE001 — CLI surface
        result = _empty_result(
            ok=False,
            operation="invalid",
            error=str(exc),
            message=f"help_service error: {exc}",
        )
        _cli_print(result, as_json=args.json)
        return 2

    _cli_print(result, as_json=args.json)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
