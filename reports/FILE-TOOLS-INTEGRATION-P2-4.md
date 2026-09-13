# FILE-TOOLS-INTEGRATION-P2-4 作業 REPORT

**TASK_ID:** `FILE-TOOLS-INTEGRATION-P2-4`  
**担当:** Cursor  
**状態:** `P2-4_COMPLETE`  
**日付:** 2026-09-02

---

## 大目標に対する現在位置

**大目標:** Native Tool Calling Agent が Workspace File Tools を組み合わせて実際に調査できるか

**現在位置:**

- P2-1 `read_file` / P2-2 `list_files` / P2-3 `search_files` Registry 公開完了
- **P2-4 統合フロー実測検証 完了**
- P2-5 以降 未着手（自動着手なし）

---

## 検証環境

| 項目 | 値 |
|------|-----|
| OS | Windows |
| モデル | `qwen3:14b`（`config/pipeline.yaml` active_model） |
| Ollama | 本機接続 |
| Tool 経路 | `registry/tools.json` → `build_production_agent_tools()` → Native Tool Calling |
| 実測ハーネス | `ai_tool/agent_integration/file_tools_integration_verify.py` |
| 一次資料 | `runs/ai_tool/20260902T055216Z_file_tools_integration_p24/run.json` |

**注意:** 本検証は `agent.py` 全起動（Clarity / Pre-Web 等）ではなく、Registry 正規 Tool ループを **現行 Ollama モデルで実測** したもの。`agent.py` の SYSTEM_PROMPT はより長いが、File Tool 説明は同等。

---

## 人間用：LLM 入力・観察用ブラウザ画面の手動実行方法

### 方法 A — P2-4 実測ハーネス（推奨・再現容易）

Workspace File Tools 統合シナリオを一括実行する。

```powershell
Set-Location D:\AI-Agent
python -m ai_tool.agent_integration.file_tools_integration_verify
```

- 出力: 各シナリオの Tool 列・最終回答の先頭
- 保存: `runs/ai_tool/<timestamp>_file_tools_integration_p24/run.json`

環境変数でモデル変更する場合（任意）:

```powershell
$env:AI_AGENT_MODEL = "qwen3_8b"
python -m ai_tool.agent_integration.file_tools_integration_verify
```

### 方法 B — 本番 `agent.py`（フル Agent 経路）

```powershell
Set-Location D:\AI-Agent
$env:AI_AGENT_USER_REQUEST = "tests/fixtures に何があるか確認して、p2_read_file_sample.txt を読んで説明してください。"
$env:AI_AGENT_SKIP_TOOL_DISCOVERY = "1"
$env:AI_AGENT_SKIP_PRE_WEB = "1"
$env:AI_AGENT_SKIP_CLARITY = "1"
python agent.py
```

- 標準出力に Tool 選択・実行ログ・`[MODEL_REGISTRY]` 等が出る
- 人間確認 Gate がある場合はプロンプトに従う
- 既定 USER_REQUEST は Web 調査用のため、**必ず `AI_AGENT_USER_REQUEST` で上書き**すること

### 方法 C — Local Agent Chat UI（観察用ブラウザ）

```powershell
Set-Location D:\AI-Agent
python ai_tool/run_chat_ui.py
```

1. ブラウザで `http://127.0.0.1:8765/` を開く
2. モデルが Ollama 一覧に存在することを確認（画面上部 / `/api/health`）
3. チャット入力欄に自然言語要求を入力して送信

**観察できるもの:**

- 応答テキスト（`turn.answer`）
- パイプラインイベント（tool_select / tool_result 等）
- Dev タイムライン（`/api/dev/events?session_id=...`）

**制約（観測時の注意）:**

- `/api/health` の `capabilities.tools` は `AGENT_VISIBLE_DEFAULT` 固定リストで、**file tools 名が表示に含まれない場合がある**
- 実際の LLM Tool Schema は `build_production_agent_tools()` 経由のため、**`list_files` / `search_files` / `read_file` は呼び出し可能**（P2-4 実測ハーネスと同経路）
- Chat UI の SYSTEM_PROMPT は `agent.py` より短く、File Tool 説明が薄い → 本番 agent との挙動差があり得る

### 方法 D — 単発 Tool 実測（デバッグ用）

