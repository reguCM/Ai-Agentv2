#!/usr/bin/env python3
"""Web Evidence Pipeline implementation verification (tool + optional live LLM)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    live_chat_fn,
    ollama_available,
)
from ai_tool.agent_integration.production_bridge import ollama_tools_for_llm
from ai_tool.agent_integration.trial import normalize_arguments
from ai_tool.experimental.read_url.reader import read_url_text
from tools.system.network.search_web import search_web

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_evidence_pipeline_implementation"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def deterministic_pipeline() -> dict:
    search = execute_registry_tool("search_web", {"query": "Osaka population", "limit": 1})
    url = None
    if isinstance(search.result, dict):
        hits = search.result.get("hits") or []
        if hits:
            url = hits[0].get("url")
    fetch = None
    if url:
        fetch = execute_registry_tool("read_url_text", {"url": url})
    return {
        "search_ok": search.ok,
        "fetch_ok": fetch.ok if fetch else False,
        "url": url,
        "main_text_preview": (
            str((fetch.result or {}).get("main_text") or "")[:300] if fetch and fetch.result else ""
        ),
        "fact_ready": ((fetch.result or {}).get("quality") or {}).get("fact_ready") if fetch and fetch.result else None,
        "grounding": (fetch.result or {}).get("grounding") if fetch and fetch.result else None,
    }


def live_llm_probe() -> dict:
    if not ollama_available():
        return {"skipped": True, "reason": "ollama_unavailable"}
    try:
        from tools.system.llm_tool_capability import probe_tool_calling
        from tools.system.config import get_llm_profile
        from ollama import chat

        profile = get_llm_profile("qwen3_8b")
        model = profile.get("model")
        cap = probe_tool_calling(model)
        if not cap.get("supported"):
            return {"skipped": True, "reason": "model_tool_calling_unsupported", "capability": cap}

        tools = build_production_agent_tools(include_experimental_overlay=False)
        prompt = (
            "大阪市の人口をWeb検索して、参照したページを根拠に答えてください。"
            "search_web と read_url_text を使ってください。"
        )
        messages = [{"role": "user", "content": prompt}]
        chat_fn = live_chat_fn()
        response = chat_fn(model=model, messages=messages, tools=ollama_tools_for_llm(tools))
        msg = response.message
        tool_trace = []
        if getattr(msg, "tool_calls", None):
            messages.append(msg)
            for tc in msg.tool_calls:
                rec = execute_registry_tool(tc.function.name, tc.function.arguments)
                tool_trace.append(
                    {
                        "tool": tc.function.name,
                        "args": normalize_arguments(tc.function.arguments),
                        "fact_ready": ((rec.result or {}).get("quality") or {}).get("fact_ready")
                        if isinstance(rec.result, dict)
                        else None,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tc.function.name,
                        "content": json.dumps(rec.result, ensure_ascii=False),
                    }
                )
            final = chat(model=model, messages=messages)
            answer = getattr(final.message, "content", None) or str(final.message)
        else:
            answer = getattr(msg, "content", None) or str(msg)

        return {
            "skipped": False,
            "model": model,
            "tool_trace": tool_trace,
            "final_answer_preview": str(answer)[:800],
            "html_meta_response": any(
                x in str(answer) for x in ("HTML", "BeautifulSoup", "パーサー", "JSONデータ")
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {"skipped": True, "reason": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "run_id": RUN_ID,
        "deterministic": deterministic_pipeline(),
        "live_llm": live_llm_probe(),
    }
    (RUN_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nArtifacts: {RUN_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
