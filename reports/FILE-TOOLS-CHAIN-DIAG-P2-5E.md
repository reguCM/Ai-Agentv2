# FILE-TOOLS-CHAIN-DIAG-P2-5E 作業 REPORT

**TASK_ID:** `FILE-TOOLS-CHAIN-DIAG-P2-5E`  
**担当:** Cursor  
**状態:** `P2-5E_INVESTIGATION_COMPLETE`  
**日付:** 2026-09-02

---

## 1. 結論

### 総合判定: **B — 結果量との相関はあるが、truncated・error・結果品質の影響と分離できない**

同一検索条件（`path: "."`, `query: "read_file"`）・同一モデル（`qwen3:14b`）・同一 user prompt で、**LLM へ渡す search 結果の件数だけ**を変えた診断の結果:

| 観測 | 内容 |
|------|------|
| **件数 1〜30（truncated=false）** | 全ケース **Native `read_file` 3/3**（100%） |
| **件数 39・実 truncated 結果（Case F）** | **Native `read_file` 0/3**、**Type 3（自然言語回答）3/3** |
| **境界** | **30 件（6092B）→ 成功 / 39 件（7811B）+ truncated + error → 失敗** の間に存在。正確な閾値は未特定 |
| **truncated フラグ単独** | 20 件 + `truncated=true`（人工）でも **3/3 成功** → フラグ単独では説明不可 |
| **thinking `<tool_call>` 逸脱** | 今回 3 回×10 ケース = **30 回中 0 回**。P2-5A の Type 4 は再現せず |
| **Case F の失敗形態** | `read_file` を **意図しているが Native Tool Call せず、content に捏造した読取結果**を出力（Type 3） |

**P2-5A 前提との整合:** messages 構造差では説明できない（P2-5A 判定 C）→ 今回、**結果量・truncated 実結果・結果品質（registry 不在・診断ファイルノイズ）** の組合せが LLM 行動変化と相関。**ただし要因の単独切り分けは未完了。**

---

## 2. 実験条件

| 項目 | 値 |
|------|-----|
| モデル | `qwen3:14b` |
| 検索条件 | `search_files(path=".", query="read_file")` |
| user prompt | 「Tool Registryで read_file がどこで定義または参照されているか探して、重要なファイルを1つ選んで内容を確認してください。」 |
| LLM 経路 | `ollama_chat()` → `response.message`（P2-5A `post_search_llm_only` 相当） |
| 各ケース実行回数 | **3 回** |
| 診断スクリプト | `ai_tool/agent_integration/file_tools_search_result_volume_diag_p25e.py` |
| 一次資料 | `runs/ai_tool/20260902T062345Z_file_tools_search_result_volume_diag_p25e/volume_diag.json` |

**結果の切り詰め方（Case A〜E）:** 実 `search_files` 出力の `matches` を先頭 N 件に限定し、`match_count` を更新。`truncated=false`, `error=null` に設定（Tool 実装は変更していない。診断用 payload 合成のみ）。

**Case F:** 実 `search_files` 出力を **改変なし** で使用。

---

## 3. 結果表

### 3.1 主実験（件数段階）

| Case | 件数 | payload (B) | truncated | error | unique paths | Native read_file | thinking `<tool_call>` | no tool (Type 3) |
|------|-----:|------------:|-----------|-------|-------------:|-----------------:|-----------------------:|-----------------:|
| A | 1 | 328 | false | null | 1 | **3/3** | 0/3 | 0/3 |
| B | 5 | 1,037 | false | null | 3 | **3/3** | 0/3 | 0/3 |
| C | 10 | 1,996 | false | null | 3 | **3/3** | 0/3 | 0/3 |
| D | 20 | 4,123 | false | null | 5 | **3/3** | 0/3 | 0/3 |
| E | 30 | 6,092 | false | null | 6 | **3/3** | 0/3 | 0/3 |
| **F** | **39** | **7,811** | **true** | **走査上限 200** | **9** | **0/3** | **0/3** | **3/3** |

※ Case E50（40〜50 件）は今回の wide raw が 39 件のため未実施。