```powershell
Set-Location D:\AI-Agent
python -c "from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool; print(execute_registry_tool('list_files', {'path':'tests/fixtures'}))"
```

Registry 実行のみ。LLM ループなし。

---

## 実施内容

1. 既存 3 File Tool の統合フロー実測（シナリオ A〜E）
2. 検証ハーネス `file_tools_integration_verify.py` 追加（Agent 改造なし）
3. 構造テスト `tests/ai_tool/agent_integration/test_file_tools_integration_p24.py` 追加
4. 回帰テスト再実行

**実施しなかったこと:** Planner 追加、Prompt 大幅変更、新 Tool、Tool Chain 機構

---

## 変更ファイル

| ファイル | 理由 |
|----------|------|
| `ai_tool/agent_integration/file_tools_integration_verify.py` | **新規** Live 実測ハーネス |
| `tests/ai_tool/agent_integration/test_file_tools_integration_p24.py` | **新規** 非 Live 構造テスト |
| `runs/ai_tool/20260902T055216Z_file_tools_integration_p24/run.json` | **新規** 一次資料 |

---

## 各シナリオ結果

### シナリオ A：探索 → 検索 → 読み取り

**入力:**

```text
Workspace内で get_gpu_status の実装場所を探し、
該当するファイルの内容を確認して、その実装が何をしているか説明してください。
```

| 項目 | 結果 |
|------|------|
| Tool 順序 | `search_files` のみ |
| 引数 | `query: get_gpu_status`（path 省略 → workspace root） |
| Tool 結果 | match_count=50（上限打ち切り）。`gpu_status.py` 本体未到達の可能性 |
| read_file | **未実行** |
| 最終回答 | 英語で長文（検索ヒットの推測に基づく説明。実装ファイル未読） |
| 判定 | **PARTIAL** — search は動作。read_file 連鎖・根拠付き説明は未達 |

### シナリオ B：list_files → read_file

**入力:**

```text
tests/fixtures に何があるか確認して、p2_read_file_sample.txt の内容を読んで説明してください。
```

| 項目 | 結果 |
|------|------|
| Tool 順序 | `list_files` → `read_file` |
| 引数 | `path: tests/fixtures` → `path: tests/fixtures/p2_read_file_sample.txt` |
| Tool 結果 | 3 件一覧 → 2 行読取成功 |
| 最終回答 | 日本語で一覧と内容を説明 |
| 判定 | **PASS** |

### シナリオ C：search_files → read_file

**入力:**

```text
Tool Registryで read_file がどこで定義または参照されているか探して、
重要なファイルを1つ選んで内容を確認してください。
```

| 項目 | 結果 |
|------|------|
| Tool 順序 | `search_files` のみ |
| 引数 | `path: .`, `query: read_file` |
| Tool 結果 | match_count=10、走査 200 ファイル上限で打ち切り |
| read_file | **未実行**（`registry/tools.json` を直接読んでいない） |
| 最終回答 | **空** |
| 判定 | **PARTIAL** — search のみ。read_file 連鎖なし |

### シナリオ D：Tool エラーからの回復

**入力:**

```text
tests/fixtures/does_not_exist_p2_4.txt を読んでください。
存在しない場合は Workspace 内から正しい対象を探して、見つかったファイルを読んで内容を要約してください。
```

| 項目 | 結果 |
|------|------|
| Tool 順序 | `list_files` → `read_file`（存在しないファイルへの read_file **未実行**） |
| 挙動 | 先に list で正しいファイルを特定してから read |
| 最終回答 | **空** |
| 判定 | **PARTIAL** — 目的は達成方向だが、read_file エラー → 回復の経路は **NOT OBSERVED** |

### シナリオ E1：単純 list_files

**入力:** `tests/fixtures の中に何があるか教えてください。`

| Tool | `list_files` のみ |
| 最終回答 | **空** |
| 判定 | **PARTIAL** — Tool 選択は適切。回答生成 **NOT OBSERVED** |

### シナリオ E2：単純 read_file

**入力:** `tests/fixtures/p2_read_file_sample.txt の内容を教えてください。`

| Tool | `read_file` のみ |
| 最終回答 | 2 行の内容を日本語で返答 |
| 判定 | **PASS** |

