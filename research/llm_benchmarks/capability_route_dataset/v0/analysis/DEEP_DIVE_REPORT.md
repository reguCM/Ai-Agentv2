# capability_route v0 50件 傾向深掘り報告

**監査主体:** CURSOR_VALIDATION  
**実装変更:** なし  
**誤判定率:** 算出しない（指示§17）  
**データ:** `results/run_v0_50/` + `cases.json` + `capability_route_obs.py`

---

## 1. 総評

v0の「29件」は、**同一主体の自己矛盾29件**ではなく、**二層の観測がずれて見えている件数**である。

| 層 | 何を表すか | 誰が決めるか |
|----|------------|--------------|
| `judged_appropriate` | 要求文のWeb語ヒント、または related に `search_web` | **heuristic_v1（観測用）** |
| `called` / `agent_tools_tried` の `search_web` | Toolループで実際に `search_web` が実行された | **PROJECT_AGENT_LLM の Tool選択** |

したがって `judged_no × called = 29` を「AgentがWeb不要と判断したのに検索した」と読むと**コード上不正確**である。正しくは:

> 観測heuristicが `judged_appropriate=false` と記録した一方、LLMは `search_web` を実行した。

`uncertain=39` はほぼすべて **related_tools が空**で、heuristicが「公開Toolはあるがrelated一致なし」に落ちた結果である。related一致＝要求達成可能、とは**同一視されていないが、routeラベルの意味はそれに近い簡略化**になっている。

Web検索経路は判断層と独立に見て、outcomeの大半が `error`。hitsはごく少数。検索品質問題とAgent判断問題は分離して扱う必要がある。

---

## 2. データ概要

| 項目 | 値 |
|------|----|
| 総件数（Stage1/2ログあり） | 50 |
| route: uncertain | 39 |
| route: agent_continue | 10 |
| route: needs_new_tool | 1 |

### Web判断 × 実行

| | called | not_called |
|--|-------:|----------:|
| judged_yes | 3 | 5 |
| judged_no | **29** | 13 |

### Web実行 outcome（試行回数ベース、複数回呼出を含む）

| outcome | 回数（概数） |
|---------|-------------:|
| error | 52 |
| hits | 2 |
| empty_hits | 0（本ランの outcome ラベル上） |
| blocked | 0 |

※ `error` の中には「検索結果がありません」も含まれる実装になっている（後述）。empty_hits と error の境界はログ上ぼやけうる。

---

## 3. judged_no × called = 29 の詳細

### 3.1 コード上の意味（確認事項への回答）

1. **`judged_appropriate`**  
   `heuristic_web_search_judgment`:  
   `True` ⇔ `_request_hints_web(request)`（固定語リスト）または `search_web ∈ related_tools`。  
   **LLMの意図・「必要だと思ったか」ではない。**

2. **`agent_tools_tried` の `search_web`**  
   Toolループ内で `execute_tool("search_web", ...)` が走った事実（Gate通過後または blocked結果を含む trial）。

3. **同じ要求を見ているか**  
   同一 `observation_id`・同一 request。ただし**判断アルゴリズムは異なる**（heuristic語 vs LLM）。

4. **別理由で呼ばれうるか**  
   あり。LLMはSYSTEM上 search_web を公開Toolとして知っており、heuristicがfalseでも呼びうる。別Tool失敗後のフォールバックもログ上あり（例: H01で read/list 後に search_web）。

5. **実行前判断か**  
   記録タイミングはループ**後**。しかし judgment の入力は request + related（ループ前に相当する材料）のみで、**tried結果をjudgmentにフィードバックしていない**。実行前判断の再現に近いが、LLM判断そのものではない。

6. **`called=true` の意味**  
   「AgentがWeb必要と判断した」ではない。**search_web が実行された**ことのみ。

### 3.2 29件の内訳（カテゴリ）

| category | 件数 | 含意（ラベルではなく設計意図の参照） |
|----------|-----:|--------------------------------------|
| web_needed_ambiguous | 5 | 設計上Web寄りの曖昧ケース |
| web_needed_no_web_words | 5 | 明示Web語なし・外部情報向き |
| search_hard | 5 | 検索困難 |
| paraphrase | 5 | 天気/RTX言い換え |
| web_needed_clear | 4 | 明確Web向きだがヒント語がheuristicに無い表現 |
| tool_gap_candidate | 4 | 不足候補なのに検索が走った |
| composite_multi_tool | 1 | File後にWeb |

全29件の `web_reason` は **`search_web_is_agent_public` のみ**（＝認識はあるが judged_appropriate はfalse）。

### 3.3 分類（正解ラベルなし）

| 分類 | 件数感 | 説明 |
|------|--------|------|
| **判断と実行が異なる層を見ている** | **29（ほぼ全て）** | heuristic観測 vs LLM実行 |
| 判断と実行が一致している | 0（このバケット定義上） | 本バケットは不一致定義 |
| ケースの意味が曖昧 | 一部（C系・G gap） | 要求自体が多義 |
| ログだけでは判断不能 | 一部 | 「本当にWebが必要だったか」は未判定 |
| その他 | — | — |

