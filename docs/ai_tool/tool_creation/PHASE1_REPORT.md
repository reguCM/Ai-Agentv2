# Tool Creation Layer — Phase 1 Report

**完了日:** 2026-08-28  
**スコープ:** 設計・テンプレート・検証基盤（新規 Tool 本体・MCP 実装・既存移行なし）

---

## 1. 現在の Tool 作成手順の問題点

| # | 問題 | 根拠 |
|---|------|------|
| P1 | **提案仕様と Registry のスキーマ乖離** | `validate_tool_spec` は 15 必須項目。登録後 `tools.json` は 8–10 項目（`build_registry_entry`） |
| P2 | **出力契約の欠如** | Registry に `output` がほぼ無い。`validate_tool_result` は Builder 段階のみ |
| P3 | **テストが引数なし 1 回のみ** | `test_tool()` L135 `function()` — パラメータ付き Tool に弱い |
| P4 | **戻り値形式が Tool ごとに非統一** | GPU は rich dict、CPU は `{status}` のみ |
| P5 | **安全ゲートが分散** | `agent_tool_gate`、AST Safety、`evaluate_tool_safety`（AI-TOOL）が非統合 |
| P6 | **二重レジストリ** | `tools.json` vs `ai_tool_catalog.json` スキーマ不一致 |
| P7 | **副作用の明示なし** | Registry に side_effect / execution_mode なし（推論頼み） |
| P8 | **実験と本番採用の状態混同リスク** | Catalog 上の三層分離が未運用 |

**ラベル:** 問題認識 ADOPT CANDIDATE / 解消は NOT READY（本文書で標準化のみ）

---

## 2. 新 Specification で既存 Tool を表現できるか

**はい（ADOPT CANDIDATE）。**

- `get_gpu_status` — 完全 Mapping 可能。Contract・Test も既存テストから逆算可能
- `cpu_status` — Mapping 可能。legacy パターンとして契約の薄さを明示記録

実装・Registry は**一切変更していない**。

---

## 3. Local / MCP / API / External を共通化できる範囲

| 領域 | 共通化 | ラベル |
|------|--------|--------|
| Identity, description, version | 全 Provider | ADOPT CANDIDATE |
| input_schema / output_schema | 全 Provider | ADOPT CANDIDATE |
| side_effect, risk_level, cost | 全 Provider | ADOPT CANDIDATE |
| capability, contract | 全 Provider | ADOPT CANDIDATE |
| tool / experiment / adoption status | Catalog 層 | ADOPT CANDIDATE |
| Discovery + Execution API | Provider ごと | EXPERIMENTAL（AI-TOOL 参照） |
| UI / Resources（Apps SDK） | 対象外 | UNKNOWN |

---

## 4. Provider 固有にすべき情報

| Provider | provider_specific |
|----------|-------------------|
| Local | module, function, registry_visibility, registry_path |
| MCP | server_label, transport, server_command, mcp_tool_name, raw annotations（非信頼） |
| API | base_url, method, auth（未設計） |
| External | 個別定義 |

---

## 5. Test Contract で不足している項目

| 不足 | ラベル |
|------|--------|
| 共通 pytest フィクスチャ | NOT READY |
| CI での Contract 強制 | NOT READY |
| パラメータ化テストの Registry 駆動 | UNKNOWN |
| MCP/API 向け Integration テンプレ | EXPERIMENTAL（文書のみ） |
| `execute_tool` 経由の統合テスト | NOT READY |

契約**定義**自体は ADOPT CANDIDATE。

---

## 6. Catalog に必要な情報

必須（ドラフト）:

- tool_id, name, provider, version
- capabilities, input_schema, output_schema（推奨）
- side_effect, permissions, network_access, risk_level, cost
- **tool_status**, **experiment_status**, **adoption_status**（三層分離）
- spec_ref, provider_specific

不要に混ぜない: LLM prompt 全文、実行ログ本文

---

## 7. 今後 Tool を増やす際の標準手順

[CREATION_WORKFLOW.md](./CREATION_WORKFLOW.md) / [HUMAN_GUIDE.md](./HUMAN_GUIDE.md) 参照:

