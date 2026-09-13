# Agent Integration Phase 5 — 完了報告

**Git baseline commit:** `053e703` — `ai-tool: freeze experimental tool integration baseline`  
**Git integration commit:** `88febb3` — `ai-agent: integrate experimental read_url_text`

---

## Phase 5-0 作業前状態

| 項目 | 状態 |
|------|------|
| branch | `master` |
| 未コミット modified (tracked) | `agent.py`, `registry/tools.json`, research/*, tools/* 等 — **ai-tool 以外の既存作業** |
| 未追跡 (ai-tool) | `ai_tool/`, `docs/ai_tool/`, `tests/ai_tool/`, `runs/ai_tool/` |

**判断:** ai-tool 成果物は未コミットだが、research 大規模 diff 等は baseline に混ぜない。baseline は ai-tool パスのみ selective commit。

---

## Phase 5-1 Git Freeze（baseline）

**Commit message:** `ai-tool: freeze experimental tool integration baseline`

**含める:** `ai_tool/`（Phase 5 bridge 除く）, `docs/ai_tool/`, `tests/ai_tool/`（Phase 5 テスト除く）, `runs/ai_tool/`, `registry/ai_tool_catalog.json`, `.gitignore`

**含めない:** research/*, `registry/tools.json` modified diff, 無関係 tools/* diff

### Pre-commit tests

| Suite | 結果 |
|-------|------|
| tests/ai_tool/ (smoke 除く) | 132 passed, 2 skipped |
| test_read_url_text.py | 28 passed |
| test_agent_tool_gate + test_general_web_search | 15 passed |
| tests/ai_tool/agent_integration/ (Phase 5 前) | 47 passed |

---

## Phase 5-2〜5 統合設計

`production_bridge.py` — Registry 非変更 overlay:

- `append_experimental_agent_tools()` — LLM schema 追加
- `execute_experimental_agent_tool()` — gate + catalog implementation
- `experimental_agent_exposed` — Discovery `agent_available` とは別軸

---

## Phase 5-3 Exposure

```text
tool_status=unavailable
experiment_status=experimental
adoption_status=<catalog 現在値維持>
agent_available=false (Discovery — Registry 未登録)
experimental_agent_exposed=true (overlay 有効時)
```

無効化: `AI_AGENT_DISABLE_EXPERIMENTAL_READ_URL=1`

---

## Phase 5-4 Safety

- SSRF: `read_url_text` 内部（Agent 経路でも同一）
- Gate: `authorize_tool_execution()` 接続
- localhost/private → `ssrf blocked`

---

## Phase 5-5 LLM Schema

- 既存 7 Tool schema **不変**
- `read_url_text` のみ overlay 追加
- description に search_web 使い分け明示

---

## Phase 5-6 / 5-7 実 Agent Trial（mock LLM + bridge）

| Case | expected | result |
|------|----------|--------|
| URL直接取得 | read_url_text | PASS |
| Web探索 | search_web | PASS |
| URL+質問 | read_url_text → 回答 | PASS |
| 危険URL | SSRF 拒否 | PASS |

---

## 最終報告テンプレート

```text
Git baseline commit: (see git log)
Git integration commit: (see git log)

Existing Agent: CHANGED (experimental overlay only)
Existing Registry: UNCHANGED (read_url_text 未登録)

read_url_text: Integrated (experimental overlay)

LLM Tool Selection: PASS (mock trial)
Argument Generation: PASS (mock trial)
Execution: PASS
Safety: PASS
Result Utilization: PASS (mock messages)
search_webとの使い分け: PASS

Regression: PASS (production schema unchanged, registry SHA unchanged)

Remaining UNKNOWN:
- Live Ollama E2E（本番 LLM 実呼び出し）は未実施
- agent.py 全体 diff のうち ai-tool 以外の変更は別途コミット判断

次の判断: 実地評価後に正式 Registry 登録 / 改良 / Reject
```

---

## STOP 条件

該当なし — 統合完了。
