# search_web 現行コード経路の原因調査（実装変更なし）

調査日の文脈: Web効果レビューで「hits はあるが本文が空」が多発した現象の切り分け。  
**本ドキュメントは調査報告のみ。search_web / Agent / heuristic / Gate / Pipeline / Stage3/4 は変更していない。**

---

## ① 現在の search_web の全体フロー

Agent 公開 Tool の `search_web` は、Tool Builder 用 `research.web.search_web`（MS Learn 優先）とは**別経路**である。

```text
ユーザー要求
  ↓
（Agent本番）LLMが tool_call で query を決定
（レビューハーネス）LLMが英語百科寄りクエリを1行生成 + seed + 原文（再試行あり）
  ↓
tools.system.network.search_web.search_web(query, limit?)
  ↓
tools.system.network.general_web_search.general_web_search(...)
  ↓
並列ではないが順に3バックエンド:
  1. DuckDuckGo Instant Answer API  (search_duckduckgo)
  2. 日本語 Wikipedia OpenSearch     (search_wikipedia → ja.wikipedia.org)
  3. 英語 Wikipedia OpenSearch       (search_wikipedia_en → en.wikipedia.org)
  ↓
各 backend の HTTP GET → JSON パース → compact_hit(title, snippet, url, backend)
  ↓
title または snippet があるものだけ収集
  ↓
rank_hits_for_query（クエリ語の title/snippet 一致スコア）で上位 return_limit 件
  ↓
戻り値 dict { query, hits[], backends_tried, error, fetch_limit, return_limit, ... }
  ↓
（Agent）execute_tool → messages に raw JSON を tool ロールで追加 → LLM が最終回答
（レビューハーネス）hits JSON を user メッセージに埋め込んで完成回答生成
```

**ページURLへの二次アクセス（本文スクレイピング）はコード上存在しない。**

---

## ② 使用している検索技術

| 項目 | 内容 |
|------|------|
| Agent入口 | `tools/system/network/search_web.py` → `search_web()` |
| 実装本体 | `tools/system/network/general_web_search.py` → `general_web_search()` |
| 共有HTTP/パース | `tools/system/tool_builder/research/web.py` の `http_get`, `compact_hit`, `search_duckduckgo`, `search_wikipedia` |
| 方式 | **HTTP GET + JSON API**（SDKなし、スクレイピングなし） |
| DDG | `https://api.duckduckgo.com/?q=...&format=json&no_redirect=1&no_html=1`（Instant Answer） |
| Wikipedia JA | `https://ja.wikipedia.org/w/api.php?action=opensearch&...` |
| Wikipedia EN | `https://en.wikipedia.org/w/api.php?action=opensearch&...` |
| User-Agent | Chrome 風固定文字列（`USER_AGENT`） |
| Accept-Language | **未設定** |
| タイムアウト | `REQUEST_TIMEOUT = 12` 秒 |
| リトライ | **search_web 本体には無し**（例外は backend 単位で errors に蓄積） |
| 認証 / APIキー | **無し**（公開API） |
| 件数 | 既定 `return_limit=5`, `fetch_limit=5` |
| 地域・日付指定 | **無し** |
| セーフサーチ | **無し** |

※ Tool Builder 用 `research.web.search_web` は learn.microsoft を含むが、Agent の `search_web` はこれを呼ばない（テストで明示）。

---

## ③ 検索結果取得（何を取っているか）

各 hit は次の4フィールドのみ（`compact_hit`）:

```python
{
  "title":   str[:200],
  "snippet": str[:400],   # ここが「本文」相当。ページ全文ではない
  "url":     str[:300],
  "backend": "duckduckgo" | "wikipedia" | "wikipedia-en",
}
```

取得元:

| フィールド | DuckDuckGo | Wikipedia OpenSearch |
|------------|------------|----------------------|
| title | Heading / RelatedTopics Text | payload[1] titles |
| snippet | AbstractText / RelatedTopics Text | payload[2] descriptions |
| url | AbstractURL / FirstURL | payload[3] urls |

**一般的な「検索エンジンの10件SERP」ではない。** DDG Instant Answer は抽象・関連トピックがある場合のみ、Wikipedia はタイトル候補リスト＋（あれば）短い description。

---

## ④ 本文取得

**していない。**

- 検索結果 URL への追加 HTTP GET なし
- HTML パーサ / readability / JS レンダリングなし
- robots / Cloudflare 対策なし（ページを取りに行かないため）

したがってレビュー上の「内容なし」は多くの場合:

> 検索ヒット（title+url）は返ったが、APIが返した snippet/description が空文字

という意味であり、「ページに本文があるのに落とした」とは限らない（ページ本文は最初から取得対象外）。

---

## ⑤ LLMへの受け渡し

### Agent本番（`agent.py`）

1. `execute_tool("search_web", arguments)` → `function(**arguments)` の **raw dict**
2. `messages` に `role=tool`, `content=json.dumps(result)` で**全文**を渡す  
   （stdout の `summarize_tool_result` は表示専用。LLM経路は raw）
3. LLM は `hits[].title/snippet/url` を見て最終回答

