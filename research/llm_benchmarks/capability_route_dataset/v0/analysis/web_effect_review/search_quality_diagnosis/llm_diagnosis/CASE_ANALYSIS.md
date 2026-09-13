# CASE_ANALYSIS

- model: `qwen3:8b`
- generated: `2026-08-24T06:54:08.939043+00:00`

## A06

- request: Python 3.13で追加された主な変更点を教えて
- language: ja_request_en_query
- api_candidate_count: 1
- returned_count: 1
- non_empty_snippet_count: 0
- ranking_dropped_candidates: 0
- page_has_usable_text: False
- llm_received_count: 1
- llm_received_usable_evidence: no
- observed_search_outcome: return_hits_all_snippet_empty
- suspected_bottlenecks: ['A', 'C']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が渡されなかった

**観測事実:**
- return_snippet_nonempty: 0
- api_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- snippet空の候補がLLMに渡されたため、回答に影響

### 2. API段階に有用候補が存在した可能性
**判断:** APIが有用候補を返していない可能性

**観測事実:**
- api_raw: 1
- hit_accepted: 1
- after_unique: 1
- after_ranking: 1
- return: 1

**推測:**
- 検索クエリ「Python 3.13」に合致する候補が不足

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が失われていない

**観測事実:**
- ranking_dropped_total: 0
- ranking_dropped_with_snippet: 0

**推測:**

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に失敗していないが情報不足

**観測事実:**
- api_snippet_empty: 1
- return_snippet_empty: 1

**推測:**
- 取得したページがPython 3.13の情報を持たない可能性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの受け渡しは正常

**観測事実:**
- llm_handoff_count_match: True

**推測:**

### 6. 日英差
**判断:** 言語差による影響は確認されない

**観測事実:**
- language_hint: ja_request_en_query

**推測:**

### 7. 現在性（時間依存の場合）
**判断:** タイムリネスの影響はなし

**観測事実:**
- time_sensitive: False

**推測:**

---

## E04

- request: 日本の運転免許は一般にどう取得されるか教えて
- language: ja
- api_candidate_count: 2
- returned_count: 2
- non_empty_snippet_count: 0
- ranking_dropped_candidates: 0
- page_has_usable_text: False
- llm_received_count: 2
- llm_received_usable_evidence: no
- observed_search_outcome: return_hits_all_snippet_empty
- suspected_bottlenecks: ['C', 'D']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が届いていない

**観測事実:**
- return_snippet_nonempty: 0
- api_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- snippet空候補がLLMに渡された可能性
- ページ本文が存在しても抽出失敗の可能性

### 2. API段階に有用候補が存在した可能性
**判断:** API候補に有用情報が含まれていない

**観測事実:**
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0

**推測:**
- WikipediaのAPIが本文を取得できない可能性
- 検索対象の性質（免許取得手順）がsnippetに反映されない可能性

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が失われていない

**観測事実:**
- ranking_dropped_total: 0
- ranking_dropped_with_snippet: 0

**推測:**

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に失敗

**観測事実:**
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- Wikipediaのページ構造がsnippet取得を妨げる可能性
- APIの取得処理が本文を抜き取れない可能性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの情報伝達に問題なし

**観測事実:**
- llm_received_hit_count: 2
- llm_handoff_count_match: True

**推測:**
- LLMが空のsnippetを処理する仕様の可能性

### 6. 日英差
**判断:** 言語差の影響なし

**観測事実:**
- language_hint: ja
- search_query: 普通自動車免許

**推測:**

### 7. 現在性（時間依存の場合）
**判断:** タイムリーアクセスの影響なし

**観測事実:**
- time_sensitive: False

**推測:**

---

## C03

- request: RTX 3060って今どういう扱いですか？
- language: ja_request_en_query
- api_candidate_count: 5
- returned_count: 5
- non_empty_snippet_count: 0
- ranking_dropped_candidates: 0
- page_has_usable_text: False
- llm_received_count: 5
- llm_received_usable_evidence: no
- observed_search_outcome: return_hits_all_snippet_empty
- suspected_bottlenecks: ['C', 'その他']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が届いていない

**観測事実:**
- llm_received_usable_evidence: no
- return_snippet_nonempty: 0
- api_snippet_nonempty: 0