**分類軸の問題（重要）:**  
`judged_* × called` を「AgentのWeb要否判断の一致率」に使うと、指標が壊れる。Stage3では少なくとも

- `heuristic_web_flag`
- `llm_executed_search_web`

を別フィールドとして扱うべき。

### 3.4 ヒント語ギャップ（事実）

`_WEB_HINTS` にある例: 検索, 最新, 現在, ニュース, 調べ, …  
**無い例:** 最近, 今日, 明日, 今, 天気, 雨  

そのため A03「最近」・A05「明日の天気」・言い換え天気群などは、設計カテゴリが web寄りでも **judged_no** になりやすい。一方 LLMは多くで search_web を実行 → 29件に入る。

---

## 4. judged_yes × called（3件）

| id | category | outcomes | answer_proxy | tools |
|----|----------|----------|--------------|-------|
| A01 | web_needed_clear | error | inconclusive | search_web |
| A02 | web_needed_clear | error | inconclusive | search_web |
| H02 | composite | error | inconclusive | get_gpu_status, search_web |

### 連鎖の分離

```text
Webを必要とheuristicがフラグ
→ search_web を実行した
→ 検索結果を取得した（本3件は outcome=error。hits成功ではない）
→ 検索結果を回答に利用できた（本データでは未確認／表面は declined/inconclusive）
→ 回答を生成した（空ではないが success とは未判定）
```

**「判断yes＋実行」≠検索成功≠回答成功。** 3件ともパターンは  
`web_judged_called_error_answer_declined_unconfirmed`。

judged_yes の根拠例: A01「ニュース」、A02「現在」、H02「調べて」がヒントにヒット。

---

## 5. judged_yes × not_called（5件）

全件 **category = web_word_but_unneeded（D）**。

| id | web判定理由の要点 | 実際のTool | 表面 |
|----|-------------------|------------|------|
| D01 | Web検索語＋relatedにsearch_web | search_files | present |
| D02 | 「最新」等 | list/read | empty（failure_candidate） |
| D03 | 「現在」 | （試行なし） | inconclusive |
| D04 | ニュース語＋related | search_files | inconclusive |
| D05 | 検索結果語＋related | （試行なし） | present |

### 原因候補（仮説ではなくログ事実＋構造）

- Gate拒否: search_web trial の blocked は見えない（未実行）
- LLMがローカルFile系を選択した（D01/D04で search_files）
- heuristicは語に反応して judged_yes、LLMは「ローカルで足りる」側に寄った可能性

→ **逆方向の層ずれ**（heuristicはWeb寄り、実行は非Web）。誤判定と即断しない。

---

## 6. uncertain 39件

### 事実

- **39件すべて** `route_reason = agent_public_tools_exist_but_no_related_match`
- **39件すべて** related_tools が空（またはagent公開との交わりなし）
- category分布は web_needed_* / search_hard / paraphrase / tool_gap 等多岐

### 分解

uncertain は「能力不足」ではなく、heuristic規則:

```text
新Toolヒントなし
かつ related_public なし
かつ agent公開Toolは存在する
→ uncertain
```

### 共通特徴

- キーワードスコアの related が付かない要求文が多い
- Web実行の有無とは独立（uncertainかつ called が多数＝NNの大半）

### 可能性のある原因（仮説）

- related が弱い／空だと route がほぼ uncertain に飽和する
- その結果 route 分布の情報量が低い

---

## 7. agent_continue（10件）

related が付いた例:

- B01/B02/G04: cpu/gpu 系キーワード → cpu_status / get_gpu_*
- B06/G01/G05系: list / gpu processes
- D01/D04/D05: **search_web が related**（要求にWeb語）→ agent_continue かつ judged_yes、ただし実行はFile寄り（YN）
- C01: 「CPU温度」で cpu/gpu related → agent_continue。一方 search_web も実行（NN側）
- H02: gpu related ＋調べて → continue ＋ search

### 確認結果

**related_tools の存在と「既存Toolだけで達成可能」は同一視されていない（コード上も達成判定なし）。**  
ただし route 名 `agent_continue` は読み手に達成可能性を暗示しうる。用語リスクあり。

C01は「relatedがあるからcontinue」でも、LLMはWebも触っており、routeだけでは行動を表せない。

---

## 8. needs_new_tool（1件）

- **id:** D02  
- **request:** 「registryにある最新のTool一覧をファイルから確認して」  
- **reason:** `request_hints_new_tool; no_related_agent_public_tools`  
- **実際のマッチ:** `_NEW_TOOL_HINTS` の **`registryに`** が部分一致

これは「新機能が必要」という人間語感ではなく、**ヒント文字列の衝突**で発火した観測事実である。成功例／失敗例としない。Pipeline未起動（遵守）。

---

## 9. 言い換え group 分析

### para_osaka_weather（P01a/b/c）

| | route | judged | called | outcomes |
|--|-------|--------|--------|----------|
| P01a | uncertain | no | yes | error× |
| P01b | uncertain | no | yes | hits→error |
| P01c | uncertain | no | yes | error× |

route/judgment/call は一致。outcomeのみ P01b で一時 hits。

