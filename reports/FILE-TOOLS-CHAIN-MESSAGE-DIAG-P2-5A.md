# FILE-TOOLS-CHAIN-MESSAGE-DIAG-P2-5A 作業 REPORT

**TASK_ID:** `FILE-TOOLS-CHAIN-MESSAGE-DIAG-P2-5A`  
**担当:** Cursor  
**状態:** `P2-5A_INVESTIGATION_COMPLETE`  
**日付:** 2026-09-02

---

## 1. 調査目的

P2-5 で確認された `run_instrumented_chain()` と `run_post_search_llm_only()` の差について、**LLM へ渡される Native Tool Calling の messages 構造**に違いがないかを調査する。

- 今回は **修正なし**（診断ログ追加のみ）
- P2-6 は着手しない

---

## 2. 実験環境

| 項目 | 値 |
|------|-----|
| モデル | `qwen3:14b` |
| 診断スクリプト | `ai_tool/agent_integration/file_tools_message_diag_p25a.py` |
| 一次資料 | `runs/ai_tool/20260902T061739Z_file_tools_message_diag_p25a/message_diag.json` |
| Ollama 正規化 | `ollama._client._copy_messages()` をパイプライン直前で記録 |

---

## 3. 調査経路と結果概要

| 経路 | シナリオ | Round2 前 messages | 次 LLM 出力 |
|------|----------|-------------------|-------------|
| **A** instrumented（広い search） | P2-4 C 再現 | 4 件（User→Assistant→Tool） | `round1_tool_names: []` **失敗** |
| **A** instrumented（狭い search） | 明示 search_files | 4 件（同上構造） | `round1_tool_names: ["read_file"]` **成功** |
| **B** post_search_llm_only | 狭い payload 注入 | 4 件（合成 Assistant→Tool） | `llm_tool_names: ["read_file"]` **成功** |
| 合成 A/B | tool_name 有無 | 同一狭い payload | **両方** `read_file` **成功** |

---

## 4. 成功経路の messages 構造

### 4.1 instrumented_chain（狭い search・成功）

**入力 messages（Round2 直前、4 件）**

| index | role | 型 | tool_calls | tool_name | 備考 |
|-------|------|-----|------------|-----------|------|
| 0 | system | dict | — | — | 共通 system prompt |
| 1 | user | dict | — | — | 「search_files ツールを使って…」 |
| 2 | assistant | **ollama.Message** | `search_files` | null | **`thinking` あり**（~1100 文字） |
| 3 | tool | dict | — | **`search_files`** | payload 577B、1 match |

**`_copy_messages()` 後（Ollama へ実際に渡る形）**

- assistant: `content: null`, `thinking` 保持, `tool_calls` 保持
- tool: `tool_name: "search_files"` 保持, `content` = JSON
- **`tool_call_id` は全て `null`**（Ollama `ToolCall` に `id` フィールドなし）

**Round2 出力:** ネイティブ `tool_calls: [{name: read_file, arguments: {path: tools/system/gpu/gpu_status.py}}]`

### 4.2 post_search_llm_only（成功）

**入力 messages（LLM 直前、4 件）**

| index | role | 型 | tool_calls | tool_name | 備考 |
|-------|------|-----|------------|-----------|------|
| 0 | system | dict | — | — | 同上 |
| 1 | user | dict | — | — | 「tools/system/gpu 以下で…」（文言が instrumented と異なる） |
| 2 | assistant | **dict** | `search_files` | — | `content: ""`, **`thinking` なし**（合成） |
| 3 | tool | dict | — | **なし** | payload 311B（`web_status` なし） |

**`_copy_messages()` 後**

- assistant: `thinking: null`, `tool_calls` 保持
- tool: **`tool_name: null`**
- `tool_call_id`: 全て `null`

**出力:** ネイティブ `tool_calls: [{name: read_file, ...}]`

---

## 5. 失敗経路の messages 構造

### instrumented_chain（広い search・失敗）

**入力 messages（Round2 直前）** — 成功経路と **同一パターン**

| index | role | 型 | tool_calls | tool_name | 備考 |
|-------|------|-----|------------|-----------|------|
| 0 | system | dict | — | — | 同上 |
| 1 | user | dict | — | — | 「Tool Registryで read_file が…」（P2-4 C） |
| 2 | assistant | **ollama.Message** | `search_files` | null | `thinking` あり（~969 文字） |
| 3 | tool | dict | — | **`search_files`** | payload **5964B**, 28 match, truncated |