**推測:**
- snippet空の候補がLLMに渡された可能性
- Wikipediaの抽出処理が失敗している可能性

### 2. API段階に有用候補が存在した可能性
**判断:** APIが有用候補を返したが内容取得失敗

**観測事実:**
- api_candidate_count: 5
- api_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- Wikipediaのページが非表示または構造変更された可能性
- APIが非英語コンテンツを取得できない可能性

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が失われていない

**観測事実:**
- ranking_dropped_total: 0
- ranking_dropped_with_snippet: 0

**推測:**

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得が失敗している

**観測事実:**
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- WikipediaのAPIがコンテンツを取得できない可能性
- ページが非公開または構造変更された可能性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの受け渡しは正常

**観測事実:**
- llm_handoff_count_match: True
- llm_received_hit_count: 5

**推測:**

### 6. 日英差
**判断:** 日本語対応が不十分

**観測事実:**
- language_hint: ja_request_en_query
- api_candidate_count: 5（すべて英語）

**推測:**
- 日本語コンテンツが不足している可能性
- 英語ページの日本語翻訳が不足している可能性

### 7. 現在性（時間依存の場合）
**判断:** タイムリー性が影響していない

**観測事実:**
- time_sensitive: True
- api_candidate_count: 5（最新情報が含まれる可能性）

**推測:**

---

## P02b

- request: 今のRTX 3060の立ち位置を教えて
- language: ja_request_en_query
- api_candidate_count: 5
- returned_count: 5
- non_empty_snippet_count: 0
- ranking_dropped_candidates: 0
- page_has_usable_text: False
- llm_received_count: 5
- llm_received_usable_evidence: no
- observed_search_outcome: return_hits_all_snippet_empty
- suspected_bottlenecks: ['C', 'その他']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が届いていない

**観測事実:**
- return_snippet_nonempty: 0
- llm_received_usable_evidence: no

**推測:**
- snippet空の候補がLLMに渡された可能性
- ページ本文が存在しても抽出失敗の可能性

### 2. API段階に有用候補が存在した可能性
**判断:** APIが有用候補を返した可能性

**観測事実:**
- api_candidate_count: 5
- api_snippet_nonempty: 0

**推測:**
- Wikipediaのページが存在するがsnippet取得失敗
- 検索APIが非日本語コンテンツを優先している可能性

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が失われていない

**観測事実:**
- ranking_dropped_candidates: 0
- return_hits_all_snippet_empty

**推測:**
- ランキングロジックがsnippet空の候補を優先している可能性

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に失敗している

**観測事実:**
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- Wikipediaページの本文取得処理が失敗
- snippet取得APIの制限が発生

### 5. LLM受け渡し段階の問題
**判断:** LLMへの受け渡しに問題はない

**観測事実:**
- llm_handoff_count_match: True
- agent_passes_full_return: True

**推測:**
- LLMがsnippet空の候補を無視している可能性

### 6. 日英差
**判断:** 日本語/英語差異が影響している可能性

**観測事実:**
- language_hint: ja_request_en_query

**推測:**
- 英語コンテンツが日本語検索に不適切
- 日本語のRTX 3060情報が取得できていない

### 7. 現在性（時間依存の場合）
**判断:** タイムリネスが影響している可能性

**観測事実:**
- time_sensitive: True

**推測:**
- 最新情報が取得できていない可能性

---

## C02

- request: Ollamaについて詳しく教えて
- language: ja_request_en_query
- api_candidate_count: 18
- returned_count: 3
- non_empty_snippet_count: 1
- ranking_dropped_candidates: 11
- page_has_usable_text: False
- llm_received_count: 3
- llm_received_usable_evidence: partial
- observed_search_outcome: return_hits_partial_snippet
- suspected_bottlenecks: ['A', 'B', 'その他']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が部分的に提供された

**観測事実:**
- return_snippet_nonempty: 1
- llm_received_hit_count: 3
- json_bytes: 830

**推測:**
- 非空スニペットは1件のみで情報量が限られている可能性

### 2. API段階に有用候補が存在した可能性
**判断:** API候補に有用な情報が存在した

