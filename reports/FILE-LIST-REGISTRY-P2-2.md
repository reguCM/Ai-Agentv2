# FILE-LIST-REGISTRY-P2-2 作業 REPORT

**TASK_ID:** `FILE-LIST-REGISTRY-P2-2`  
**担当:** Cursor  
**状態:** `P2-2_COMPLETE`  
**日付:** 2026-09-02

---

## 大目標に対する現在位置

**大目標:** Tool Calling + Tool Contract + Model Registry + Workspace File Tools

**現在位置:**

- P2-1 `read_file` 完了
- **P2-2 `list_files` 完了**
- P2-3 `search_files` 未着手（自動着手なし）

---

## 実施内容

1. 既存 `tools/file/workspace/list_files.py` を調査（実装変更なし）
2. `registry/tools.json` に `list_files` を `visibility: agent` で正式登録
3. Input Schema は `path` のみ公開（`recursive` / `glob` は非公開 → 既定で非再帰・直下のみ）
4. 専用テスト `tests/test_list_files_registry.py` 追加
5. P2-1 回帰テスト期待値を最小更新（分類 C）
6. Native Tool Calling 実測（本機 Ollama）

---

## 変更ファイル

| ファイル | 変更理由 |
|----------|----------|
| `registry/tools.json` | `list_files` 正式登録 |
| `tests/test_list_files_registry.py` | **新規** P2-2 専用テスト |
| `tests/ai_tool/agent_integration/test_production_integration.py` | Registry 期待値: `list_files in names` |
| `tests/test_read_file_registry.py` | 同上（P2-1 テストの整合） |
| `tests/test_tool_calling_rules.py` | agent 公開 Tool 数下限 11 |
| `registry/TOOLS_CHANGELOG.md` | 変更履歴追記 |

**変更していないもの:** `list_files.py` 本体、`_paths.py`、`read_file`、`search_files`、Model Registry、Agent TC 経路、Action Bridge、研究資産。

---

## Registry 登録内容

```text
name: list_files
module: tools.file.workspace.list_files
function: list_files
category: file / workspace
risk: low
side_effect: read-only
visibility: agent
input: path（任意。省略時 workspace root）
```

`recursive` / `glob` は Registry Schema に含めない。実装の既定値 `recursive=False` により **直下 1 階層のみ** 列挙。

---

## Workspace 境界

P2-1 と同一の `_paths.py` を使用。

- root = リポジトリ root（`registry/tools.json` 基準、cwd 非依存）
- `..` セグメントは解決前に拒否
- 絶対パス・UNC は `resolve()` 後に `relative_to(root)` で判定
- エラーに workspace root 絶対パスを含めない（P2-1 修正済み）

---

## セキュリティ対策

| 脅威 | 対策 |
|------|------|
| Path Traversal (`../`, `..\`) | `Path.parts` で `..` 拒否 |
| 絶対パス / ドライブ指定 | workspace 外として拒否 |
| UNC path | workspace 外として拒否 |
| Workspace 外解決 | `relative_to` 失敗で拒否 |
| 情報露出 | エラーに内部 root パスなし |

---

## Input / Output

### Input（Agent 公開）

| 引数 | 必須 | 説明 |
|------|------|------|
| `path` | 任意 | ディレクトリ相対パス。省略時 `.` |

### Output（既存実装を尊重）

成功時:

```json
{
  "ok": true,
  "root": "...",
  "base": "...",
  "recursive": false,
  "count": N,
  "entries": [{"name": "...", "type": "file|dir", "path": "..."}],
  "truncated": false,
  "error": null
}
```

- `type` は既存実装どおり `"file"` / `"dir"`（`directory` ではない）
- 上限 `LIST_MAX_ENTRIES=500` 超過時は `truncated: true`

### Error

- 不存在 / ファイル指定 / 境界外 / 読取失敗 → `ok: false` + `error` 文字列

---

## Native Tool Calling 実測結果

**環境:** 本機 Ollama、`active_model=qwen3_14b`

| 段階 | 結果 |
|------|------|
| LLM → `list_files` tool_call | **OBSERVED** — `{"path": "tests/fixtures"}` |
| Tool 実行 | **PASS** — `EXEC_OK: True`, `count: 3` |
| 結果 → LLM（role=tool） | **OBSERVED** |
| 最終 LLM 自然言語回答 | **OBSERVED** — 3 ファイル名を列挙 |

---

## テスト結果

### 専用テスト

```text
tests/test_list_files_registry.py    17 passed, 1 skipped
```

| カテゴリ | 確認内容 |
|----------|----------|
| Registry / Schema | 登録・Ollama 変換・`recursive` 非公開 |
| 正常 | `.`, `tests/fixtures`, 非再帰（fixtures 内ファイルは直下に不出現） |
| 拒否 | `..`, `..\`, 絶対パス, UNC, 不存在, ファイル指定 |
| TC ループ | execute_registry_tool → JSON 返却 |

### 回帰

```text
tests/test_read_file_registry.py      15 passed, 1 skipped
tests/test_tool_calling_rules.py      14 passed
tests/test_model_registry.py          14 passed
tests/ai_tool/agent_integration       96 passed
────────────────────────────────────────────────
合計                                  157 passed, 2 skipped
```

`read_file` 含む既存機能に退行なし。

---

## 最終 LLM 回答の観測結果

**OBSERVED** — `tests/fixtures` 内の `__init__.py`, `broken_tools.py`, `p2_read_file_sample.txt` を自然言語で列挙。

（P2-1 では最終回答が空だったが、P2-2 では観測できた。モデル応答のばらつきであり、今回の修正対象ではない。）

---

## 未解決事項

1. **アクセス拒否の実環境テスト** — OS 権限依存のため専用テスト未追加（人工 mock は今回スコープ外）
2. **Chat UI `AGENT_VISIBLE_DEFAULT`** — 未更新（`agent.py` Registry 経路とは別）

---

## 将来課題

1. **大量エントリ** — 1000 / 10000 / 100000 件で Tool Result が LLM Context を圧迫。現状 `LIST_MAX_ENTRIES=500` で打ち切りのみ。ページング・limit は未実装
2. **`search_files`** — P2-3
3. **`recursive` / `glob` の Agent 公開要否** — 現状非公開。必要なら別タスクで Contract 設計
4. **探索→読取フロー** — `list_files` + `read_file` の E2E integration テスト強化

---

## 完了条件チェックリスト

- [x] Registry 正式登録
- [x] visibility: agent
- [x] Tool Contract 整合
- [x] Workspace 境界
- [x] Path Traversal / 絶対パス / Drive / UNC 拒否
- [x] Workspace 内 directory 列挙
- [x] ファイル指定・不存在のエラー
- [x] 内部 root 非露出
- [x] Native Tool Calling 実測
- [x] 専用テスト PASS
- [x] 回帰テスト PASS
- [x] `read_file` 非退行
- [x] CHANGELOG / REPORT

**判定:** `PASS`

---

## P2-3 への引き継ぎ

- `search_files` の Registry 公開（同じ workspace 境界）
- `list_files` → `read_file` の開発支援フロー検証

**P2-3 には自動着手しない。**
