# FILE-TOOLS-CHAIN-DIAG-P2-5 作業 REPORT

**TASK_ID:** `FILE-TOOLS-CHAIN-DIAG-P2-5`  
**担当:** Cursor  
**状態:** `P2-5_INVESTIGATION_COMPLETE`  
**日付:** 2026-09-02

---

## 1. P2-4で発見された問題

P2-4（`reports/FILE-TOOLS-INTEGRATION-P2-4.md`）では:

| シナリオ | 観測 |
|----------|------|
| A（広い search） | `search_files` のみ → `read_file` なし。英語で推測回答 |
| C（registry 内 search） | `search_files` のみ → 最終回答空 |
| B（list→read） | **成功** |

一次資料: `runs/ai_tool/20260902T055216Z_file_tools_integration_p24/run.json`

---

## 2. 調査目的

`search_files → read_file` が成立しない原因を、以下に切り分ける:

1. Tool Result の受け渡し
2. path の有無
3. LLM の次 Tool Call 生成
4. Agent Tool Calling ループ

**本調査では Agent 改修・Prompt 大幅変更・強制連鎖は行わない。**

---

## 3. 実験環境

| 項目 | 値 |
|------|-----|
| モデル | `qwen3:14b` |
| 経路 | P2-4 同様（`build_production_agent_tools` + `ollama_chat` + `execute_registry_tool`） |
| 診断スクリプト | `ai_tool/agent_integration/file_tools_chain_diag_p25.py` |
| 一次資料 | `runs/ai_tool/20260902T060341Z_file_tools_chain_diag_p25/diag.json` |

---

## 4. 最小再現ケース（狭い path）

### search_files 単体（Tool 実装）

`tools/system/gpu` + `query: def get_gpu_status`:

```json
{
  "ok": true,
  "match_count": 1,
  "truncated": false,
  "error": null,
  "matches": [{
    "path": "tools/system/gpu/gpu_status.py",
    "line": 6,
    "text": "def get_gpu_status():"
  }],
  "payload_bytes": 311
}
```

**read_file に渡せる path は明確に存在する。**

### 広い path との対比（`path: .`, `query: get_gpu_status`）

| 項目 | 狭い | 広い |
|------|------|------|
| match_count | 1 | 50（上限） |
| truncated | false | **true** |
| error | null | マッチ上限メッセージ |
| gpu_status.py in matches | **あり** | **なし**（先頭は PROJECT_SPEC.md 等） |
| payload_bytes | 311 | 9077 |

→ P2-4 の失敗は **検索上限・ノイズ（E）** と切り分け可能。

---

## 5. search_files Tool Result の LLM 受け渡し

ハーネスは `execute_registry_tool` 後、**raw JSON をそのまま** `role=tool` で LLM に渡す（P2-4 / agent_turn / agent.py と同型）。

| 確認項目 | 狭い search | 広い search |
|----------|-------------|-------------|
| `ok` | true | true |
| `matches[].path` | あり | あり（実装ファイル以外が先頭） |
| `error` | null | 打ち切りメッセージあり |
| LLM へ渡る payload | 311B | 4.7〜9KB |

**Agent Loop が Result を欠落させている証拠はなし（D 否定）。**

---

## 6. LLM の次 Tool Call 生成（最重要）

### ケース判定: **ケース B が主因**（LLM が Tool Call を出さない）

P2-4 シナリオ C 再現（`diag.json` → `p24_c_replay`）:

```text
Round 0: search_files 実行
Round 1: llm_tool_call_count = 0 → 最終回答（空）
```

→ **`read_file` の Tool Call は生成されていない** → Agent Loop 問題（ケース A）ではない。

### 反証実験（Test 3: post_search_llm_only）

狭い path の **実際の search_files 結果 JSON** を `role=tool` で渡し、LLM のみ再呼び出し:

```text
llm_tool_names: ["read_file"]
read_file_args: {"path": "tools/system/gpu/gpu_status.py"}
```

→ **検索結果が明確なとき、LLM は read_file を選択できる。**

### 強制 search_files 実験（追加実測）

プロンプトに「`search_files` ツールを使って」と明示 + 狭い path:

```text
Tool 順序: search_files → read_file
read_file_after_search: True
```

→ **`search_files → read_file` 連鎖は成立する**（条件が揃えば）。

### 狭い path だが search_files を選ばない例

プロンプト「探し、read_file で読んで」（search_files 名なし）:

```text
Tool 順序: list_files → read_file  （search_files 未使用）
```

→ LLM は **search より list_files を優先**（C: Tool 選択）。

---

## 7. list_files → read_file との比較