**観測事実:**
- api_snippet_nonempty: 8
- duckduckgo候補にOllamaの説明あり

**推測:**
- 日本語Wikipediaの空スニペットが有用性を低下させた可能性

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が脱落した

**観測事実:**
- ranking_dropped_with_snippet: 4
- 非空スニペットの候補が0スコアで脱落

**推測:**
- スコアリングロジックが日本語コンテンツを優先していない可能性

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に問題なし

**観測事実:**
- extract_probe_page_has_usable_text: False
- Wikipedia抽出結果が空

**推測:**
- 日本語ページの本文取得が失敗している可能性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの受け渡しに問題なし

**観測事実:**
- llm_handoff_count_match: True
- agent_passes_full_return: True

**推測:**

### 6. 日英差
**判断:** 日本語/英語差が影響している

**観測事実:**
- language_hint: ja_request_en_query
- 日本語Wikipediaのスニペットが空

**推測:**
- 英語コンテンツが優先され日本語情報が不足している可能性

### 7. 現在性（時間依存の場合）
**判断:** タイムリネスに影響なし

**観測事実:**
- time_sensitive: False

**推測:**

---

## A03

- request: OpenAIについて最近何か大きな発表はありましたか
- language: ja_request_en_query
- api_candidate_count: 10
- returned_count: 5
- non_empty_snippet_count: 0
- ranking_dropped_candidates: 5
- page_has_usable_text: True
- llm_received_count: 5
- llm_received_usable_evidence: no
- observed_search_outcome: return_hits_all_snippet_empty
- suspected_bottlenecks: ['C', 'その他']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が届いていない

**観測事実:**
- return_snippet_nonempty: 0
- llm_received_usable_evidence: no

**推測:**
- snippet空の候補がLLMに渡された可能性
- 内容取得プロセスで本文が取得されていない可能性

### 2. API段階に有用候補が存在した可能性
**判断:** API候補に有用なコンテンツが含まれていた可能性

**観測事実:**
- extract_probe_page_has_usable_text: True
- api_snippet_nonempty: 0

**推測:**
- snippet取得処理が失敗した可能性
- API候補の本文取得が不完全だった可能性

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用な候補が失われた可能性

**観測事実:**
- ranking_dropped_candidates: 5
- ranking_dropped_with_snippet: 0

**推測:**
- ランキング基準がコンテンツに依存していない可能性
- 有用な候補が過剰表示制限で除外された可能性

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に失敗している可能性

**観測事実:**
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0

**推測:**
- 本文取得プロセスのエラー
- snippet抽出処理の不完全性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの情報伝達に問題がある

**観測事実:**
- llm_received_usable_evidence: no
- agent_passes_full_return: True

**推測:**
- 空のsnippetがLLMに渡された可能性
- 内容取得後の情報伝達が不完全だった可能性

### 6. 日英差
**判断:** 言語差による影響は限定的

**観測事実:**
- language_hint: ja_request_en_query
- api_candidate_count: 10

**推測:**
- 英語コンテンツが優先されても有用な情報が得られなかった可能性

### 7. 現在性（時間依存の場合）
**判断:** タイムリーアクセスが影響している可能性

**観測事実:**
- time_sensitive: True
- observed_search_outcome: return_hits_all_snippet_empty

**推測:**
- 最新情報が取得できていない可能性
- タイムリーアクセスがsnippet取得に影響した可能性

---

## A04

- request: 今のNVIDIAの株価の雰囲気を教えて
- language: ja_request_en_query
- api_candidate_count: 21
- returned_count: 5
- non_empty_snippet_count: 3
- ranking_dropped_candidates: 9
- page_has_usable_text: True
- llm_received_count: 5
- llm_received_usable_evidence: partial
- observed_search_outcome: return_hits_partial_snippet
- suspected_bottlenecks: ['B', 'C', 'その他']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が部分的に届いた

**観測事実:**
- return_snippet_nonempty: 3
- return_snippet_empty: 2
- llm_received_hit_count: 5

**推測:**
- 空のsnippetは株価情報に直接関係しない可能性
- LLMが株価雰囲気を推測するための文脈が不足している

### 2. API段階に有用候補が存在した可能性
**判断:** API候補に有用な情報が含まれていた

