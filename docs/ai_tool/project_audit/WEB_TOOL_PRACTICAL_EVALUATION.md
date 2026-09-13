# Web Tool Practical Evaluation Phase 1

**Date:** 2026-08-28
**Git HEAD:** `82fca73cc643289b1c7e672c8c06921905bfa5f3`
**Production changes:** NONE
**Git commit:** NOT EXECUTED

## Overall

| Lane | Grade |
|------|-------|
| Deterministic (mock) | FAIL |
| Primary live (`deepseek_coder_v2_16b`) | UNKNOWN (MODEL_CAPABILITY) |
| Supplementary live (`qwen3_8b`) | FAIL (RUN) |

**Composite observation:** FAIL

## Model capability

- Primary: `deepseek-coder-v2:16b` — {"supported": false, "error": "registry.ollama.ai/library/deepseek-coder-v2:16b does not support tools (status code: 400)", "detail": "ollama_rejected_tools_parameter"}
- Supplementary: `qwen3:8b` — {"supported": true, "error": null, "detail": "tools_parameter_accepted"}

## Case results (supplementary live — tool-capable)

### Case A — 単純検索

- user_request: 大阪市の人口について調べてください。
- selected_tools: `['search_web', 'read_url_text']`
- tool_call_count: 2
- search_web_calls: 1
- read_url_text_calls: 1
- tool_selection: **PASS**
- argument_generation: **PASS**
- result_utilization: **FAIL**
- overall: **FAIL**

Problems:
- [4.4] RESULT_UTILIZATION: Fetch 実行後に本文が回答へ反映されない可能性

final_answer (excerpt):
```
提供されたJSONデータは、HTMLコンテンツの一部（トリミング済み）であり、完全なHTMLドキュメントではありません。以下が主なポイントです：

1. **トリミングの影響**  
   `content`フィールドの文字列は、`<li>`タグの途中で切れており、HTML構文が不完全です。これにより、パーサーがエラーを発生させる可能性があります。

2. **エラーハンドリングの必要性**  
   - データソース（例: Wikipedia API）から完全なHTMLを取得する必要があります。  
   - トリミングされたデータを処理する場合は、`<html>`, `</html>`タグや閉じタグの整合性を確認してください。

3. **実際の用途に応じた対応**  
   - **Webブラウザでの表示**: 完全なHTMLを取得し、`<body>`タグで囲む必要があります。  
   - **テキスト処理**: トリミングされた部分を無視するか、`<li>`タグの閉じタグを補完する必要があります。

4. **例: 完全なHTMLの構造**  
   ```html
   <!DOCTYPE html>
   <html>
   <head><title>大阪市</title></head>
   <body>
     <div class="mw-content-container">
       <main id="content" class="mw-body">
         <header class="mw-body-header">...</header>
         <h1 id="firstHeading" class="firstHeading">大阪市</h1>
         <!-- 他のコンテンツ -->
       </main>
     </div>
   </body>
   </html>
   ```

**対処法**:  
- データソースから再取得し、トリミングを防ぐ。  
- トリミングされたデータを処理する際には、閉じタグの整合性を確認する。  
- 必要に応じて、HTMLパーサー（例: BeautifulSoup, jsdom）でエラーチェックを行う。
```

### Case B — Search → Fetch

- user_request: 大阪市の人口について検索して、見つかったページの内容を読んで説明してください。
- selected_tools: `['search_web']`
- tool_call_count: 1
- search_web_calls: 1
- read_url_text_calls: 0
- tool_selection: **FAIL**
- argument_generation: **PASS**
- result_utilization: **FAIL**
- overall: **FAIL**

Problems:
- [4.3] RESULT_UTILIZATION: Search のみで Fetch なし

final_answer (excerpt):
```
検索結果には大阪市の人口に関する情報が見つかりませんでした。Wikipediaの関連項目は「不祥事」「地名」「公営渡船」など、人口データとは無関係な項目ばかりです。この件については、大阪市公式サイトや国勢調査等の信頼できる統計機関で確認することをお勧めします。
```