---

## 最終判定（§19）

| # | 項目 | 判定 |
|---|------|------|
| 1 | list_files | **PASS** |
| 2 | search_files | **PASS** |
| 3 | read_file | **PASS** |
| 4 | search_files → read_file | **PARTIAL** |
| 5 | list_files → search_files → read_file | **NOT OBSERVED** |
| 6 | Tool Error → recovery | **PARTIAL** |
| 7 | 単一 Tool 要求 | **PARTIAL**（E2 PASS / E1 回答空） |
| 8 | 最終 LLM 回答 | **PARTIAL**（B・E2 OBSERVED / 他は空または英語推測） |

**総合:** **PARTIAL_PASS** — 各 Tool 単体と `list_files→read_file` は成立。search 後の read_file 連鎖と 3 Tool 連鎖は未成立。

---

## Tool 選択の誤り・改善候補（記録のみ。今回未改修）

| 問題 | 観測 | 改善候補（将来） |
|------|------|------------------|
| search 後に read_file しない | A, C | description に「ヒット後は read_file で実装を確認」と明記 |
| search 範囲が広すぎ | A で 50 件上限、C で走査 200 上限 | ユーザー要求に `path: tools` を促すプロンプト例。Registry 既定 path の検討は別タスク |
| read_file せず推測回答 | A 英語長文 | agent SYSTEM_PROMPT の「Tool 結果のみ事実」と整合強化（大幅変更は P2-4 外） |
| 空の最終回答 | C, D, E1 | モデル応答のばらつき。max_tool_rounds 内で回答生成前に終了した可能性 |
| execute_registry_tool の ok 判定 | search 打ち切り時 `ok:false` だが `result.ok:true` | ハーネス表示上の混乱。Tool 自体は動作（既知の gpu_process_e2e 判定） |

---

## 大量検索時の課題

- `SEARCH_MAX_MATCHES=50` / `SEARCH_MAX_FILES_SCANNED=200` で打ち切りが LLM に `error` 文字列として渡る
- 広い `path`（`.` や workspace root）では実装ファイルに到達する前に上限到達しやすい
- ページング・path 絞り込みは未実装（P2-3 引き継ぎどおり）

---

## 非テキストファイルの扱い

既存 `search_files` 実装どおりバイナリ・大ファイルはスキップ。本検証では問題なし。

---

## テスト結果

### 回帰

```text
tests/test_search_files_registry.py              18 passed, 1 skipped
tests/test_list_files_registry.py                17 passed, 1 skipped
tests/test_read_file_registry.py                 15 passed, 1 skipped
tests/test_tool_calling_rules.py                 14 passed
tests/test_model_registry.py                     14 passed
tests/ai_tool/agent_integration                  99 passed, 3 skipped
────────────────────────────────────────────────────────────────
合計                                             179 passed, 3 skipped
```

### 新規構造テスト

- `test_file_tools_in_production_schema` — 3 File Tool が Ollama schema に含まれる
- `test_run_scenario_with_mock_chat` — ハーネス mock ループ

---

## 未解決事項

1. **3 Tool 連鎖** — 今回の実測では未観測
2. **search → read_file** — 部分的のみ（B は list→read で成功）
3. **Chat UI capabilities 表示** — file tools が API 一覧に出ない表示ドリフト
4. **agent.py フル経路** — 本 REPORT の Live 実測は専用ハーネス。agent.py 同一プロンプトでの再実測は未実施

---

## 将来課題

1. P2-5 以降: 3 Tool 統合 E2E のプロンプト / description 微調整（大幅変更なし）
2. search_files の既定 path または description で「狭い path を推奨」
3. Chat UI `AGENT_VISIBLE_DEFAULT` と capabilities API の file tools 整合
4. 打ち切り `error` と `ok:true` の LLM 向けメッセージ整理

---

## 禁止事項の遵守

- Agent 改造・Planner・Tool Chain 追加: **なし**
- 新 Tool / Prompt 大幅変更: **なし**
- P2-5 自動着手: **なし**

**判定:** `PARTIAL_PASS`（個別 Tool と B/E2 連鎖は PASS。search 連鎖・3 Tool 連鎖・一部最終回答は PARTIAL / NOT OBSERVED）