### 3.2 対照実験

| Case | 件数 | payload (B) | truncated | Native read_file | 備考 |
|------|-----:|------------:|-----------|-----------------:|------|
| CTRL_trunc_false_20 | 20 | 4,123 | false | **3/3** | 20 件・truncated なし |
| CTRL_trunc_true_20 | 20 | 4,184 | **true** | **3/3** | 20 件・truncated **人工付与** |
| CTRL_few_long_3 | 3 | 833 | false | **3/3** | 長い text の 3 件 |
| CTRL_many_short_15 | 15 | 3,099 | false | **3/3** | 短い行が多い 15 件 |

**対照1（件数 vs payload サイズ）:** 3 件長文（833B）も 15 件短文（3099B）も成功 → **同一 payload サイズ帯内では件数/行長だけでは失敗に至らない**（30 件 6092B まで成功）。

**対照2（truncated 有無）:** 20 件では `truncated=true` 人工付与でも **3/3 成功** → **truncated フラグ単独は原因ではない**（39 件 + 実 error との組合せは未分離）。

---

## 4. LLM 出力分類（Type 1〜5）

| Type | 定義 | 今回の観測 |
|------|------|-----------|
| **1** | Native `tool_calls` に `read_file` | A〜E, 全 CTRL: **27/27 回** |
| **2** | Native `tool_calls` だが read_file 以外 | **0 回** |
| **3** | `tool_calls=null` + 自然言語回答 | **Case F のみ 3/3** |
| **4** | `tool_calls=null` + thinking/content 内 `<tool_call>` | **0/30 回**（P2-5A では 1 回観測） |
| **5** | その他（空応答等） | **0 回** |

### Case F Type 3 の詳細（重要）

3 回とも `tool_calls=null`。thinking では `read_file` 使用を検討しているが、**Native Tool Call は生成しない**。

| run | thinking の意図 | content の内容 | 捏造 |
|-----|----------------|---------------|------|
| 1, 2 | 「`read_file` で definition を読むべき」 | 「`read_file` で読み取ります」+ **仮想の Python コード例** | **あり** |
| 3 | 「definition は search 結果に無いが参照はある」 | スニペット列挙で終了。**read_file 未実行** | スニペットベース推測 |

**区別（指示書 §8）:**

- LLM は run 1–2 で **`read_file` を意図していた可能性: 中〜高**（thinking に明示）
- **実際には Tool Call として実行されていない: 確定**
- run 1–2 は **Tool 結果を捏造**（ルール 2「Tool 結果にない情報を捏造しない」違反）

---

## 5. 仮説検証

### 仮説: 結果量 ↑ → payload ↑ → Native Tool Call 率 ↓ → thinking `<tool_call>` 逸脱

```text
検索結果が増える → payload が増える → Native Tool Call 生成率が低下 → thinking 内 <tool_call> へ逸脱
```

| 段階 | 観測 | 判定 |
|------|------|------|
| 1〜30 件 | Native read_file **100%** | 仮説の前半（単純な件数増）は **支持されない** |
| 39 件 + 実 truncated | Native read_file **0%** | 後半（失敗）は **支持** |
| thinking `<tool_call>` 逸脱 | **0 回** | P2-5A で観測された Type 4 は **今回再現せず**。失敗形態は **Type 3（捏造回答）** が主 |

**確認できた境界（近似）:**

```text
30 件 (6092B, truncated=false) → Native read_file 3/3
39 件 (7811B, truncated=true, error あり) → Type 3 3/3
```

正確な閾値（31? 35? 38?）および truncated/error/品質の単独寄与は **追加診断が必要**。

---

## 6. 結果品質の記録

wide raw（Case F ベース）の品質:

| 項目 | 値 |
|------|-----|
| match_count | 39 |
| files_scanned | 200（上限到達） |
| truncated | true |
| error | 「走査ファイル数が上限 200 に達したため打ち切りました」 |
| unique_paths | 9 |
| registry 関連 path | **なし**（`registry/tools.json` 未到達） |
| 同一ファイル複数マッチ | 4 ファイル（diag 系スクリプト等） |
| first_match | `agent.py` L886（説明文） |
| last_match | `ai_tool/experimental/run_scoped_read_experiment.py` L169 |

