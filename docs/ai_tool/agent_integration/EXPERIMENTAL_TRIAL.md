# Experimental Tool Execution Trial — Phase 4

**状態:** Phase 4 実装済み  
**スコープ:** 隔離環境での LLM Tool 公開・選択・実行・結果利用 trial

---

## 目的

`local:read_url_text` を **trial 専用** LLM Tool schema に載せ、Tool 選択・引数生成・実行・結果利用までを隔離検証する。`search_web` との使い分けも評価対象。

```text
Trial Runner (isolated)
  ├─ production subset: search_web (registry 読取のみ)
  └─ experimental overlay: read_url_text (catalog → implementation)
        ↓
   mock/real LLM tool_calls loop
        ↓
   execute_trial_tool → messages に結果返却
```

---

## 本番との境界

| 項目 | 本番 agent.py | Phase 4 Trial |
|------|--------------|---------------|
| Ollama schema | registry visibility=agent の 7 Tool | trial runner が overlay 生成 |
| read_url_text | **非公開** | trial のみ公開 |
| execute path | `execute_tool()` + registry | `execute_trial_tool()` + catalog |
| Registry | 変更禁止 | **変更なし** |
| Discovery agent_available | false | **false のまま** |

---

## search_web vs read_url_text

| | search_web | read_url_text |
|---|-----------|---------------|
| **用途** | キーワード Web 検索 | 既知 URL の HTTP GET 本文取得 |
| **入力** | `query`, `limit?` | `url`, `max_bytes?`, `timeout_seconds?` |
| **出力** | hits (title/snippet/url) | page body text |
| **いつ使う** | URL 不明・探索・複数ソース | URL が明示されている |
| **使わない** | 特定 URL の直接 GET | キーワード検索 |

---

## API

```python
from ai_tool.agent_integration import run_experimental_trial

result = run_experimental_trial(catalog_entries_dir=sandbox_entries)
# result.tools_exposed → ["read_url_text", "search_web"]
# result.execution_count > 0
# result.registry_modified == False
```

---

## Trial シナリオ

1. **url_fetch_known_page** — URL 指定 → `read_url_text` 選択期待
2. **web_search_open_question** — 探索質問 → `search_web` 選択期待

デフォルトは mock LLM + mock fetch/search（deterministic）。

---

## Safety

- Registry / production catalog / agent.py **未変更**
- Production Discovery は `agent_available=false` 維持
- Trial 実行は isolated runner のみ
- 本番 `create_ollama_tools()` 出力は trial 前後で同一

---

## 関連

- [HUMAN_REVIEW.md](./HUMAN_REVIEW.md) — Phase 3
- [DISCOVERY_HOOK.md](./DISCOVERY_HOOK.md) — Phase 2
- [PHASE4_REPORT.md](./PHASE4_REPORT.md)