**観測事実:**
- api_snippet_nonempty: 11
- search_web return hitsに英語Wikipediaが含まれる

**推測:**
- 日本語Wikipedia候補が検索APIで取得できなかった可能性
- 株価関連情報が英語ページに集中している

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が脱落した可能性

**観測事実:**
- ranking_dropped_with_snippet: 2
- ranking_dropped_total: 9

**推測:**
- 株価関連情報を持つ候補がランキングで優先順位を失った
- 英語ページが日本語ページよりも優先された可能性

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に不完全な部分がある

**観測事実:**
- api_snippet_empty: 10
- extract_probe_page_has_usable_text: True

**推測:**
- 日本語Wikipediaページのsnippet取得が失敗した
- コンテンツ取得処理がページ構造に依存している可能性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの情報伝達に不完全な部分がある

**観測事実:**
- llm_handoff_count_match: True
- llm_received_usable_evidence: partial

**推測:**
- 空のsnippetがLLMの文脈理解に影響を与えた
- 株価情報に直接関係する文脈が不足している

### 6. 日英差
**判断:** 日本語/英語の検索差異が影響している

**観測事実:**
- language_hint: ja_request_en_query
- search_web return hitsに英語ページが含まれる

**推測:**
- 日本語検索で株価情報が取得できなかった可能性
- 英語ページが株価関連情報に特化している

### 7. 現在性（時間依存の場合）
**判断:** タイムリーな情報取得が不十分

**観測事実:**
- time_sensitive: True
- search_web return hitsに時系列情報が含まれていない

**推測:**
- 株価雰囲気に関する最新情報が取得できていない
- 金融情報専門サイトが検索候補から除外されている

---

## C04

- request: ローカルLLMの事情、最近どう？
- language: ja_request_en_query
- api_candidate_count: 10
- returned_count: 2
- non_empty_snippet_count: 1
- ranking_dropped_candidates: 4
- page_has_usable_text: True
- llm_received_count: 2
- llm_received_usable_evidence: partial
- observed_search_outcome: return_hits_partial_snippet
- suspected_bottlenecks: ['A', 'B', 'C', 'その他']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が部分的に提供された

**観測事実:**
- return_snippet_nonempty: 1
- return_snippet_empty: 1
- llm_received_hit_count: 2

**推測:**
- 空のsnippet候補がLLMに渡された可能性
- LLMが部分的な情報のみで推論を実行している

### 2. API段階に有用候補が存在した可能性
**判断:** API候補に有用な情報が含まれていた

**観測事実:**
- api_snippet_nonempty: 8
- extract_probe_page_has_usable_text: True

**推測:**
- Wikipediaのページが有効なテキストを含むがsnippetが空だった
- 検索APIが日本語対応していない可能性

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用な候補が除外された可能性

**観測事実:**
- ranking_dropped_with_snippet: 4
- ranking_dropped_total: 4

**推測:**
- エネルギー関連の候補が不適切なスコアで除外された
- 日本語対応の候補がランキングで優先されなかった

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得で空のsnippetが発生

**観測事実:**
- api_snippet_empty: 2
- return_snippet_empty: 1

**推測:**
- Wikipediaのページがsnippet取得に失敗した
- コンテンツ取得処理が言語設定を無視している

### 5. LLM受け渡し段階の問題
**判断:** LLMへの情報伝達に不完全な点がある

**観測事実:**
- llm_received_usable_evidence: partial
- llm_handoff_count_match: True

**推測:**
- 空のsnippet候補がLLMに渡された可能性
- 日本語対応の情報がLLMに届いていない

### 6. 日英差
**判断:** 日本語と英語の差異が影響している

**観測事実:**
- language_hint: ja_request_en_query
- search_query: large language model

**推測:**
- 日本語のローカルLLMに関する情報が英語候補に含まれていない
- 日本語対応の検索結果が除外された可能性

### 7. 現在性（時間依存の場合）
**判断:** タイムリネスの影響は不明

**観測事実:**
- time_sensitive: True

**推測:**
- 最新情報が検索候補に含まれていない可能性
- タイムリネスフィルターが不適切に動作している

---

## B05

