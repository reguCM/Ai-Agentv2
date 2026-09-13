# Next Decisions

**監査日:** 2026-08-28

**本ドキュメントは優先順位を決定しない。** 人間判断用の候補整理のみ。

---

## Ready candidates（実装・実験は存在、統合判断待ち）

| 候補 | 現状 | 判断が必要な点 |
|------|------|---------------|
| Tool Creation Validator | ADOPT CANDIDATE、36 pytest | Tool Builder pipeline への正式組込み範囲 |
| LocalToolProvider / ToolDescriptor | ADOPT CANDIDATE | Agent 読込路径（read-only view vs execute path） |
| `evaluate_tool_safety` | ADOPT CANDIDATE | agent_tool_gate との関係・重複 |
| `workspace_read_text_scoped` | experimental 完成 | Registry 登録 / visibility / allowlist 本番化 |
| `read_url_text` | experimental 完成 | network Tool の human_required ゲート設計 |
| MCP Provider adapter（1.x/2.x） | 比較で gap 確認 | 別 venv vs 統一 SDK |

---

## Experimental candidates（引き続き experimental 枠）

| 候補 | 理由 |
|------|------|
| Context Builder Phase 3+ | LLM 投入前にスコープ要定義 |
| External Help 自動配信 | Cursor 連携 API / フロー未定 |
| MCP Fetch Phase 2 | Phase 1 FROZEN — trust model 設計後 |
| `ai_tool_catalog.json` 拡張 | trust tier 等 — Proposal のみ |
| Real Web Smoke 定期実行 | CI network 依存の扱い |

---

## Future candidates（設計のみ / 未着手）

| 候補 | 状態 |
|------|------|
| APIToolProvider | UNKNOWN |
| Registry 自動更新 | NOT_READY |
| Agent MCP allowlist | NOT_STARTED |
| LLM 自動 Tool 生成 | 意図的に対象外 |
| Diagnostic Framework NH15+ | FROZEN — 需要まで保留 |
| Cognitive Phase 1 → Tool 接続 | sidecar のみ |

---

## 意図的に保留（STOP / FROZEN）

| 項目 | 理由 |
|------|------|
| Agent ← ai_tool 統合 | Phase 1–複数フェーズで明示的 STOP |
| MCP 本番接続 | Phase 1 Freeze |
| Diagnostic Framework 本番統合 | PROJECT_FREEZE |
| 既存 Run 再実行・上書き | 記録固定 |
| registry/tools.json 変更 | 本番 — 監査・実験で触らない |

---

## 判断時に参照すべき文書

| 決定テーマ | 参照 |
|-----------|------|
| MCP 関連 | [../mcp_comparison/PHASE1_FREEZE.md](../mcp_comparison/PHASE1_FREEZE.md) |
| Tool 採用 | [../tool_creation/CATALOG.md](../tool_creation/CATALOG.md) |
| AI-TOOL 統合 | [../CURRENT_STATUS.md](../CURRENT_STATUS.md) |
| DF 再開 | [../../diagnostic_framework/FUTURE_WORK.md](../../diagnostic_framework/FUTURE_WORK.md) |
| 本監査ギャップ | [KNOWN_GAPS.md](./KNOWN_GAPS.md) |

---

## 推奨されない飛び越し（監査上の注意）

```text
experimental Tool 完成
        ↓
   （Human Review / Policy を省略）
        ↓
Registry + Agent 統合   ← 現状ギャップ。省略判断は人間のみ
```
