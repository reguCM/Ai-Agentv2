# Production Agent Integration — Phase 5

**状態:** Phase 5 実装  
**スコープ:** `local:read_url_text` を本番 Agent overlay 経由で LLM 公開・実行（Registry 未登録）

---

## 設計

```text
registry/tools.json (7 production tools — 不変)
        +
ai_tool/catalog/entries/local_read_url_text.json
        ↓
production_bridge.append_experimental_agent_tools()
        ↓
agent.py tools[] → LLM
        ↓
execute_tool() → production_bridge.execute_experimental_agent_tool()
        ↓
ai_tool.experimental.read_url.reader.read_url_text()  (+ SSRF)
        ↓
agent_tool_gate (authorize_tool_execution)
```

---

## 二つの availability 概念

| フィールド | 意味 |
|-----------|------|
| `agent_available` (Discovery) | Registry `visibility=agent` 統合済みか |
| `experimental_agent_exposed` (Hook) | 本番 Agent overlay で LLM 公開中か |

`read_url_text` は Phase 5 時点で:

```text
agent_available=false              (Registry 未登録)
experimental_agent_exposed=true    (overlay 有効時)
discovery_category=experimental
```

三層 catalog status は変更しない。

---

## 無効化

```text
AI_AGENT_DISABLE_EXPERIMENTAL_READ_URL=1
```

---

## search_web との使い分け（SYSTEM_PROMPT + schema description）

- **search_web** — URL 不明・探索
- **read_url_text** — 既知 URL の本文 GET

---

## Safety

- SSRF: `ai_tool/experimental/read_url/ssrf.py`（Agent 経路でも同一実装）
- Gate: `authorize_tool_execution()` — 本番 gate と同経路
- Registry: 変更なし

---

## 関連

- [EXPERIMENTAL_TRIAL.md](./EXPERIMENTAL_TRIAL.md) — Phase 4 隔離 trial
- [PHASE5_REPORT.md](./PHASE5_REPORT.md)
