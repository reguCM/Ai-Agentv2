"""LLM へ渡す Tool Result と、Event へ保存する観測を分ける。

観測のために Tool を再実行しない。無いキーは作らない。
search_web / read_url_text の本文は Event に載せない。
"""
from __future__ import annotations

from typing import Any

from tools.system.tool_result_contract import normalize_tool_result

# 観測してよいスカラー。戻り値に無いものは出さない。
SAFE_SCALAR_KEYS = (
    "ok",
    "status",
    "error",
    "observation_source",
    "source",
    "gpu",
    "name",
    "temperature",
    "temp",
    "utilization",
    "vram_used",
    "vram_total",
    "datetime",
    "timezone",
    "formatted",
    "model",
    "physical_cores",
    "logical_processors",
    "load_percentage",
    "max_clock_mhz",
    "current_clock_mhz",
    "architecture",
    "total_mb",
    "used_mb",
    "free_mb",
    "used_percent",
    "blocked_by_agent_tool_gate",
)

# Event に載せない。LLM 経路とは独立。
OMIT_BODY_KEYS = (
    "hits",
    "main_text",
    "raw",
    "html",
    "content",
    "body",
    "documents",
    "snippets",
    "matrix",
    "research",
)

MAX_STRING = 240
MAX_TITLES = 5


def _clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_STRING:
        return value[:MAX_STRING] + "…"
    return value


def _pick_scalars(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in SAFE_SCALAR_KEYS:
        if key in payload:
            out[key] = _clip(payload[key])
    return out


def _public_error(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    return {
        "code": str(value.get("code") or "")[:MAX_STRING],
        "message": str(value.get("message") or "")[:MAX_STRING],
    }


def _public_warnings(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        {
            "code": str(item.get("code") or "")[:MAX_STRING],
            "message": str(item.get("message") or "")[:MAX_STRING],
        }
        for item in value
        if isinstance(item, dict)
    ]


def observe_tool_result(tool_name: str, result: Any) -> dict[str, Any]:
    """戻り値から Event 用の観測だけを取る。LLM へ渡す JSON ではない。"""
    name = str(tool_name or "")
    if not isinstance(result, dict):
        text = str(result)
        clipped = text[:MAX_STRING]
        return {
            "status": "unknown",
            "truncated": len(text) > MAX_STRING,
            "text": clipped + ("…" if len(text) > MAX_STRING else ""),
        }

    normalized = normalize_tool_result(result, tool_name=name)
    contract_fields = {
        "ok": normalized["ok"],
        "status": normalized["status"],
        "error": _public_error(normalized.get("error")),
        "warnings": _public_warnings(normalized.get("warnings")),
    }

    if name == "search_web":
        hits = result.get("hits") or []
        hit_count = len(hits) if isinstance(hits, list) else 0
        obs: dict[str, Any] = {
            "query": result.get("query"),
            "hit_count": hit_count,
            "omitted": ["hits"],
            **contract_fields,
        }
        for key in ("source", "fetch_limit", "return_limit", "candidates_collected"):
            if key in result:
                obs[key] = result.get(key)
        tried = result.get("backends_tried")
        if isinstance(tried, list):
            obs["backends_tried"] = [str(item) for item in tried]
        web_status = result.get("web_status")
        if isinstance(web_status, dict) and "overall" in web_status:
            obs["web_status_overall"] = web_status.get("overall")
        titles = [
            str(item.get("title") or "")[:80]
            for item in (hits[:MAX_TITLES] if isinstance(hits, list) else [])
            if isinstance(item, dict)
        ]
        if titles:
            obs["titles"] = titles
        return obs

    if name == "read_url_text":
        text = str(result.get("main_text") or "")
        quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
        obs = {
            "url": result.get("url"),
            "main_text_chars": len(text),
            "omitted": ["main_text"],
            **contract_fields,
        }
        if "fact_ready" in quality:
            obs["fact_ready"] = quality.get("fact_ready")
        for key in ("source",):
            if key in result:
                obs[key] = result.get(key)
        return obs

    obs = _pick_scalars(result)
    obs.update(contract_fields)
    sections = result.get("sections")
    if isinstance(sections, dict) and sections:
        section_obs: dict[str, Any] = {}
        for key, value in sections.items():
            if isinstance(value, dict):
                picked = _pick_scalars(value)
                if picked:
                    section_obs[str(key)] = picked
        if section_obs:
            obs["sections"] = section_obs
            obs["composed_section_keys"] = list(section_obs.keys())
            obs["independent_tool_calls"] = False
    derived = result.get("derived")
    if isinstance(derived, dict) and "ok_by_section" in derived:
        obs["derived"] = {"ok_by_section": derived.get("ok_by_section")}
    omitted = [key for key in OMIT_BODY_KEYS if key in result]
    if omitted:
        obs["omitted"] = omitted
    return obs
