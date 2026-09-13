# Web Tool Evidence Pipeline — Implementation Phase

**Date:** 2026-08-28  
**Git HEAD (start):** `82fca73`  
**Design basis:** [WEB_TOOL_ARCHITECTURE_DESIGN_CHALLENGE.md](./WEB_TOOL_ARCHITECTURE_DESIGN_CHALLENGE.md) — Hybrid Evidence Pipeline (案 C)

## Summary

Implemented minimal Evidence Contract on `read_url_text`, discovery enrichment on `search_web`, and Agent grounding hints — without Research Tool, model-specific logic, or ranking engine overhaul.

## Changes

| Area | Files | Change |
|------|-------|--------|
| Fetch normalization | `ai_tool/experimental/read_url/html_normalize.py` (new) | HTML → `main_text` + `quality` |
| Fetch | `ai_tool/experimental/read_url/reader.py`, `config.py` | Evidence output; default fetch 256KB; extract then truncate |
| Search | `tools/system/network/general_web_search.py` | `snippet` fallback, `relevance_hint`, `grounding` on empty/non-empty |
| Agent grounding | `tools/system/network/web_evidence.py` (new), `agent.py` | `enrich_web_tool_result`; prompt Search→Fetch→Evidence |
| E2E harness | `ai_tool/agent_integration/gpu_process_e2e.py` | Same enrichment on registry execution |
| Registry | `registry/tools.json` | `read_url_text` description + default max_bytes note |
| Tests | `tests/ai_tool/experimental/test_read_url_evidence.py`, `tests/test_web_evidence_pipeline.py` | New |
| Run | `ai_tool/run_web_evidence_pipeline_implementation.py` | Verification harness |

## Interface (NON-BREAKING additive)

`read_url_text` adds:

- `main_text` — LLM-facing evidence text
- `title` — optional page title
- `quality` — `{ extraction_success, body_reached, truncated, fact_ready, extraction_method, warnings[] }`
- `content` — now mirrors `main_text` (was raw HTML)

`search_web` hit adds (optional fields):

- `relevance_hint` — high/medium/low/unknown
- `snippet` — title fallback when empty

Both tools may include `grounding` after Agent/E2E enrichment.

## Run artifacts

- `runs/ai_tool/20260828_213838_web_evidence_pipeline_implementation/`

## Known constraints

- Wikipedia 大阪市: `mw-parser-output` reachable at 256KB but extracted segment may be wikidata/metadata → `fact_ready=false` (conservative).
- Live qwen3:8b one-round probe: search only, no hallucinated population, no HTML meta response.
- Primary model Tool Calling remains MODEL_CAPABILITY (unchanged).

## Human Review

**YES** — `fact_ready` heuristics and default fetch size increase.

**STOP:** Implementation complete pending Human Review for commit scope.