**`_copy_messages()` 後:** 構造は狭い search 成功時と同型。差は **payload 内容・サイズ** と **user 文言** のみ。

**Round2 出力（失敗の実体）**

```json
{
  "tool_calls": null,
  "thinking": "<tool_call>\n{\"name\": \"read_file\", \"arguments\": {\"path\":\"ai_tool/agent_integration/file_tools_chain_diag_p25.py\"}}\n</tool_call>"
}
```

- ネイティブ `tool_calls` は **空**
- モデルは `read_file` を **`thinking` 内のテキスト `<tool_call>` 形式**で出力
- Agent / harness は `tool_calls` のみ解釈するため **未実行扱い**

---

## 6. 差分まとめ

### 6.1 instrumented 成功 vs post_search（normalized 比較）

`diff_instrumented_success_vs_post_search` で **3 箇所** の差:

| index | 差分内容 | Native Tool Calling 上の意味 |
|-------|----------|------------------------------|
| 1 (user) | プロンプト文言 | 調査対象外（意図的に異なるシナリオ） |
| 2 (assistant) | instrumented に `thinking` あり / post_search は null | Ollama は thinking を会話履歴に含める。ただし **両経路とも read_file 成功** |
| 3 (tool) | instrumented: `tool_name: search_files` + `web_status` 付き payload / post_search: `tool_name: null` + 短い payload | `tool_name` は Ollama 形式では tool result 紐付けに使えるが、**有無で結果は変わらない**（§7 参照） |

### 6.2 instrumented 成功 vs instrumented 失敗

| 項目 | 成功（狭い） | 失敗（広い） |
|------|-------------|-------------|
| messages 構築パターン | `response.message` + `{role:tool, tool_name, content}` | **同一** |
| assistant 型 | ollama.Message | ollama.Message |
| tool message 形式 | `tool_name` 付き dict | **同一** |
| tool_call_id | 全て null | 全て null |
| payload サイズ | 577B / 1 match | 5964B / 28 match / truncated |
| Round2 出力形式 | ネイティブ `tool_calls` | **`thinking` 内テキスト tool_call** |

→ **messages 入力構造は実質同一。失敗は構造差では説明できない。**

### 6.3 agent.py 本番経路（参照）

```1140:1148:agent.py
        messages.append(
            {
                "role": "tool",
                "tool_name": tool_name,
                "content": json.dumps(result, ensure_ascii=False, indent=2)
                if not isinstance(result, str)
                else result,
            }
        )
```

instrumented 診断は agent.py と同型。

---

## 7. 重点確認項目

### A. Tool Call ID

| 確認 | 結果 |
|------|------|
| Ollama `ToolCall` に `id` | **存在しない** |
| `response.message.tool_calls` 内 ID | 全ケース **null** |
| `messages.append()` 後の保持 | ID 自体が無いため N/A |
| tool result 側の ID | **未使用** |
| Ollama 紐付け方式 | **`Message.tool_name` フィールド**（tool role メッセージ用） |

`_copy_messages()` 実装:

```python
{k: v for k, v in dict(message).items() if v}  # falsy 値は除外
```

空 `content: ""` は正規化時に落ち、`content: null` になる。

### B. tool_name

| 確認 | 結果 |
|------|------|
| instrumented / agent.py | tool message に `tool_name` を設定 |
| post_search | `tool_name` **なし** |
| Ollama 正規化後 | dict の `tool_name` キー → `Message.tool_name` にマップ |
| 合成 A/B 実験 | **有無どちらも `read_file` 生成** |

**結論:** 現行 Ollama 実装では `tool_name` は tool result に付与可能だが、**今回の成功/失敗差の説明因子ではない**。

### C. post_search との差が Tool 選択へ与える影響

- **assistant 型差**（Message vs dict）: `_copy_messages()` 後は同型 `Message` → **実質差なし**
- **thinking 有無**: 成功経路では両パターン存在（instrumented 成功は thinking あり、post_search はなし）→ **単独では説明不可**
- **payload 差**: 広い search（5964B, truncated）vs 狭い（311–577B）→ P2-5 と整合。**主たる差**

---

## 8. 判定（§8）

### 総合判定: **C — messages 構造は実質同一（成功/失敗を説明できない）**

**根拠:**