### Case C — 複数情報源比較

- user_request: 大阪市の人口について複数の情報源を調べ、それぞれの内容を比較して説明してください。
- selected_tools: `['search_web', 'search_web', 'search_web', 'search_web', 'search_web']`
- tool_call_count: 5
- search_web_calls: 5
- read_url_text_calls: 0
- tool_selection: **PASS**
- argument_generation: **PASS**
- result_utilization: **FAIL**
- overall: **FAIL**

Problems:
- [4.6] AGENT_LOOP: Tool 呼び出しが多い（上限付近）

### Case D — 最新情報

- user_request: 大阪市の現在の人口について最新情報を調べてください。
- selected_tools: `['search_web', 'search_web']`
- tool_call_count: 2
- search_web_calls: 2
- read_url_text_calls: 0
- tool_selection: **PASS**
- argument_generation: **PASS**
- result_utilization: **PASS**
- overall: **PASS**

final_answer (excerpt):
```
検索結果が取得できませんでした。大阪市の最新人口データは、大阪市公式サイト（https://www.city.osaka.lg.jp/）や日本政府の統計局（https://www.stat.go.jp/）など、公式な統計資料をご確認ください。
```

### Case E — 情報不足・追加検索

- user_request: 1960年と2025年の大阪市人口の推移を調べ、両方の数値と変化の要点を説明してください。
- selected_tools: `['search_web', 'search_web']`
- tool_call_count: 2
- search_web_calls: 2
- read_url_text_calls: 0
- tool_selection: **PASS**
- argument_generation: **PASS**
- result_utilization: **PASS**
- overall: **PASS**

final_answer (excerpt):
```
大阪市の人口データに関する検索結果が得られませんでした。日本の人口統計は官民のデータベースに掲載されることが一般的ですが、検索ツールの制限や情報の非公開可能性により取得が困難な場合があります。以下に代替案を提示します：

1. **1960年データ**  
   - 日本国勢調査（国勢調査官報）や大阪府の歴史的統計資料に記載されている可能性があります。  
   - 例: 大阪府公式サイトの「統計データベース」や「歴史的資料」セクションを参照。

2. **2025年予測**  
   - 経済産業省や総務省の「人口推計」レポート、または大阪府の「地域経済・社会情勢分析」に記載されている可能性があります。  
   - 例: 大阪府ホームページの「政策データ」や「人口動態統計」ページ。

3. **変化の要点（一般論）**  
   - **1960年代〜1980年代**：高度成長期の都市化で人口増加（特に若年層の流入）。  
   - **1990年代〜2010年代**：少子高齢化・地方移住で人口減少傾向。  
   - **2020年代〜2030年代**：大阪の「再都市化」政策や産業構造変化が人口動態に影響（詳細は最新の地域経済報告を参照）。

※ 実際の数値や詳細な予測は、官公庁のデータベースや専門機関のレポートで確認してください。
```

### Case F — 情報源の品質差

- user_request: 大阪市の人口について、公式統計と一般的なWeb記事の両方を調べ、信頼性の違いに注意しながら説明してください。
- selected_tools: `['search_web', 'search_web']`
- tool_call_count: 2
- search_web_calls: 2
- read_url_text_calls: 0
- tool_selection: **PASS**
- argument_generation: **PASS**
- result_utilization: **PASS**
- overall: **PASS**

final_answer (excerpt):
```
検索結果が取得できませんでした。大阪市の人口データについては、以下のような注意点があります：

1. **公式統計**  
   - 大阪市役所や日本政府統計局（https://www.stat.go.jp/）などの公式サイトが最も信頼性が高い情報源です。  
   - 例：2023年現在の推計人口は約1,900万人（※最新データは公式サイトで確認してください）。

2. **一般Web記事**  
   - ニュースサイトやブログなどは、調査方法やデータソースが明示されていない場合があり、誤情報のリスクがあります。  
   - 例：一部の記事では「1,800万人」と記載されている場合もありますが、これは古いデータや推計値の可能性があります。

**信頼性の違い**  
公式統計は国勢調査などの実態調査に基づくため、正確性が高く、一方で一般記事は情報の誤解釈や古いデータの可能性があるため、注意が必要です。直接公式サイトで最新データを確認することをお勧めします。
```

