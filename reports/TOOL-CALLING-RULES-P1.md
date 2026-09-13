# TOOL-CALLING-RULES-P1 作業 REPORT

**TASK_ID:** `TOOL-CALLING-RULES-P1`  
**担当:** Cursor  
**状態:** `P1-2_COMPLETE`  
**日付:** 2026-09-02

---

## 大目標に対する現在位置

**大目標:** Tool Calling を主経路とし、Tool 規約と Model Registry で運用基盤を整える

**現在位置:**

- P0 完了
- P1-1 Model Registry 完了
- **P1-2 Tool Calling 規約 完了**
- P2 未着手

---

## 実装前の Tool 構造

### 正本と経路

| 層 | 場所 | 役割 |
|----|------|------|
| Tool 登録正本 | `registry/tools.json` | 23 Tool 登録 |
| LLM 公開 | `agent.create_ollama_tools()` | `visibility == "agent"` のみ（9 Tool） |
| 実行 | `agent.execute_tool()` | Registry 解決 → `module.function` 呼出 |
| Schema 変換 | `agent.py` / `experimental_exposure.registry_entry_to_ollama_tool` | `input` → Ollama parameters |
| 試験実行 | `gpu_process_e2e.execute_registry_tool` | agent.py 非 import の Registry 実行 |
| overlay | `production_bridge` | P0 以降空（`read_url_text` は Registry 正本） |

### visibility 実態

- **`agent`:** 9 Tool（観測系 + `search_web` + `read_url_text` + legacy `cpu_status`）
- **未指定:** 14 Tool（Tool Builder パイプライン内部。LLM 非公開）

### 既存 Contract の観察

- description は多くの Tool で LLM 向けに具体化済み（データ源・制約明記）
- 観測系は `ok` / `status` / `error` を返す実装が一般的
- `read_url_text` は `ok` / `error` + SSRF（P0 維持）
- Legacy `cpu_status` は `{"status": "..."}` のみ — 形式統一の例外
- `execute_tool` は想定外 Exception を raise（構造化 error に未変換）— 既知の例外

---

## Tool Contract（決定内容）

概念的な Contract 観点:

```text
identity   → name, module, function
purpose    → description, keywords, category
input      → input schema（type, description, required）
output     → 実装戻り値（Registry output は任意ヒント）
error      → ok:false + error（推奨）。想定外は raise
side_effect→ read-only / write / external-effect（新規推奨フィールド）
security   → risk + 実装制約（SSRF 等）
visibility → agent / 未指定（非公開）
```

過剰フレームワーク化は避け、**ドキュメント + 最小検証** で運用。

---

## 決定した規約（要約）

| 項目 | 決定 |
|------|------|
| Tool ID | 新規は `snake_case`。既存改名禁止 |
| description | LLM 選択用。何を・どこから・制約を明記。単独「情報を取得します」禁止（新規） |
| Input Schema | `type` + `description` 必須。`required: true` またはトップレベル `required` |
| Output | 新規は `ok` / `error` 推奨。既存一斉変更はしない |
| Error | 構造化 dict → LLM `role=tool` へ JSON 返却 |
| Side Effect | 分類を定義。既存は description から推定可 |
| Security | `risk` + network/filesystem/process の明示。SSRF 維持 |
| visibility | `agent` のみ Ollama 公開。Registry 存在 ≠ Agent 利用可 |
| 登録 | 実装 → Registry → テスト → CHANGELOG |
| 変更 | ID/schema/output/security は CHANGELOG 必須 |
| EXCEPTIONS | legacy / experimental / special format を明示記録 |

---

## 変更ファイル

| ファイル | 変更理由 |
|----------|----------|
| `docs/TOOL_CALLING_RULES.md` | **新規** 規約正本 |
| `registry/TOOLS_CHANGELOG.md` | **新規** Tool 変更履歴 |
| `tools/system/tool_contract.py` | **新規** 参照・検証 Access Layer |
| `tests/test_tool_calling_rules.py` | **新規** 規約・経路テスト（§19 Test 1–6） |