確認済み事実: raw を削って空にする中間変換は Agent 側に見当たらない。

### レビューハーネス（`run_web_effect_pilot.py`）

- hits を JSON で user メッセージに埋め込み
- 保存時は `title/url/snippet` のみ（`backend` は落ちる）→ 観測上 backend=None になり得る

---

## ⑥ error / empty_hits / hits の定義

観測側（`capability_route_obs.classify_search_web_outcome`）:

| ラベル | 条件 |
|--------|------|
| `blocked` | `blocked_by_agent_tool_gate` |
| `error` | `result.error` が truthy |
| `empty_hits` | error なし かつ `hits == []` |
| `hits` | error なし かつ `len(hits) > 0` |
| `other` | 上記以外 |

実装側（`general_web_search`）の重要な挙動:

- **hits が1件でもあれば `error=None`**（たとえ全 snippet が空でも）
- hits が0のときだけ `error` に  
  - backend 例外の連結文字列（例: `wikipedia-ja: HTTPError: ... 429 ...`）  
  - または `"検索結果がありません"`
- 収集条件: `title or snippet` があれば採用 → **titleのみ・snippet空も hits になる**

したがって:

```text
「検索結果0件」≠「本文（snippet）なし」
「hits」≠「LLMに使える本文がある」
「error」には 429 / タイムアウト / JSON失敗 / 全backend空 が混在し得る
```

`empty_hits` と「snippet空の hits」は**別物**。後者は outcome=`hits` のままレビューで「内容なし」と見える。

---

## ⑦ 「内容なし」が発生する場所

```text
検索API応答
  ↓  ★ Wikipedia OpenSearch の description がしばしば空
  ↓  ★ DDG Instant Answer に Abstract が無いクエリが多い
パース (compact_hit)
  ↓  snippet="" をそのまま格納（破棄ではない。空のまま保持）
本文取得
  ↓  ★ 段階自体が存在しない（ここが最大の構造要因）
Agent受け渡し
  ↓  raw を渡す（空snippetをさらに消す処理は見当たらない）
LLM
  ↓  title/url と空snippetを受け取り、「内容なし」と答える／公式サイトへ誘導
```

**強く疑われる箇所（コード根拠あり）:**  
「検索結果は存在するが、取得しているのがSERP要約相当であり、しかもその要約が空でも hit として残る」＋「URL先本文を取らない」。

Agent受け渡しで内容が消えている可能性は、現状のコード根拠では**低い**。

---

## ⑧ 日本語検索の扱い

| 観点 | コード事実 |
|------|------------|
| 日本語→英語の自動翻訳 | **search_web 本体には無し**（クエリをそのまま送る） |
| 日本語専用バックエンド | `wikipedia-ja`（`ja.wikipedia.org`）を常に試行 |
| 英語バックエンド | `wikipedia-en` も常に試行 |
| ランキング | クエリにCJKがあり hit 側にもCJKがあると +1 |
| Accept-Language | 未設定 |
| レビューハーネスのみ | `_suggest_search_query` が「英語の固有名詞・百科事典向けを優先」と指示 → ログ上クエリが英語化しやすい |

既存ログ例:

- B05: 要求は日本語 → クエリ `Python tuple`（英語）
- C04: 要求「ローカルLLMの事情、最近どう？」→ `large language model`
- E04系: 日本語クエリもあり得るが、成功バッチでは英語百科寄りが多い

**日本語ページの本文抽出処理は存在しない**（本文取得自体が無い）。

---

## ⑨ 429 等の扱い

`http_get` は `urllib.request.urlopen`。HTTPエラーは `HTTPError` として backend の `except` に入り、`errors` に文字列追加。

- **ステータスコード別の専用分岐（429だけ待つ等）は search_web 本体に無し**
- hits が他 backend から取れれば、429 が errors に残っても最終 `error=None` になり得る
- レビューハーネス `search_until_hits` のみ、エラー文字列に `429` があれば追加 sleep（本体ではない）

既存 `web_effect_review_hits.json`（hits確保後の25件）では、最終結果に hits があるケースが多く、attempts 内429カウントはケース依存。初回パイロットや失敗マニフェストには Wikipedia 429 が記録されている（例: `HITS_BATCH_REPORT` / failed attempts）。

**429は低HIT率の一因になり得るが、「hitsはあるが内容なし」現象の主因ではない**（主因は snippet空＋本文未取得）。

---

## ⑩ 既存ログとの照合（代表）

出典: `web_effect_review_hits.json`（25件集計: hits合計100、**snippet空53 / 有47**）

### 1) content空（hitsだが本文なし）— B05

```text
request: Pythonのリストとタプルの違いを簡単に説明して
query:   Python tuple
HTTP:    backends duckduckgo / wikipedia-ja / wikipedia-en（error=None）
parsed:  3 hits, titleあり, snippet 全て空
LLM入力: title+url+空snippet
final:   Webなしと同系統の一般説明（検索本文に依存していない）
```

### 2) 英語本文あり — C02

