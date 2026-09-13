"""Web Evidence grounding helpers for Agent tool results (policy hints, not inference)."""
from __future__ import annotations

from typing import Any

from tools.system.network.web_status import derive_web_status


def enrich_web_tool_result(tool_name: str, result: Any) -> Any:
    """Attach grounding hints and machine-readable web_status for LLM consumption."""
    if not isinstance(result, dict):
        return result
    enriched = dict(result)
    web_status = derive_web_status(tool_name, result).to_dict()
    enriched["web_status"] = web_status

    if tool_name == "search_web":
        hits = result.get("hits") or []
        empty = not hits
        enriched["grounding"] = {
            "web_evidence_available": not empty,
            "empty_search": empty,
            "do_not_claim_web_verified_facts": empty,
            "web_status_overall": web_status.get("overall"),
            "instruction": (
                "Search returned no hits. Do not state specific facts as if verified from the Web. "
                "Say confirmation was not possible via search_web."
            )
            if empty
            else (
                "Hits are discovery candidates only. Use read_url_text on selected URLs for evidence. "
                "Do not treat titles alone as verified facts."
            ),
        }
    elif tool_name == "read_url_text":
        quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
        fact_ready = bool(quality.get("fact_ready"))
        ok = bool(result.get("ok"))
        overall = web_status.get("overall")
        enriched["grounding"] = {
            "prefer_main_text_for_facts": True,
            "do_not_analyze_html_structure": True,
            "fact_ready": fact_ready,
            "web_status_overall": overall,
            "instruction": (
                "Use main_text as evidence. Answer the user's question from main_text. "
                "Do not describe HTML/JSON structure unless the user asked for format debugging."
            )
            if ok and fact_ready
            else (
                "Fetch succeeded but evidence quality is insufficient (fact_ready=false). "
                "Do not present specific numeric facts as confirmed. "
                "Try another URL, adjust search, or state that evidence was insufficient."
            )
            if ok
            else "Fetch failed. Do not claim page content was retrieved.",
        }
    return enriched