**品質上の問題（Case F）:**

- ユーザー要求は「Tool Registry で read_file の定義」だが、**registry 配下の path が matches に含まれない**
- 先頭は `agent.py` の説明行、続いて diag スクリプトの参照行が大量 → **目的ファイル特定が困難**
- Case F では LLM が「definition は見つからない」と判断する run もあり（run 3）

---

## 7. P2-5A との関係

| P2-5A 結論 | P2-5E での位置づけ |
|------------|-------------------|
| messages 構造差では成功/失敗を説明できない（C） | 今回も同一 messages パターン（post_search）で **payload のみ変更** → 構造は原因でないことを再確認 |
| 広い search 失敗時、thinking 内 `<tool_call>` テキスト（Type 4） | 今回 **Type 4 は 0 回**。失敗形態は **Type 3（自然言語 + 捏造）** が観測された。**逸脱形式は run 依存で固定ではない** |
| payload 内容・サイズが主たる差 | **支持**: 30 件まで成功、39 件実 truncated で失敗 |

---

## 8. thinking 内 `<tool_call>` の扱い

| 項目 | 今回 |
|------|------|
| Type 4 発生 | **0/30 回** |
| P2-5A Type 4 | instrumented 広い search で 1 回（`read_file` 意図、`tool_calls` null） |
| 解釈 | Native Tool Call 逸脱は **`<tool_call>` テキストに限られない**。Case F では **content 直接出力 + 捏造** も失敗形態 |

**救済・変換は実施していない**（指示書準拠）。

---

## 9. 次に進むべき方向（修正は今回未実施）

### 追加診断が必要な点

1. **31〜38 件の中間ケース** — 正確な閾値特定
2. **39 件 + truncated=false** vs **39 件 + truncated=true** — truncated/error の単独寄与
3. **instrumented 経路**での同条件再現 — Type 3 vs Type 4 の出現条件
4. **registry/tools.json が matches に含まれる**条件 vs 含まれない条件

### 次フェーズ候補（実装は別タスク）

| 候補 | 根拠 |
|------|------|
| search_files 結果 UX 改善 | Case F: 打ち切り + registry 未到達 + ノイズ → LLM が read_file せず捏造 |
| 検索 path 誘導（運用） | P2-5 継続 |
| Native Tool Call 逸脱への対応方針検討 | Type 3 捏造 / Type 4 テキスト `<tool_call>` の両方があり得る |
| description 最小改善 | P2-6 候補（今回未着手） |

---

## 10. 実際に行った変更

| ファイル | 内容 |
|----------|------|
| `ai_tool/agent_integration/file_tools_search_result_volume_diag_p25e.py` | **新規** 診断スクリプト |
| `runs/ai_tool/20260902T062345Z_file_tools_search_result_volume_diag_p25e/volume_diag.json` | 診断一次資料 |

**禁止事項（read_file / search_files 実装、registry、Agent Loop、prompt 等）への変更: なし**

---

## 11. テスト

```text
179 passed, 3 skipped
```

対象: `test_search_files_registry`, `test_list_files_registry`, `test_read_file_registry`, `test_tool_calling_rules`, `test_model_registry`, `tests/ai_tool/agent_integration`

---

## 12. 再現コマンド

```bash
python -m ai_tool.agent_integration.file_tools_search_result_volume_diag_p25e
```

---

## 13. 完了条件チェック

| 条件 | 状態 |
|------|------|
| 検索結果量を変えた比較 | **PASS**（A〜F + 対照 4 ケース） |
| Native `tool_calls` 有無記録 | **PASS** |
| thinking `<tool_call>` 有無記録 | **PASS**（0 回だが記録済） |
| payload 量記録 | **PASS** |
| truncated 影響確認 | **PASS**（単独では失敗原因にならず） |
| 結果品質影響確認 | **PASS** |
| 既存テスト非破壊 | **PASS**（179 passed） |
| 報告書作成 | **PASS** |

**P2-6 および修正作業には進まない。**
