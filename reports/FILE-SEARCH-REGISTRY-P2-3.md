# FILE-SEARCH-REGISTRY-P2-3 作業 REPORT

**TASK_ID:** `FILE-SEARCH-REGISTRY-P2-3`  
**担当:** Cursor  
**状態:** `P2-3_COMPLETE`  
**日付:** 2026-09-02

---

## 大目標に対する現在位置

**大目標:** Workspace File Tools（list → search → read）による Agent コードベース調査

**現在位置:**

- P2-1 `read_file` 完了
- P2-2 `list_files` 完了
- **P2-3 `search_files` 完了**
- P2-4（3 Tool 統合フロー検証）未着手（自動着手なし）

---

## 実施内容

1. 既存 `tools/file/workspace/search_files.py` を調査（実装変更なし）
2. `registry/tools.json` に `search_files` を `visibility: agent` で正式登録
3. Input Schema は `query`（必須）+ `path`（任意）のみ（`glob` 非公開）
4. 専用テスト `tests/test_search_files_registry.py` 追加
5. P2-1 / P2-2 回帰テスト期待値を最小更新（分類 C）
6. Native Tool Calling 実測（本機 Ollama）

---

## 変更ファイル

| ファイル | 変更理由 |
|----------|----------|
| `registry/tools.json` | `search_files` 正式登録 |
| `tests/test_search_files_registry.py` | **新規** P2-3 専用テスト |
| `tests/ai_tool/agent_integration/test_production_integration.py` | `search_files in names` |
| `tests/test_read_file_registry.py` | 同上 + 重複 assert 除去 |
| `tests/test_list_files_registry.py` | 同上 |
| `tests/test_tool_calling_rules.py` | agent 公開 Tool 数下限 12 |
| `registry/TOOLS_CHANGELOG.md` | 変更履歴追記 |

**変更していないもの:** `search_files.py` 本体、`_paths.py`、`read_file` / `list_files`、Model Registry、Agent TC 経路、Action Bridge、研究資産。

---

## Registry 登録内容

```text
name: search_files
module: tools.file.workspace.search_files
function: search_files
category: file / workspace
risk: low
side_effect: read-only
visibility: agent
input:
  query (required) — 通常の部分文字列
  path (optional) — 検索起点、省略時 workspace root
```

`glob` / 正規表現 / `max_results` 等は Schema 非公開。

---

## Input Schema

| 引数 | 必須 | 説明 |
|------|------|------|
| `query` | **はい** | 部分文字列（正規表現ではない） |
| `path` | 任意 | 検索起点ディレクトリまたはファイル。省略時 `.` |

---

## Output（既存実装を尊重）

成功時:

```json
{
  "ok": true,
  "query": "...",
  "base": "...",
  "files_scanned": N,
  "match_count": M,
  "truncated": false,
  "matches": [
    {"path": "tools/system/gpu/gpu_status.py", "line": 6, "text": "def get_gpu_status():"}
  ],
  "error": null
}
```

- マッチなし: `ok: true`, `match_count: 0`, `matches: []`
- 上限超過: `truncated: true`, `error` に打ち切り理由

---

## 検索仕様

| 項目 | 仕様 |
|------|------|
| 一致方式 | `needle in line`（部分文字列、正規表現ではない） |
| 走査 | 指定 path 以下を **再帰**（`os.walk`） |
| ファイル指定 | path がファイルの場合はその 1 ファイルのみ |
| スキップ | `should_skip_dir`（`.git`, `node_modules` 等）、バイナリ、256KB 超 |
| 上限 | 走査 200 ファイル / マッチ 50 件（既存定数） |

`list_files`（直下 1 階層）との責務分離を維持。

---

## Workspace 境界 / Path Traversal

P2-1 / P2-2 と同一の `_paths.py`:

- `..` セグメント拒否
- `relative_to(root)` による境界チェック
- walk 中も `current.resolve().relative_to(root)` で逸脱防止
- エラーに workspace root 絶対パスなし

### Symbolic Link

`resolve()` 後に `relative_to` で判定。専用 symlink 機構は新設せず、既存 `_paths.py` / walk 内チェックに依存。追加リスクは将来課題として記録。

---

## Native Tool Calling 実測

**環境:** 本機 Ollama、`active_model=qwen3_14b`

| 段階 | 結果 |
|------|------|
| LLM → `search_files` | **OBSERVED** — `{"path": "tools/", "query": "get_gpu_status"}` |
| Tool 実行 | **PASS** — `EXEC_OK: True`, `MATCHES: 4` |
| Tool Result → LLM | **OBSERVED** |
| 最終 LLM 自然言語回答 | **OBSERVED** — `gpu_status.py` 等の位置を日本語で説明 |

---

## 専用テスト結果

```text
tests/test_search_files_registry.py    18 passed, 1 skipped
```

| カテゴリ | 確認 |
|----------|------|
| Registry / Schema | 登録・`query` required・`glob` 非公開 |
| 正常 | 再帰検索、複数行、マッチなし、単一ファイル path、正規表現非解釈 |
| 異常 | 空 query、不存在 path、traversal、絶対パス、UNC |
| TC ループ | execute_registry_tool → JSON 返却 |

---

## 回帰テスト結果

```text
tests/test_search_files_registry.py     18 passed, 1 skipped
tests/test_list_files_registry.py       17 passed, 1 skipped
tests/test_read_file_registry.py        15 passed, 1 skipped
tests/test_tool_calling_rules.py        14 passed
tests/test_model_registry.py            14 passed
tests/ai_tool/agent_integration         96 passed
────────────────────────────────────────────────────────
合計                                    176 passed, 3 skipped
```

`read_file` / `list_files` 含む既存機能に退行なし。

---

## 大量検索時の課題

| 上限 | 値 | 影響 |
|------|-----|------|
| `SEARCH_MAX_FILES_SCANNED` | 200 | 大規模 repo で未走査領域が残る |
| `SEARCH_MAX_MATCHES` | 50 | LLM Context 圧迫の緩和だが不完全 |
| `SEARCH_MAX_FILE_BYTES` | 256KB | 大ファイルはスキップ |

ページング・offset は未実装。P2-4 以降で要検討。

---

## 非テキストファイルの扱い

- `is_probably_binary()` でスキップ
- UTF-8 読取（`errors=replace`）
- 読取失敗ファイルは `continue`（Tool 全体は継続）

---

## 未解決事項

1. **Symlink 経由の境界逸脱** — 既存 `resolve()` 依存。実環境での実測は未実施
2. **Chat UI `AGENT_VISIBLE_DEFAULT`** — 未更新（Registry 経路とは別）

---

## 将来課題

1. **P2-4** — `list_files` → `search_files` → `read_file` 統合フロー検証
2. **検索結果ページング** — 大量マッチ時の Context 管理
3. **`glob` の Agent 公開要否** — 現状 Schema 非公開

---

## 完了条件チェックリスト

- [x] Registry 正式登録 / visibility: agent
- [x] Tool Contract 整合
- [x] Workspace 境界 / Path Traversal / 絶対パス / Drive / UNC
- [x] 再帰文字列検索 / 構造化結果 / マッチなし処理
- [x] Native Tool Calling 実測
- [x] 専用・回帰テスト PASS
- [x] CHANGELOG / REPORT

**判定:** `PASS`

---

## P2-4 への引き継ぎ

3 File Tool の組み合わせ E2E:

```text
list_files → search_files → read_file
```

**P2-4 には自動着手しない。**