**変更していないもの:** `registry/tools.json` 本体、Model Registry、`agent.py` 主経路、Action Bridge、研究資産、file tools。

---

## 既存 Tool への適用結果

| Tool | 分類 | 結果 |
|------|------|------|
| `get_gpu_status` | 適合 | description・Schema・ok/error 実装。検証 PASS |
| `get_cpu_status` | 適合 | CIM 実測・Legacy 区別明記。検証 PASS |
| `get_gpu_processes` | **D** 例外維持 | `processes` 配列を含む構造化 dict。規約上 EXCEPTIONS に記載 |
| `read_url_text` | 適合 | Schema・SSRF・ok/error。P0 対策維持。検証 PASS |
| `create_tool_proposal` | **B** Registry 定義は十分 | `visibility` 未指定は意図的（LLM 非公開） |

`validate_agent_visible_registry()`: agent 公開 9 Tool すべて **issue 0**。

---

## 例外（EXCEPTIONS）

| ID | 内容 | 扱い |
|----|------|------|
| E1 | `cpu_status` — Legacy output 形式 | 後継 `get_cpu_status` を優先。今回改修しない |
| E2 | `execute_tool` の想定外 raise | 新規 Tool は捕捉して構造化 error 推奨。既存はそのまま |
| E3 | Tool Builder 系 visibility 未指定 | パイプライン内部 Tool。暗黙公開しない |
| E4 | `side_effect` フィールド未一括導入 | 新規から任意追加。既存は description で代替 |

---

## テスト結果

### P1-2 新規（指示書 §19）

| Test | 内容 | 結果 |
|------|------|------|
| Test 1 | Registry 読込 | **PASS** |
| Test 2 | Schema → Ollama | **PASS** |
| Test 3 | 代表 Tool 実行 | **PASS** |
| Test 4 | Tool エラー LLM 返却可能形 | **PASS** |
| Test 5 | visibility | **PASS** |
| Test 6 | agent_integration 回帰 | **PASS** |

```text
tests/test_tool_calling_rules.py     14 passed
tests/ai_tool/agent_integration      96 passed
```

---

## 回帰テスト結果

Native Tool Calling 主経路・Registry 実行・SSRF ブロック・visibility フィルタに退行なし。

---

## 残課題

1. **`side_effect` フィールド** — 規約定義済み。既存 23 Tool への一括追加は未実施（P2 以降で段階的に）
2. **Output 形式統一** — 新規推奨のみ。Legacy `cpu_status` 等の移行は別タスク
3. **file tools** — Registry 未登録のまま（P2 想定）。SYSTEM_PROMPT との不整合は未解消
4. **`execute_tool` 例外経路** — 構造化 error への統一は将来検討
5. **Tool Builder 系の visibility 明示** — 現状「未指定＝非公開」で動作。`pipeline` 値の正式採用は将来

---

## P2 への引き継ぎ

1. file tools（`list_files` / `read_file` / `search_files`）の Contract 設計と Registry 登録
2. 既存 Tool への `side_effect` 段階的付与
3. Tool 変更時の CHANGELOG 運用継続
4. Tool Calling E2E 実測 evaluation の Registry への追記（Model Registry evaluation と整合）

---

## 禁止事項の遵守

- 全 Tool 全面リファクタ: **なし**
- Tool ID 改名: **なし**
- file tools 本番公開: **なし**
- Model Registry 変更: **なし**
- Agent 再設計 / TC 経路変更: **なし**
- Action Bridge / 研究資産削除: **なし**

---

## 完了条件チェックリスト

- [x] TOOL_CALLING_RULES.md 作成
- [x] Tool Contract 明文化
- [x] Tool ID / description / Input / Output / Error / Side Effect / Security / visibility 規約
- [x] Registry 登録・変更・CHANGELOG・EXCEPTIONS・新規手順
- [x] 代表 Tool 整合確認
- [x] Native Tool Calling 回帰 PASS
- [x] REPORT 作成

**判定:** `PASS`