### para_rtx3060（P02a/b）

いずれも uncertain / judged_no / called / error 系。大きく分岐せず。

### 明示語依存の可能性

- 「最新」「現在」「ニュース」「検索」は heuristic の Web フラグを上げやすい（D系・A01/A02）
- 「最近」「明日」「天気」はフラグを上げにくい（NNに入りやすい）

→ **単語依存の可能性が観測された**（断定しない）。

---

## 10. Web検索Tool独立分析

### 実行層（Agent経由）

- 試行 outcome: **error 優位**、hits は C02・P01b（各1系統）程度
- blocked: 本ランでは実質なし（collection trust）
- empty_hits ラベル: 本集計ではほぼ出ていない（「結果なし」が error 文字列側に寄っている可能性）

### 単体スモーク（Agent非経由）

`analysis/web_search_foundation_smoke.json` 再確認:

- 英語一般語 → hits ありうる
- 時事日本語・架空語 → 空／error になりやすい

### 分離

| 問題領域 | 本データの示唆 |
|----------|----------------|
| 検索Tool品質 | 時事・日本語クエリで失敗しやすい |
| Agent判断（LLM） | 多くの外部情報要求で search_web を試す |
| 接続・観測 | heuristicフラグとLLM実行が別指標 |

「Web必要→検索→error」は **判断失敗と直接結論できない**。

---

## 11. 観測された事実（A）

1. judged と called は定義上別層である。  
2. judged_no×called が29件で最大セル。  
3. uncertain 39件はすべて related 空＋同一 reason。  
4. needs_new_tool 1件は `registryに` ヒント衝突。  
5. Web outcome は error が支配的、hits は稀。  
6. 言い換えgroup内で route は安定、outcome のみ一部差。  
7. D系5件は judged_yes かつ not_called（逆方向のずれ）。  
8. Stage3ラベルはすべて null のまま。

---

## 12. 判断傾向の仮説（B）

1. Web heuristic は「最近／今日／明日／天気」等を取りこぼし、LLM実行と系統的にずれる可能性。  
2. related キーワードがあると route が agent_continue に寄り、Web行動とは独立。  
3. LLMは外部情報っぽい要求で search_web を試しやすい一方、D系（ローカル指示＋Web語）ではFileを選ぶことがある。  
4. tool_gap 要求でも search_web が走り、route は uncertain のまま残りやすい。  
5. `registryに` のような短すぎる new_tool ヒントは誤発火しうる。

---

## 13. 未判定事項（C）

- 各要求で本当にWebが必要だったか  
- 最終回答の事実正誤  
- hits 1件を回答に使えたか  
- needs_new_tool が能力的に妥当だったか  
- error がネットワーク／ランキング／クエリのいずれか  

---

## 14. Stage 3分類軸の草案（実装しない）

### 観測構造（必須候補）

- `heuristic_web_flag` / `llm_search_executed` / `judgment_execution_layer_mismatch`

### Web判断関連（仮称）

- `heuristic_underflag_candidate`（語不足で judged_no、だがLLMは検索）  
- `heuristic_overflag_candidate`（Web語で judged_yes、だがLLMは非Web）  
- `judgment_uncertain_route_saturated`

### Web実行関連

- `search_error` / `search_hits` / `search_result_not_used` / `search_blocked`

### Tool能力関連

- `related_hit_not_sufficiency`  
- `new_tool_hint_collision_candidate`（D02型）  
- `existing_tool_tried_candidate`

自動ラベルは付けない。人間が軸を確定してから実装。

---

## 15. 追加収集が必要なケース

機械的に100件へは増やさない。不足が見えたものだけ提案する。

| 目的 | 追加案 | 目安 |
|------|--------|-----:|
| heuristic語ギャップの再現確認 | 「最近」「明日の天気」vs「最新ニュース」「現在の株価」の対照を増やす | 6〜8 |
| hits成功連鎖の観測 | 英語・安定トピックで judged/call/hits を揃えて見る | 4〜6 |
| D02型ヒント衝突 | `registryに` 以外の短語衝突の有無確認 | 2〜3 |
| relatedあり＋Web実行の関係 | C01型（local related＋search）を意図的に | 3〜4 |

**今すぐ必須ではない。** まず本報告の「二層ずれ」理解を共有した方がよい。

---

## 16. 次段階への提言

1. **Stage3実装に進まない。** 分類軸草案の人間レビューを先に。  
2. 集計ダッシュボードを作るなら、`judged×called` を「誤判定率」にしない。  
3. 追加収集するなら上表のピンポイントのみ。  
4. Web検索品質改善（F-002）は**別チケット**。本観測の前提知識として分離。  
5. heuristic修正は、同一ケース再試験可能な状態を保ってから（指示§11）。今回は触らない。

---

## 付録: コード参照

- `heuristic_web_search_judgment` / `_WEB_HINTS`: `tools/system/capability_route_obs.py`  
- `heuristic_capability_route`（uncertain条件）: 同  
- `_NEW_TOOL_HINTS` に `registryに` を含む: 同  
- 記録タイミング: `agent.py` Toolループ後 Stage1、最終回答後 Stage2  