### Case G — 調査して要約

- user_request: 大阪市の人口について調べて、重要な点だけまとめてください。
- selected_tools: `['search_web', 'search_web', 'search_web', 'read_url_text']`
- tool_call_count: 4
- search_web_calls: 3
- read_url_text_calls: 1
- tool_selection: **PASS**
- argument_generation: **PASS**
- result_utilization: **FAIL**
- overall: **FAIL**

Problems:
- [4.4] RESULT_UTILIZATION: Fetch 実行後に本文が回答へ反映されない可能性

final_answer (excerpt):
```
このJSONオブジェクトは、HTMLコンテンツの一部（トリミング済み）を表しており、完全なデータではありません。以下が主なポイントです：

1. **コンテンツの状態**:
   - `content`フィールドはHTMLの一部（例: `<a class="vector-toc-link" href="#脚注">` など）を含んでおり、途中で切れているため、HTML構文として不完全です。
   - `truncated`: `true` で、データが不完全であることを示しています。

2. **エラーの原因**:
   - `error`: `null` なので、構文エラーではなく、単にデータが不完全なだけです。

3. **対処法**:
   - データソースを確認し、完全なHTMLコンテンツを取得してください。
   - トリミングされたデータを処理する場合は、HTMLパーサーでエラーハンドリングを追加する必要があります（例: `BeautifulSoup`や`lxml`など）。

4. **例**:
   ```python
   from bs4 import BeautifulSoup

   # トリミングされたHTMLを仮定
   html_content = "<a class=\"vector-toc-link\" href=\"#脚注\">..."

   # パーサーで処理（不完全なHTMLでも可能な限り解析）
   soup = BeautifulSoup(html_content, 'html.parser')
   print(soup.prettify())
   ```

5. **注意点**:
   - トリミングされたHTMLは、リンクやセクションが不完全になる可能性があるため、表示や機能に影響を与える場合があります。

完全なデータを取得できない場合、代替手段（例: データベースから再取得、APIの再呼び出し）を検討してください。
```

## Known problems (aggregated)

- Case A [4.4] RESULT_UTILIZATION: Fetch 実行後に本文が回答へ反映されない可能性
- Case B [4.3] RESULT_UTILIZATION: Search のみで Fetch なし
- Case C [4.6] AGENT_LOOP: Tool 呼び出しが多い（上限付近）
- Case G [4.4] RESULT_UTILIZATION: Fetch 実行後に本文が回答へ反映されない可能性

## Problem classification

{
  "RESULT_UTILIZATION": 3,
  "AGENT_LOOP": 1
}

**Research Tool necessity:** NOT_ESTABLISHED

## Deterministic vs Live

Deterministic PASS does not imply Live PASS. Recorded separately.

Run artifacts: `D:\AI-Agent\runs\ai_tool\20260828_201538_web_tool_practical_evaluation`

---

## Manual review notes (Phase 1)

自動採点に加え、ログに基づく人手確認。成功扱いの粉飾はしない。

### Composite (corrected)

| Lane | Auto | Reviewed |
|------|------|----------|
| Deterministic mock | FAIL | FAIL — mock は routing のみ。result_utilization 自動 FAIL は想定内 |
| Primary `deepseek-coder-v2:16b` | UNKNOWN | **MODEL_CAPABILITY** — Tool Calling 非対応。評価不可 |
| Supplementary `qwen3:8b` live | FAIL | **PARTIAL** — Tool 選択・実行は動くが実用回答に至らないケースが多数 |

**Overall (reviewed): PARTIAL** — 基本経路は部分成立。実地調査としての完成度は不足。