1. instrumented の成功/失敗は **同一 messages 構築コード**・同一正規化パターン
2. post_search との構造差（`tool_name`, `thinking`, assistant 入力型）は存在するが、**合成 A/B で tool_name 影響なし**、thinking 有無だけでは成功/失敗を分離できない
3. 広い search 失敗時、モデルは `read_file` 意図を **`thinking` テキスト**に出力し、ネイティブ `tool_calls` を生成しない — **入力 messages 構造の問題ではない**

### 副次所見（D 相当）: LLM 出力形式の不一致

広い search 失敗ケースでは、Round2 応答が:

- `tool_calls: null`
- `thinking: "<tool_call>{...read_file...}</tool_call>"`

となり、Native Tool Calling パーサが拾えない。**P2-5 の「LLM が Tool Call を出さない」観測の具体形**として記録。

---

## 9. 原因候補と確度

| 候補 | 内容 | 確度 | 根拠 |
|------|------|------|------|
| **payload 量・ノイズ** | 5964B / 28 match / truncated が次行動を阻害 | **高** | P2-5 + 今回: 同一構造で payload のみ異なり結果が分岐 |
| **LLM 出力形式 drift** | 長いコンテキスト後に `<tool_call>` テキスト形式へ逸脱 | **中** | 広い search Round2 の `round1_assistant_dump` で観測。再現性は 1 回 |
| **user プロンプト差** | 広い search シナリオの曖昧な指示 | **中** | P2-5 既知。messages 構造とは別軸 |
| **tool_name 欠如/有無** | post_search と instrumented の tool message 差 | **低（否定）** | 合成 A/B 両方成功 |
| **tool_call_id 欠如** | ID 未設定 | **低（否定）** | Ollama 仕様上 ID なし。成功経路も同様 |
| **messages.append(Message) vs dict** | assistant 入力型差 | **低（否定）** | `_copy_messages()` 後同型。成功経路で確認 |

---

## 10. 次に修正すべき箇所の候補（今回は未実施）

| 優先 | 候補 | 種別 | 備考 |
|------|------|------|------|
| 1 | search_files 結果の量・打ち切り UX | Tool Result / 上限 | P2-5 E。messages 構造変更ではない |
| 2 | `thinking` 内 `<tool_call>` の検出・救済 | Agent 出力パース | **新候補**（P2-5A 所見）。仕様判断要 |
| 3 | search_files description 最小追記 | Registry | P2-5 候補。messages 構造とは別 |
| 4 | tool_name / tool_call_id 形式統一 | messages 形式 | **今回の証拠では優先度低** |

---

## 11. 実際に行った変更

| ファイル | 内容 |
|----------|------|
| `ai_tool/agent_integration/file_tools_message_diag_p25a.py` | **新規** 診断スクリプト（messages 直前キャプチャ + 合成 A/B） |
| `runs/ai_tool/20260902T061739Z_file_tools_message_diag_p25a/message_diag.json` | 診断一次資料 |

**Agent 本体・Tool Schema・Description・Loop の変更なし。**

---

## 12. 再現コマンド

```bash
python -m ai_tool.agent_integration.file_tools_message_diag_p25a
```

出力例:

```text
Saved: runs/ai_tool/20260902T061739Z_file_tools_message_diag_p25a/message_diag.json
wide round1: []
narrow round1: ['read_file']
post_search: ['read_file']
diff count: 3
```

---

## 13. テスト

診断スクリプト追加のみ。Agent / Registry ロジック未変更。

前回 P2-5 時点: **179 passed, 3 skipped**（本調査で pytest 再実行は省略。変更範囲は診断専用ファイルのみ）

---

## 14. 結論

> `run_instrumented_chain()` と `run_post_search_llm_only()` の messages 構造差は、search_files 後に read_file が生成されない原因か？

**答え: いいえ（判定 C）。**

- 両経路とも Ollama `_copy_messages()` 後は **同一の 4 ターン Native Tool Calling 形状**（system / user / assistant+tool_calls / tool+content）
- instrumented 内の成功/失敗は **messages 構築が同一**で、**payload 内容と LLM 出力形式**で分岐
- `tool_name` の有無は **影響なし**（合成 A/B で確認）
- `tool_call_id` は Ollama 現行仕様で **存在しない**（成功/失敗共通）
- 広い search 失敗時の新情報: モデルが `read_file` を **`thinking` 内 `<tool_call>` テキスト**として出力し、ネイティブ `tool_calls` が空 — Agent が解釈できない出力形式の問題

**P2-5 主因（C: LLM Tool 選択 + E: 検索ノイズ）を messages 構造調査は否定しないが、messages 構造自体を主因とは判定しない。**

**P2-6 へは自動着手しない。**
