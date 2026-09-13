# Web Tool Formal Adoption — Implementation Report

**Phase:** Implementation Phase  
**Date:** 2026-08-28  
**Prior approval:** [WEB_TOOL_FORMAL_ADOPTION_APPROVAL.md](./WEB_TOOL_FORMAL_ADOPTION_APPROVAL.md)  
**Status:** **COMPLETE**

---

## Summary

| Tool | Purpose | Registry | Agent schema | Overlay |
|------|---------|----------|--------------|---------|
| `search_web` | Discovery | ✅ `visibility=agent` | ✅ | ❌ |
| `read_url_text` | Fetch | ✅ `visibility=agent` | ✅ | ❌ (graduated) |

**HR-7 Research Tool:** DEFERRED (unchanged)

---

## Changes

### search_web

- Committed: `tools/system/network/search_web.py`, `general_web_search.py`
- Registry entry: `module=tools.system.network.search_web`, `function=search_web`
- Input: `query` (required), `limit` (optional)
- Output shape: **unchanged**

### read_url_text

- Registry entry: `module=ai_tool.experimental.read_url.reader`, `function=read_url_text`
- Experimental overlay removed from `production_bridge.py` (`_EXPERIMENTAL_AGENT_TOOL_IDS` empty)
- Discovery: catalog entry skipped when registry has same name (no duplicate)
- Output shape / SSRF boundary: **unchanged**

### Agent

- `SYSTEM_PROMPT`: Discovery/Fetch labels; removed `[EXPERIMENTAL]` from read_url_text
- Prompt ↔ Registry ↔ schema aligned for `search_web` and `read_url_text`

---

## Security

- search_web: search backends only; no arbitrary URL fetch
- read_url_text: SSRF / localhost / private / size / timeout — regression PASS

---

## E2E

| Case | Result |
|------|--------|
| A Search only | PASS (deterministic) |
| B Known URL fetch | PASS (deterministic) |
| C Search → Fetch | PASS (deterministic, 2 rounds) |
| D URL explicit | PASS (read_url_text routing) |
| E SSRF block | PASS |
| Live LLM | See run `evaluation.json` |

---

## Lifecycle (post-adoption)

```text
search_web / read_url_text:
  IMPLEMENTED = YES
  REGISTRY = YES
  AGENT = YES
  PROMPT = YES
  STATUS = FORMALLY_ADOPTED
```

---

## Compatibility

- Observation tools unchanged
- No intentional output breaking change
- Agent capability expansion (new tools visible)

---

## Run

```bash
python ai_tool/run_web_tool_formal_adoption_implementation.py
```
