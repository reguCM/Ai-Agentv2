# Safety Boundary — Agent Discovery Phase 1

## 原則

**Discovery is read-only metadata access.**

Phase 1 の Discovery Adapter は Tool **存在の列挙**のみ。副作用なし。

---

## 許可

| 操作 | 状態 |
|------|------|
| `registry/tools.json` 読取 | OK |
| `ai_tool/catalog/entries/` 読取 | OK |
| `registry/ai_tool_catalog.json` 読取 | OK |
| audit JSONL 追記（discovery イベント） | OK |

---

## 禁止

| 操作 | Phase 1 |
|------|---------|
| Tool 実行（local / experimental / MCP） | **禁止** |
| ネットワークアクセス | **禁止**（MCP live discovery 不使用） |
| ファイル書込（Registry / catalog） | **禁止** |
| `agent.py` state 変更 | **禁止**（未接続） |
| experimental Tool 自動昇格 | **禁止** |
| LLM schema への experimental 追加 | **禁止** |

---

## 境界図

```text
┌─────────────────────────────────────┐
│ SAFE: Discovery Adapter (Phase 1)   │
│  JSON read → AgentDiscoveredTool    │
└─────────────────────────────────────┘
          ╳ no connection ╳
┌─────────────────────────────────────┐
│ agent.py execute_tool / ollama      │  ← 未変更
└─────────────────────────────────────┘
          ╳ no connection ╳
┌─────────────────────────────────────┐
│ ai_tool/experimental/* execution    │  ← 未呼び出し
└─────────────────────────────────────┘
```

---

## テストによる確認

`tests/ai_tool/agent_integration/test_discovery.py`:

- experimental reader を monkeypatch しても discovery 成功（実行されない）
- Registry 内容と production discovery の一致

---

## 責務分担

| 層 | Safety 責務 |
|----|------------|
| [Tool Creation SAFETY_BOUNDARY](../tool_creation/SAFETY_BOUNDARY.md) | Spec / Validator / 実装 Tool |
| [AI-TOOL SAFETY_BOUNDARY](../SAFETY_BOUNDARY.md) | Provider / evaluate_tool_safety |
| 本 doc | Discovery read-only |

Discovery は Safety **判定を実行しない**（metadata のみ）。将来 Agent 統合時に `evaluate_tool_safety` 連携は Phase 2+ 候補。