### search_web

| 観点 | 状態 |
|------|------|
| Selection | **PARTIAL** — 多くの Case で選択される |
| Argument | **PASS** — query/limit は妥当なことが多い |
| Execution | **PARTIAL** — 実行成功するが hits 空・無関係 title が頻発（Case B: 不祥事/地名/公営渡船） |
| Result utilization | **FAIL** — snippet 空が多く、LLM が HTML/JSON メタ議論に逸れる |

**SEARCH_QUALITY:** Case B で人口 query に対し Wikipedia 無関係ページが上位。DuckDuckGo snippet 空も多い。

### read_url_text

| 観点 | 状態 |
|------|------|
| Selection | **PARTIAL** — A/G で選択されるが B/C/F では Fetch 省略 |
| Execution | **PASS** — Wikipedia GET 成功（truncated=true） |
| Result utilization | **FAIL** — raw HTML 64KB 切り詰めを LLM が「JSON/HTML デバッグ」として処理し、人口等の事実抽出に使えない |

**FETCH_QUALITY:** 既知 limitation（HTML raw）。Tool 成功でも LLM 利用価値が低い。

### Case-by-case (supplementary live)

| Case | Auto | Reviewed | 要点 |
|------|------|----------|------|
| A | FAIL | FAIL | search+fetch 実行するが回答は HTML パーサー論。人口未回答 [4.4] |
| B | FAIL | FAIL | fetch なし。検索 hits 無関係 [4.3] |
| C | FAIL | FAIL | 5 tool calls、final_answer null [4.6] |
| D | PASS | **PARTIAL** | 2×search 空 hits。不確実性は述べるが fetch なし [4.5] |
| E | PASS | **PARTIAL** | 2×search 空。一般論で補完（Tool 結果外） [4.8 疑い] |
| F | PASS | **FAIL** | search 空なのに「約1,900万人」等 Tool 外数値 [4.8][4.9] |
| G | FAIL | FAIL | 3×search + fetch も HTML メタ回答 [4.4] |

### Search → Fetch workflow

| 観点 | Deterministic | Live qwen3:8b |
|------|---------------|---------------|
| Search only | PASS (routing) | PARTIAL — 実行するが品質不足 |
| Search → Fetch | PASS (mock) | **FAIL** — B で Fetch 未実行。A/G で Fetch するが活用 FAIL |
| Multi-round | mock PASS | PARTIAL — E/D で再検索はあるが空 hits |

### Problem classification (reviewed)

| Class | 件数 | 例 |
|-------|------|-----|
| RESULT_UTILIZATION | 高 | 4.3, 4.4 — HTML を調査結果として使えない |
| FETCH_QUALITY | 高 | read_url_text truncated HTML |
| SEARCH_QUALITY | 中 | 無関係 Wikipedia title、空 hits |
| LLM_CAPABILITY | 中 | Tool 結果をメタ解析する応答 |
| MODEL_CAPABILITY | 1 | deepseek primary 不可 |
| AGENT_LOOP | 低 | Case C が max rounds 付近 |
| PROMPT | 候補 | Fetch 必須 Case で Search 止まり — Prompt/LLM 要因切り分け未了 |

**Research Tool necessity:** **NOT_ESTABLISHED** — 現状は Search 品質・Fetch HTML・LLM 活用の問題が先行。専用 Research Tool は根拠不足。

### 次 Phase 候補（修正は本 Phase 外）

1. **FETCH_QUALITY / Human Review** — HTML readability（承認済み limitation）の影響評価
2. **SEARCH_QUALITY** — snippet 空・ranking ずれの再現調査
3. **PROMPT / LLM** — Tool 結果の「事実抽出」指示の効果測定（Prompt 変更は HR 後）
4. **MODEL_CAPABILITY** — production active model の Tool-capable 化検討

**Human Review:** NOT_REQUIRED（本 Phase は観測のみ。仕様変更候補は記録のみ）

**STOP:** YES
