# FILE-READ-REGISTRY-P2-1 作業 REPORT

**TASK_ID:** `FILE-READ-REGISTRY-P2-1`  
**担当:** Cursor  
**状態:** `P2-1_COMPLETE`  
**日付:** 2026-09-02

---

## 大目標に対する現在位置

**大目標:** Tool Calling + Tool Contract + Model Registry + 専門 LLM + 既存ソフトウェア

**現在位置:**

- P0 完了
- P1-1 Model Registry 完了
- P1-2 Tool Calling 規約 完了
- **P2-1 read_file Registry 正式公開 完了**
- P2-2 list_files 未着手
- P2-3 search_files 未着手

---

## 実装前の read_file 構造

| 項目 | 内容 |
|------|------|
| 実装 | `tools/file/workspace/read_file.py`（既存） |
| パス解決 | `tools/file/workspace/_paths.py` → `workspace_root()` = リポジトリ root（`registry/tools.json` 基準） |
| 入力 | `path`（必須）, `offset`, `limit`（任意） |
| 出力 | `ok`, `path`, `lines[]`, `total_lines`, `size_bytes`, `error` 等 |
| エラー | `path_error()` で `ok: false` + `error` 文字列（raise しない） |
| セキュリティ | `..` セグメント拒否、`relative_to(root)` で境界、`READ_MAX_BYTES=64KB`、バイナリ拒否 |
| Registry | **未登録**（SYSTEM_PROMPT のみ言及） |
| テスト | 研究・実験用 workspace のみ。本番 Registry 経路テストなし |

---

## 変更ファイル

| ファイル | 変更理由 |
|----------|----------|
| `registry/tools.json` | `read_file` を `visibility: agent` で正式登録 |
| `tools/file/workspace/_paths.py` | workspace 外エラーから内部 root 絶対パスを除去 |
| `tests/fixtures/p2_read_file_sample.txt` | 安全な読取テスト用 fixture |
| `tests/test_read_file_registry.py` | **新規** P2-1 専用テスト |
| `tests/ai_tool/agent_integration/test_production_integration.py` | Registry 移行期待値（C）: `read_file in names` |
| `tests/test_tool_calling_rules.py` | agent 公開 Tool 数下限 10 へ更新 |
| `registry/TOOLS_CHANGELOG.md` | read_file 公開を記録 |

**変更していないもの:** `read_file.py` 本体ロジック、`list_files` / `search_files`、Model Registry、Agent TC 経路、Action Bridge、研究資産。

---

## Tool Contract

| 観点 | 内容 |
|------|------|
| Tool ID | `read_file`（snake_case、既存名維持） |
| description | Workspace 内 read-only、境界・サイズ制限・他 Tool との使い分けを明記 |
| Input | `path`（required）, `offset`, `limit` |
| Output | 既存構造維持（`ok` + `lines` + メタ） |
| Error | 不存在 / ディレクトリ / 境界外 / サイズ超過 / バイナリ を区別 |
| Side Effect | `read-only` |
| Security | `workspace_boundary`, `path_traversal_protection`, `filesystem_access: workspace_read_only` |
| visibility | `agent` |

---

## Registry 登録内容

```text
name: read_file
module: tools.file.workspace.read_file
function: read_file
category: file / workspace
risk: low
side_effect: read-only
visibility: agent
```

`list_files` / `search_files` は Registry **未登録**（P2-2 / P2-3）。

---

## Security

### Workspace 境界

- root = リポジトリ root（cwd 非依存）
- 相対パスのみ解決（LLM から base directory 指定不可）
- 絶対パスは `resolve()` 後に `relative_to(root)` で判定

### Path Traversal 対策

- `..` をパスセグメントに含む入力は解決前に拒否
- Windows 向け `..\` パターンも `Path.parts` で検出
- シンボリックリンクは `resolve()` 後に境界再チェック

### その他

- 64KB 超ファイル拒否
- バイナリスニフ拒否
- エラーメッセージから workspace root 絶対パスを除去（今回修正）

---

## Tool Calling 実測

**環境:** 本機 Ollama、`active_model=qwen3_14b`

| 段階 | 結果 |
|------|------|
| LLM → `read_file` tool_call | **PASS** — `path: tests/fixtures/p2_read_file_sample.txt` |
| Registry → 実装実行 | **PASS** — `EXEC_OK: True` |
| 結果 → messages（role=tool） | **PASS** — JSON 返却 |
| LLM 最終自然言語回答 | **NOT OBSERVED** — 2 回試行で `content` 空（モデル応答。Tool 経路は成立） |

---

## テスト結果

### read_file 専用（§16）

| Test | 内容 | 結果 |
|------|------|------|
| 1 | Registry 取得 | **PASS** |
| 2 | Schema 正しさ | **PASS** |
| 3 | 正常読込 | **PASS** |
| 4 | 不存在 | **PASS** |
| 5 | Workspace 外拒否 | **PASS** |
| 6 | Path Traversal 拒否 | **PASS**（1 skip: POSIX path on Windows） |
| 7 | Tool error → LLM 返却形 | **PASS** |
| 8 | integration 回帰 | **PASS** |

```text
tests/test_read_file_registry.py      15 passed, 1 skipped
tests/test_tool_calling_rules.py      14 passed
tests/test_model_registry.py          14 passed
tests/ai_tool/agent_integration       96 passed
```

---

## 既存テスト回帰結果

**140 passed, 1 skipped** — 退行なし。

`test_production_integration::test_regression_production_tool_names_unchanged` は分類 **C**（Registry 移行期待値）で更新。

---

## 残課題

1. **大容量ファイル** — 現状 64KB 上限で拒否。offset/limit は行単位だが全読込後スライス。chunking / token 制限は未実装
2. **encoding 引数** — UTF-8 固定（`errors=replace`）。将来必要なら Schema 追加
3. **Chat UI `AGENT_VISIBLE_DEFAULT`** — 未更新。本番 `agent.py` Registry 経路とは別。Chat からの auto_allow は別タスク
4. **Live TC 最終回答** — tool_call→実行は確認。空回答はモデル側要因の可能性。E2E 再実測余地あり
5. **list_files / search_files** — P2-2 / P2-3

---

## P2-2 への引き継ぎ

1. `list_files` の Registry 登録（同じ `_paths.py` 境界を再利用）
2. `read_file` と組み合わせた探索→読取フローの integration テスト
3. Chat UI / `AGENT_VISIBLE_DEFAULT` への file tools 段階的追加要否の判断

---

## 完了条件チェックリスト

- [x] read_file 既存実装調査
- [x] Tool Contract 適合
- [x] registry/tools.json 登録
- [x] Agent から利用可能（visibility=agent）
- [x] Workspace 境界
- [x] Path Traversal 拒否
- [x] 絶対パス等 Workspace 外拒否
- [x] 正常読込
- [x] Tool エラー処理
- [x] Native Tool Calling 実測（tool_call + 実行）
- [x] read_file 専用テスト
- [x] integration test PASS
- [x] TOOLS_CHANGELOG 更新
- [x] REPORT 作成

**判定:** `PASS`（最終 LLM 自然言語回答は `NOT OBSERVED` を記録）