```text
query: Ollama
hits:  英語Wikipedia系 snippet あり（383文字）＋他は空
→ 稀に「使える本文」がAPIから返る例
```

### 3) hitsだが質問とズレ — A06

```text
query: Python 3.13
hit:   title=Python 3.0, snippet空
→ 「ヒットした」≠「正しいページの要約が取れた」
```

### 4) 英語snippetありでも質問に足りない — A04 / C04

```text
A04 NVIDIA: 会社概要の英語snippetはあるが株価「今」の情報ではない
C04: large language model の一般定義は取れるが「ローカルLLM最近」ではない
```

### 5) 全滅snippet空 — P02a / E02

```text
GeForce RTX 3060 / ChatGPT Plus → title一覧のみ、snippet空
outcome上は hits（error=None）
```

---

## ⑪ 原因候補ランキング

| 優先度 | 原因候補 | 根拠 | 確信度 |
|--------|----------|------|--------|
| **高** | **URL先のページ本文を取得していない**（検索APIの短文snippetのみ） | `general_web_search` / `compact_hit` にページfetch無し。コード全体を通読しても二次GET無し | **高** |
| **高** | **Wikipedia OpenSearch の description が空でも title+url で hit になる** | `title or snippet` で収集。ログで titleあり・snip_len=0 が多数 | **高** |
| **高** | **DuckDuckGo Instant Answer は汎用Web検索ではなく、Abstractが無いクエリが多い** | `api.duckduckgo.com` + AbstractText/RelatedTopics のみ | **高** |
| 中 | レビューハーネスが英語百科クエリを優先し、意図とズレたページが選ばれやすい | `_suggest_search_query` のプロンプト。本体の自動英訳ではない | 中 |
| 中 | ranking が空snippetでも title一致で上位に残す | `score_hit_for_query` は title マッチに加点 | 中 |
| 中 | 429等で Wikipedia が一時失敗し候補が減る | errors に HTTP 429。ただし「内容なしhits」の主因ではない | 中 |
| 低 | AgentがLLMへ渡す前にsnippetを落とす | raw `json.dumps(result)` を messages に追加。削る処理なし | 低（反証寄り） |
| 低 | 「検索サービスが全面的に壊れている」 | 一部ケースでは数百文字の英語snippetが取れている（C02等） | 低 |

**断定しないが、コードとログが揃って示す構造:**

> 問題の多くは「検索結果が0件」ではなく、**「検索ヒット（title/url）は返るが、取得している情報源が薄い／空のsnippetであり、ページ本文も取っていない」**。

---

## ⑫ 次に必要な最小検証（実装変更なしで可能な順）

1. **同一クエリで生API応答を保存**  
   DDG / wiki-ja / wiki-en の JSON をファイルに落とし、`payload[2]`（wiki description）と `AbstractText` が空かを確認（search_webは触らず、調査用ワンショットスクリプト可）。
2. **OpenSearch title に対応する Wikipedia extracts API を手で1回叩く**  
   同じ title で extracts が取れるなら、「ページには本文があるが現行コードが取っていない」が実証できる。
3. **snippet空 hit の比率を既存25件で再集計**（既に ≈53/100）— 再現性確認。
4. **日本語クエリ vs 英語クエリを各3件だけ**、同一トピックで snippet 有無を比較（大量再生成は不要）。
5. 上記で「APIが空を返す」vs「APIに文があるのに捨てている」を切り分けた後に初めて、改善候補（本文取得追加 / extracts / 別検索API / 空snippetの扱い）を検討する。

---

## 確認済み事実 / 強く疑われる箇所 / 未確認

### 確認済み事実

- Agent `search_web` = `general_web_search`（MS Learn 経路ではない）
- 取得物は title / snippet(≤400) / url / backend のみ
- ページ本文の二次取得は無い
- titleのみでも hits になり `error=None`
- LLMへは Agent 上 raw JSON が渡る
- 既存hitsログで snippet空が過半数

### 強く疑われる箇所

- Instant Answer + OpenSearch という情報源選択そのもの
- 空 description を「有効hit」として残す収集条件
- （レビュー時）英語百科クエリ優先によるミスマッチ

### まだ確認できない箇所

- 本番Agent実行時の tool_call クエリ分布（レビューハーネスと同一とは限らない）
- 各backendの瞬間的な429頻度の定量（環境・時刻依存）
- 「ブラウザで開くと本文がある」ことの体系的証明（上記⑫-2で確認可能）

---

## 改善提案（実装はしない・方向のみ）

確信度の高い順の**候補**（今回は実装禁止）:

1. ヒットURLまたは Wikipedia pageid から **extracts / 要約文を追加取得**する段階を検討する  
2. snippet空の hit を LLM に「有用ヒット」として渡さない／別ラベルにする  
3. Instant Answer以外の検索バックエンドの要否を検証する  
4. 時間依存クエリ（「今」「最近」）をクエリ生成でどう扱うかは、検索本体とは別問題として切り分ける

**「検索サービスを変えれば全部直る」とはまだ言わない。** まず⑫の最小検証で「空snippetの原因がAPI側か取得設計か」を確定するのが次手。