1. 目的記述 → 2. Specification → 3. 人間検証 → 4. 実装 → 5. Schema 照合 → 6. TEST_CONTRACT → 7. Safety → 8. 人間承認後 Registry → 9. Catalog Entry → 10. Manual Review

自動化・自律登録は行わない。

---

## 8. MCP 実装へ進める準備ができたか

| 観点 | 判定 |
|------|------|
| Tool Specification が MCP metadata を受け入れ可能 | **ADOPT CANDIDATE**（PROVIDER_BOUNDARY マッピング表） |
| MCP 実装そのもの | **本作業では実施しない**（AI-TOOL Phase 1 で実験済み・EXPERIMENTAL） |
| Catalog 手動接続 | **EXPERIMENTAL** |
| 本番 Agent 統合 | **NOT READY** |

**結論:** Specification / Catalog 設計は MCP 接続の**文書上の準備はできた**。実装判断は「Local vs MCP 比較」後に行う（ユーザー指示どおり）。

---

## 9. 今回確定したもの（ADOPTED / ADOPT CANDIDATE）

| 項目 | ラベル |
|------|--------|
| Tool Specification フィールドセット | ADOPT CANDIDATE |
| Creation Workflow（手動） | ADOPT CANDIDATE |
| Test Contract カテゴリ定義 | ADOPT CANDIDATE |
| Tool Contract（CAN/CANNOT/MUST/MUST_NOT） | ADOPT CANDIDATE |
| Human Guide 7 ステップ | ADOPT CANDIDATE |
| Safety パイプライン（DISCOVER→AUDIT） | ADOPT CANDIDATE |
| Catalog 三層状態モデル | ADOPT CANDIDATE |
| 既存 Tool Mapping 2 件 | ADOPT CANDIDATE |
| Phase 0 現状文書化（README） | ADOPTED |

---

## 10. experimental のまま残したもの

| 項目 | ラベル |
|------|--------|
| tool_spec.schema.json | EXPERIMENTAL |
| catalog_entry.schema.json | EXPERIMENTAL |
| Provider Boundary（Interface 未実装） | EXPERIMENTAL |
| Catalog 実体マージ・自動生成 | EXPERIMENTAL |
| MCP マッピング表の運用 | EXPERIMENTAL |
| ai_tool.ToolDescriptor との統合 | EXPERIMENTAL |

---

## 11. UNKNOWN として残したもの

| 項目 |
|------|
| APIToolProvider 設計詳細 |
| LLM 用 Tool Specification Context 生成 |
| Tool Builder ↔ Tool Creation Layer 自動連携 |
| 統一 Audit ログパス |
| 公開 MCP Server allowlist 運用 |
| Apps SDK UI / Resources 連携 |

---

## 12. 次に実装するべき項目（最大 3 件）

1. **Specification バリデータ** — `tool_spec.schema.json` を使う CLI/テスト（既存 Tool 移行なし）
2. **Catalog Entry ジェネレータ（読み取り）** — `LocalToolProvider` + Mapping テンプレから draft Entry 生成
3. **Test Contract pytest スケルトン** — 新 Tool 用 `tests/tool_contract/` 雛形（CI 未接続可）

---

## 成果物一覧

```text
docs/ai_tool/tool_creation/
├── README.md
├── TOOL_SPECIFICATION.md
├── tool_spec.schema.json
├── CREATION_WORKFLOW.md
├── TEST_CONTRACT.md
├── TOOL_CONTRACT.md
├── HUMAN_GUIDE.md
├── PROVIDER_BOUNDARY.md
├── SAFETY_BOUNDARY.md
├── CATALOG.md
├── PHASE1_REPORT.md
└── examples/
    ├── existing_get_gpu_status.md
    ├── existing_cpu_status.md
    └── existing_tool_mapping.md

docs/ai_tool/catalog/
└── catalog_entry.schema.json
```

## 制約遵守

- `agent.py`、既存 Tool、`registry/tools.json`、Tool Builder コード、diagnostic_framework — **未変更**
- 新規 Tool 本体、MCP 新規実装、外部 API、自律登録 — **未実施**

## 関連

- [AI-TOOL Layer Phase 1](../CURRENT_STATUS.md) — MCP 最小実験（別フェーズ）
- [Diagnostic Framework 凍結](../../diagnostic_framework/FREEZE_REPORT.md)