- request: Pythonのリストとタプルの違いを簡単に説明して
- language: ja_request_en_query
- api_candidate_count: 3
- returned_count: 3
- non_empty_snippet_count: 0
- ranking_dropped_candidates: 0
- page_has_usable_text: False
- llm_received_count: 3
- llm_received_usable_evidence: no
- observed_search_outcome: return_hits_all_snippet_empty
- suspected_bottlenecks: ['C', 'A', 'その他']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が届いていない

**観測事実:**
- return_snippet_nonempty: 0
- api_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- URL先に本文が存在する可能性があるが、取得処理で本文が取得されていない

### 2. API段階に有用候補が存在した可能性
**判断:** API候補が有用でない可能性

**観測事実:**
- api_snippet_empty: 3
- return_snippet_empty: 3
- search_query: Python tuple

**推測:**
- 検索クエリがタプルに特化しているため、リストとタプルの比較に必要な情報が含まれていない

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が失われていない

**観測事実:**
- ranking_dropped_total: 0
- ranking_dropped_with_snippet: 0

**推測:**
- ランキングが機能しているが、候補自体が有用でないため問題が生じている

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に失敗している

**観測事実:**
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- Wikipediaの抽出処理で本文が取得できていない可能性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの受け渡しに問題がない

**観測事実:**
- llm_handoff_count_match: True
- agent_passes_full_return: True

**推測:**

### 6. 日英差
**判断:** 日本語と英語の差異が影響している可能性

**観測事実:**
- language_hint: ja_request_en_query
- search_query: Python tuple

**推測:**
- 英語のWikipedia候補が日本語の質問に不適切である

### 7. 現在性（時間依存の場合）
**判断:** タイムリネスの影響はなし

**観測事実:**
- time_sensitive: False

**推測:**

---

## WB02

- request: Dockerコンテナの基本的な考え方を教えて
- language: ja_request_en_query
- api_candidate_count: 14
- returned_count: 5
- non_empty_snippet_count: 5
- ranking_dropped_candidates: 1
- page_has_usable_text: False
- llm_received_count: 5
- llm_received_usable_evidence: yes
- observed_search_outcome: return_hits_all_snippet_nonempty
- suspected_bottlenecks: ['C (コンテンツ取得: Wikipediaページの実際のテキスト不足)', 'B (ランキング: リターン制限による有用候補の除外)']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が受け渡された

**観測事実:**
- return_snippet_nonempty: 5
- llm_received_hit_count: 5
- snippet_len: 400-267 (return hits)

**推測:**
- snippet内容がDockerコンテナの基本概念を含む可能性

### 2. API段階に有用候補が存在した可能性
**判断:** API候補に有用な情報が含まれていた

**観測事実:**
- api_snippet_nonempty: 12
- return_hits_all_snippet_nonempty

**推測:**
- DuckDuckGo候補がDockerコンテナの説明を含む

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が失われた可能性

**観測事実:**
- ranking_dropped_total: 1
- ranking_dropped_with_snippet: 0

**推測:**
- 過剰なリターン制限で有用候補が除外された

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に問題はなかった

**観測事実:**
- api_snippet_nonempty: 12
- return_snippet_nonempty: 5

**推測:**
- Wikipediaのextractが空だがsnippetは生成可能

### 5. LLM受け渡し段階の問題
**判断:** LLMへの受け渡しに問題はなかった

**観測事実:**
- llm_handoff_count_match: True
- agent_passes_full_return: True

**推測:**

### 6. 日英差
**判断:** 言語差による影響は限定的

**観測事実:**
- search_query: Docker (software) (英語)
- return_hits: 英語コンテンツ

**推測:**
- 日本語リクエストに対応するコンテンツが不足

### 7. 現在性（時間依存の場合）
**判断:** タイムリネスの影響はなかった

**観測事実:**
- time_sensitive: False

**推測:**

---

## P02a

- request: RTX 3060について教えて
- language: ja_request_en_query
- api_candidate_count: 5
- returned_count: 5
- non_empty_snippet_count: 0
- ranking_dropped_candidates: 0
- page_has_usable_text: False
- llm_received_count: 5
- llm_received_usable_evidence: no
- observed_search_outcome: return_hits_all_snippet_empty
- suspected_bottlenecks: ['C', 'その他']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が届いていない