| 観点 | list_files → read_file | search_files → read_file（失敗時） |
|------|------------------------|-------------------------------------|
| 次行動の明確さ | `entries[].name` + `entries[].path` が3件程度で選びやすい | 広い search は数十 match + error |
| LLM の典型行動 | 一覧から `read_file` | スニペットで十分と判断、または打ち切り error で停止 |
| payload サイズ | ~780B | 4.7KB〜9KB |
| path 形式 | `entries[].path` フルパス | `matches[].path` フルパス（形式は同等） |

**形式差（A）より、結果の量・ノイズ・description（B/C）の影響が大きい。**

---

## 8. Agent Loop の挙動

| チェック | 結果 |
|----------|------|
| search 後に max_tool_rounds 内で次ラウンド呼出 | **実施されている** |
| LLM が read_file を返したとき実行されるか | **される**（post_search / force_search で確認） |
| harness `ok:false`（打ち切り error 時） | LLM への JSON は `ok:true` + `error` 文字列のまま渡る。Loop は継続 |

**D: Agent Tool Calling ループ — 主因ではない（PASS）**

---

## 9. 検索上限の影響（E）

P2-4 シナリオ A/C と `wide_root` 検査:

- 50 match / 200 file 上限で打ち切り
- `error` フィールドに日本語メッセージ
- 実装ファイル（`gpu_status.py`）が matches に含まれないケースあり

**E は P2-4 失敗に寄与。ただし狭い path では上限に達しない。**

**E 単独では説明不足**（狭い path + 明示 search_files では連鎖成功のため）。

---

## 10. 原因分類（§11）

| 分類 | 判定 | 根拠 |
|------|------|------|
| **A. Tool Result 形式** | **PARTIAL** | `matches[].path` は read_file 可能。広い結果はノイズ過多 |
| **B. Tool description / Schema** | **PARTIAL** | search→read の明示導線なし。list/search の使い分けが弱い |
| **C. LLM の Tool 選択** | **主因** | 広い search 後に read_file 未生成。list_files を代替選択 |
| **D. Agent Loop** | **FAIL 否定（PASS）** | read_file 生成時は正常実行 |
| **E. 検索範囲・上限** | **副因** | 広い path で打ち切り・実装未到達 |
| **F. その他** | harness `ok` 判定 | `execute_registry_tool` が `error` 非nullで `ok:false` 表示するが、LLM には full JSON 渡る。診断上の混乱要因 |

**複合原因:** **C + E**（状況により **B**）。**D は除外。**

---

## 11. 修正候補（今回は未実施）

| 候補 | 内容 | 優先度 |
|------|------|--------|
| description 改善 | search_files に「実装確認は read_file」と追記 | 中 |
| 検索 path 誘導 | ユーザー/プロンプトで狭い path を指定 | 高（運用） |
| 上限・打ち切り | match 上限時の LLM 向けメッセージ整理 | 中 |
| harness 判定 | `ok:true` + `error` 打ち切りの `rec.ok` 解釈 | 低（観測のみ） |
| Agent 強制連鎖 | **今回禁止どおり採用しない** | — |

---

## 12. 実際に行った変更

| ファイル | 内容 |
|----------|------|
| `ai_tool/agent_integration/file_tools_chain_diag_p25.py` | **新規** 診断スクリプトのみ |

**Tool 実装・Agent Loop・Registry・Prompt の変更なし。**

---

## 13. テスト結果

```text
179 passed, 3 skipped
```

（P2-4 から変更なし。診断スクリプトはテスト対象外。）

---

## 14. §15 最終判定

| 項目 | 判定 |
|------|------|
| search_files 単体 | **PASS** |
| search_files → read_file（狭い path + 明示） | **PASS** |
| search_files → read_file（P2-4 広い条件） | **FAIL** |
| list_files → read_file | **PASS** |
| Tool Result 受け渡し | **PASS** |
| 次 Tool Call 生成（広い search 後） | **FAIL** |
| Agent Loop 実行 | **PASS** |

---

## 15. 今後の推奨対応（P2-6 判断用）

1. **現状維持 + 運用ガイド** — 調査系は狭い `path` を指定
2. **description 最小改善** — search→read の一文（Prompt 大幅変更ではない）
3. **検索上限の UX** — 打ち切り時に「read_file で1件確認を」等（Tool Result 側の軽微改善）
4. **Agent Loop 改修** — **不要**（証拠: post_search / force_search 成功）

---

## 16. 結論

> なぜ qwen3:14b が search_files の後に read_file を選ばないか

**主答:**  
**ケース B** — LLM が次の Tool Call を生成しない、または **list_files を代替選択**する。Agent Loop は正常。

**副答:**  
**ケース E** — 広い検索で打ち切り・ノイズ多量の Result により、read_file へ進む動機が弱い。

**反証:**  
狭い path・明確な match（311B）を渡すと **read_file が正しい path で呼ばれる**。  
`search_files → read_file` 連鎖自体は **技術的に可能**。

**P2-6 へは自動着手しない。**