**観測事実:**
- return_snippet_nonempty: 0
- api_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- Wikipediaのページが日本語でないため情報が抽出できない可能性
- snippet取得処理がページ本文を正しく取得していない可能性

### 2. API段階に有用候補が存在した可能性
**判断:** APIが有用候補を返していない

**観測事実:**
- api_snippet_nonempty: 0
- api_candidate_count: 5
- all candidates are Wikipedia English pages

**推測:**
- 検索クエリが英語で実行され、日本語対応リソースが不足している可能性
- WikipediaのAPIが日本語コンテンツを提供していない可能性

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が失われていない

**観測事実:**
- ranking_dropped_total: 0
- ranking_dropped_with_snippet: 0

**推測:**
- ランキングロジックが空スニペットを除外していない可能性
- 候補絞り込みがスニペット内容を考慮していない可能性

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得が失敗している

**観測事実:**
- extract_probe_page_has_usable_text: False
- api_snippet_empty: 5
- return_snippet_empty: 5

**推測:**
- Wikipediaページの本文取得処理が機能していない可能性
- スニペット抽出処理がページ本文を正しく解析していない可能性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの情報伝達が不十分

**観測事実:**
- llm_received_usable_evidence: no
- llm_received_hit_count: 5
- json_bytes: 770

**推測:**
- 空スニペットをLLMに渡すことで回答品質が低下している可能性
- LLMが空データを無視している可能性

### 6. 日英差
**判断:** 日本語/英語の差異が影響している

**観測事実:**
- language_hint: ja_request_en_query
- all candidates are Wikipedia English pages

**推測:**
- 日本語対応リソースが不足している可能性
- 英語ページの内容が日本語ユーザーにとって不適切な可能性

### 7. 現在性（時間依存の場合）
**判断:** タイムリネスの影響なし

**観測事実:**
- time_sensitive: False

**推測:**

---

## E02

- request: ChatGPTの有料プランの違いを教えて
- language: ja_request_en_query
- api_candidate_count: 2
- returned_count: 2
- non_empty_snippet_count: 0
- ranking_dropped_candidates: 0
- page_has_usable_text: False
- llm_received_count: 2
- llm_received_usable_evidence: no
- observed_search_outcome: return_hits_all_snippet_empty
- suspected_bottlenecks: ['C', 'A']

### 1. LLMにとって有用な情報を含んでいたか
**判断:** LLMに有用な情報が届いていない

**観測事実:**
- llm_received_hit_count: 2
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- snippet空候補がLLMに渡された可能性
- ページ本文が存在しても抽出失敗の可能性

### 2. API段階に有用候補が存在した可能性
**判断:** API候補に有用なコンテンツが含まれていない

**観測事実:**
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- Wikipediaの記事が非公開/非表示の可能性
- APIが非英語コンテンツを返さない可能性

### 3. rankingで有用候補が失われた可能性
**判断:** ランキングで有用候補が失われていない

**観測事実:**
- ranking_dropped_total: 0
- ranking_dropped_with_snippet: 0

**推測:**
- 候補数が極端に少なかった可能性

### 4. 内容取得に失敗している可能性
**判断:** コンテンツ取得に失敗している

**観測事実:**
- api_snippet_nonempty: 0
- return_snippet_nonempty: 0
- extract_probe_page_has_usable_text: False

**推測:**
- Wikipediaの記事が非公開/非表示の可能性
- APIが非英語コンテンツを返さない可能性

### 5. LLM受け渡し段階の問題
**判断:** LLMへの受け渡しに問題がない

**観測事実:**
- llm_handoff_count_match: True

**推測:**
- LLMが空snippetを処理する仕様の可能性

### 6. 日英差
**判断:** 日本語/英語の差異が影響している可能性

**観測事実:**
- language_hint: ja_request_en_query
- search_query: ChatGPT Plus (英語)

**推測:**
- 日本語検索で英語コンテンツが取得できない可能性

### 7. 現在性（時間依存の場合）
**判断:** タイムリネスの影響はなさそう

**観測事実:**
- time_sensitive: False

**推測:**

---
