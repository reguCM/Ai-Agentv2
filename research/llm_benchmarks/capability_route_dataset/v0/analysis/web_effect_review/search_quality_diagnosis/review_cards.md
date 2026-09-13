# 検索品質診断 — 人間レビューカード

自動有用性判定は行っていません。

## CASE: A06

**質問:** Python 3.13で追加された主な変更点を教えて
**検索クエリ:** Python 3.13
**時間依存:** いいえ

### 段階件数（機械観測・事実のみ）

```text
API生: 1
hit化: 1
unique後: 1
ranking後: 1
return: 1
LLM受領: 1
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [wikipedia-en]
- タイトル: Python 3.0
- URL: https://en.wikipedia.org/wiki/Python_3.0
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）


### 調査専用: Wikipedia extracts（snippet空候補）

- Python 3.0: extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: E04

**質問:** 日本の運転免許は一般にどう取得されるか教えて
**検索クエリ:** 普通自動車免許
**時間依存:** いいえ

### 段階件数（機械観測・事実のみ）

```text
API生: 2
hit化: 2
unique後: 2
ranking後: 2
return: 2
LLM受領: 2
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [wikipedia-ja]
- タイトル: 普通自動車免許
- URL: https://ja.wikipedia.org/wiki/%E6%99%AE%E9%80%9A%E8%87%AA%E5%8B%95%E8%BB%8A%E5%85%8D%E8%A8%B1
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [wikipedia-ja]
- タイトル: 普通自動車第一種運転免許
- URL: https://ja.wikipedia.org/wiki/%E6%99%AE%E9%80%9A%E8%87%AA%E5%8B%95%E8%BB%8A%E7%AC%AC%E4%B8%80%E7%A8%AE%E9%81%8B%E8%BB%A2%E5%85%8D%E8%A8%B1
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）


### 調査専用: Wikipedia extracts（snippet空候補）

- 普通自動車免許: extract_len=0 page_has_usable_text=False
- 普通自動車第一種運転免許: extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: C03

**質問:** RTX 3060って今どういう扱いですか？
**検索クエリ:** GeForce RTX 3060
**時間依存:** はい

### 段階件数（機械観測・事実のみ）

```text
API生: 5
hit化: 5
unique後: 5
ranking後: 5
return: 5
LLM受領: 5
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [wikipedia-en]
- タイトル: GeForce RTX 3060
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_3060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [wikipedia-en]
- タイトル: GeForce RTX 5070
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_5070
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [wikipedia-en]
- タイトル: GeForce RTX 4050
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_4050
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 4 [wikipedia-en]
- タイトル: GeForce RTX 2060
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_2060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 5 [wikipedia-en]
- タイトル: GeForce GTX 1060
- URL: https://en.wikipedia.org/wiki/GeForce_GTX_1060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）


### 調査専用: Wikipedia extracts（snippet空候補）

- GeForce RTX 3060: extract_len=0 page_has_usable_text=False
- GeForce RTX 5070: extract_len=0 page_has_usable_text=False
- GeForce RTX 4050: extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: P02b

**質問:** 今のRTX 3060の立ち位置を教えて
**検索クエリ:** GeForce RTX 3060
**時間依存:** はい

### 段階件数（機械観測・事実のみ）

```text
API生: 5
hit化: 5
unique後: 5
ranking後: 5
return: 5
LLM受領: 5
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [wikipedia-en]
- タイトル: GeForce RTX 3060
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_3060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [wikipedia-en]
- タイトル: GeForce RTX 5070
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_5070
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [wikipedia-en]
- タイトル: GeForce RTX 4050
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_4050
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 4 [wikipedia-en]
- タイトル: GeForce RTX 2060
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_2060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 5 [wikipedia-en]
- タイトル: GeForce GTX 1060
- URL: https://en.wikipedia.org/wiki/GeForce_GTX_1060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）


### 調査専用: Wikipedia extracts（snippet空候補）

- GeForce RTX 3060: extract_len=0 page_has_usable_text=False
- GeForce RTX 5070: extract_len=0 page_has_usable_text=False
- GeForce RTX 4050: extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: C02

**質問:** Ollamaについて詳しく教えて
**検索クエリ:** Ollama
**時間依存:** いいえ

### 段階件数（機械観測・事実のみ）

```text
API生: 18
hit化: 15
unique後: 14
ranking後: 3
return: 3
LLM受領: 3
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [duckduckgo]
- タイトル: Ollama
- URL: https://en.wikipedia.org/wiki/Ollama
- snippet: Ollama is an open-source software platform developed by Jeffrey Morgan and Michael Chiang in 2023 for running and managing large language models on local computers and through hosted cloud models. It provides a command-line interface, a native GUI, a local REST API, model-management tools, and integrations for using open-weight models with coding assistants and other applications.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [duckduckgo]
- タイトル: Generative artificial intelligence - Generative artificial intelligence is a subfield of artificial intelligence that uses generative models to generate text, images, videos, audio, software code or other forms of data.
- URL: https://duckduckgo.com/Generative_AI
- snippet: Generative artificial intelligence - Generative artificial intelligence is a subfield of artificial intelligence that uses generative models to generate text, images, videos, audio, software code or other forms of data.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [duckduckgo]
- タイトル: llama.cpp - llama.cpp is an open-source software library that performs inference on various large language models such as Llama. It is co-developed alongside the GGML project, a general-purpose tensor library. Command-line tools are included with the library, alongside a server with a simple web interface.
- URL: https://duckduckgo.com/llama.cpp
- snippet: llama.cpp - llama.cpp is an open-source software library that performs inference on various large language models such as Llama. It is co-developed alongside the GGML project, a general-purpose tensor library. Command-line tools are included with the library, alongside a server with a simple web interface.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 4 [duckduckgo]
- タイトル: LM Studio — desktop application for locally running and interacting with LLMs .
- URL: https://duckduckgo.com/LM_Studio
- snippet: LM Studio — desktop application for locally running and interacting with LLMs .

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 5 [duckduckgo]
- タイトル: Native app See related meanings for the phrase 'Native app'.
- URL: https://duckduckgo.com/d/Native_app
- snippet: Native app See related meanings for the phrase 'Native app'.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 6 [duckduckgo]
- タイトル: SGLang - SGLang is an open-source framework for programming and serving large language models and multimodal models.
- URL: https://duckduckgo.com/SGLang
- snippet: SGLang - SGLang is an open-source framework for programming and serving large language models and multimodal models.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 7 [duckduckgo]
- タイトル: Free software programmed in Go
- URL: https://duckduckgo.com/c/Free_software_programmed_in_Go
- snippet: Free software programmed in Go

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 8 [duckduckgo]
- タイトル: Natural language processing software
- URL: https://duckduckgo.com/c/Natural_language_processing_software
- snippet: Natural language processing software

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 9 [wikipedia-ja]
- タイトル: Ollama
- URL: https://ja.wikipedia.org/wiki/Ollama
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 10 [wikipedia-ja]
- タイトル: OKAMA
- URL: https://ja.wikipedia.org/wiki/OKAMA
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 11 [wikipedia-ja]
- タイトル: Obama ladislavii
- URL: https://ja.wikipedia.org/wiki/Obama_ladislavii
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 12 [wikipedia-ja]
- タイトル: Obama nungara
- URL: https://ja.wikipedia.org/wiki/Obama_nungara
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 13 [wikipedia-ja]
- タイトル: Obama burmeisteri
- URL: https://ja.wikipedia.org/wiki/Obama_burmeisteri
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 14 [wikipedia-en]
- タイトル: Ollama
- URL: https://en.wikipedia.org/wiki/Ollama
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 15 [wikipedia-en]
- タイトル: Ollamalitzli
- URL: https://en.wikipedia.org/wiki/Ollamalitzli
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 16 [wikipedia-en]
- タイトル: Ollanta Humala
- URL: https://en.wikipedia.org/wiki/Ollanta_Humala
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 17 [wikipedia-en]
- タイトル: Olly Alexander
- URL: https://en.wikipedia.org/wiki/Olly_Alexander
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 18 [wikipedia-en]
- タイトル: Ollagüe
- URL: https://en.wikipedia.org/wiki/Ollag%C3%BCe
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）

- [落ちた] score=0 Generative artificial intelligence - Generative artificial intelligence is a subfield of artificial intelligence that uses generative models to generate text, images, videos, audio, software code or o (duckduckgo) snippet_len=219 理由=score<=0
- [落ちた] score=0 llama.cpp - llama.cpp is an open-source software library that performs inference on various large language models such as Llama. It is co-developed alongside the GGML project, a general-purpose tensor (duckduckgo) snippet_len=307 理由=score<=0
- [落ちた] score=0 LM Studio — desktop application for locally running and interacting with LLMs . (duckduckgo) snippet_len=79 理由=score<=0
- [落ちた] score=0 Native app See related meanings for the phrase 'Native app'. (duckduckgo) snippet_len=60 理由=score<=0
- [落ちた・snippet空] score=0 OKAMA (wikipedia) 理由=score<=0
- [落ちた・snippet空] score=0 Obama ladislavii (wikipedia) 理由=score<=0
- [落ちた・snippet空] score=0 Obama nungara (wikipedia) 理由=score<=0
- [落ちた・snippet空] score=0 Obama burmeisteri (wikipedia) 理由=score<=0
- [落ちた・snippet空] score=0 Ollanta Humala (wikipedia-en) 理由=score<=0
- [落ちた・snippet空] score=0 Olly Alexander (wikipedia-en) 理由=score<=0
- [落ちた・snippet空] score=0 Ollagüe (wikipedia-en) 理由=score<=0

### 調査専用: Wikipedia extracts（snippet空候補）

- Ollama: extract_len=0 page_has_usable_text=False
- OKAMA: extract_len=0 page_has_usable_text=False
- Obama ladislavii: extract_len=49 page_has_usable_text=False
  プレビュー: Obama ladislaviiは、リクウズムシ科の一種。ブラジル南部に分布し、緑色の体色が特徴。...

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: A03

**質問:** OpenAIについて最近何か大きな発表はありましたか
**検索クエリ:** OpenAI
**時間依存:** はい

### 段階件数（機械観測・事実のみ）

```text
API生: 10
hit化: 10
unique後: 10
ranking後: 5
return: 5
LLM受領: 5
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [wikipedia-ja]
- タイトル: OpenAI
- URL: https://ja.wikipedia.org/wiki/OpenAI
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [wikipedia-ja]
- タイトル: OpenAI o1
- URL: https://ja.wikipedia.org/wiki/OpenAI_o1
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [wikipedia-ja]
- タイトル: OpenAI Five
- URL: https://ja.wikipedia.org/wiki/OpenAI_Five
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 4 [wikipedia-ja]
- タイトル: OpenAI Codex
- URL: https://ja.wikipedia.org/wiki/OpenAI_Codex
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 5 [wikipedia-ja]
- タイトル: OpenAI o4-mini
- URL: https://ja.wikipedia.org/wiki/OpenAI_o4-mini
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 6 [wikipedia-en]
- タイトル: OpenAI
- URL: https://en.wikipedia.org/wiki/OpenAI
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 7 [wikipedia-en]
- タイトル: 2026 OpenAI agent cyberattacks
- URL: https://en.wikipedia.org/wiki/2026_OpenAI_agent_cyberattacks
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 8 [wikipedia-en]
- タイトル: OpenAI Codex (AI agent)
- URL: https://en.wikipedia.org/wiki/OpenAI_Codex_(AI_agent)
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 9 [wikipedia-en]
- タイトル: OpenAI o1
- URL: https://en.wikipedia.org/wiki/OpenAI_o1
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 10 [wikipedia-en]
- タイトル: OpenAI Five
- URL: https://en.wikipedia.org/wiki/OpenAI_Five
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）

- [落ちた・snippet空] score=11 OpenAI (wikipedia-en) 理由=over_return_limit
- [落ちた・snippet空] score=11 2026 OpenAI agent cyberattacks (wikipedia-en) 理由=over_return_limit
- [落ちた・snippet空] score=11 OpenAI Codex (AI agent) (wikipedia-en) 理由=over_return_limit
- [落ちた・snippet空] score=11 OpenAI o1 (wikipedia-en) 理由=over_return_limit
- [落ちた・snippet空] score=11 OpenAI Five (wikipedia-en) 理由=over_return_limit

### 調査専用: Wikipedia extracts（snippet空候補）

- OpenAI: extract_len=107 page_has_usable_text=True
  プレビュー: OpenAI（オープンエーアイ、オープンAI）は、非営利法人 OpenAI, Inc. と子会社の営利法人 OpenAI Global, LLC などから構成される、人工知能（AI）を開発するアメリカの企業である。...
- OpenAI o1: extract_len=514 page_has_usable_text=True
  プレビュー: OpenAI o1（オープンエーアイ オーワン）は、2024年9月にOpenAIが発表した論理的思考（reasoning）能力を強化した大規模言語モデルである。o1は回答する前に思考時間をとるため、複雑な論理的思考、科学、数学、プログラミングにおいてより高度な能力を保持する。2024年12月時点では、OpenAI o1、OpenAI o1 pro mode、OpenAI o1-miniの3モデルが...
- OpenAI Five: extract_len=547 page_has_usable_text=True
  プレビュー: OpenAI Five (オープンエーアイ ファイブ)は、OpenAIによって開発された複雑なゲームをプレイすることが可能なコンピュータプログラムである。5対5のビデオゲームである『Dota 2』をプレイする機能をもつ。2017年に公開され、プロプレイヤーのDendiとの1対1のライブ対戦で披露され、Dendiは敗北した。翌年2018年には、5人チームとしてDota 2をプレイする機能が追加され、...

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: A04

**質問:** 今のNVIDIAの株価の雰囲気を教えて
**検索クエリ:** NVIDIA
**時間依存:** はい

### 段階件数（機械観測・事実のみ）

```text
API生: 21
hit化: 15
unique後: 14
ranking後: 5
return: 5
LLM受領: 5
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [duckduckgo]
- タイトル: Nvidia
- URL: https://en.wikipedia.org/wiki/Nvidia
- snippet: Nvidia Corporation is an American multinational technology company headquartered in Santa Clara, California. The company develops graphics processing units, systems on chips, and application programming interfaces for data science, high-performance computing, artificial intelligence, and mobile and automotive applications. Founded in 1993 by Jensen Huang, Chris Malachowsky, and Curtis Priem, Nvidia has been widely described as a Big Tech company. Originally focused on GPUs for video games, Nvidia quoted themselves as a "full-stack" computing enterprise. They broadened their usage into other markets, including artificial intelligence, professional visualization, and supercomputing. The company's product lines include GeForce GPUs for gaming and creative workloads, and professional GPUs for edge computing, scientific research, and industrial applications. As of the first quarter of 2025, Nvidia held a 92% share of the discrete desktop and laptop GPU market.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [duckduckgo]
- タイトル: Nvidia Category
- URL: https://duckduckgo.com/c/Nvidia
- snippet: Nvidia Category

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [duckduckgo]
- タイトル: Nvidia Parabricks – GPU-accelerated genomics toolkit.
- URL: https://duckduckgo.com/Nvidia_Parabricks
- snippet: Nvidia Parabricks – GPU-accelerated genomics toolkit.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 4 [duckduckgo]
- タイトル: Companies in the Dow Jones Industrial Average
- URL: https://duckduckgo.com/c/Companies_in_the_Dow_Jones_Industrial_Average
- snippet: Companies in the Dow Jones Industrial Average

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 5 [duckduckgo]
- タイトル: Graphics hardware companies
- URL: https://duckduckgo.com/c/Graphics_hardware_companies
- snippet: Graphics hardware companies

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 6 [duckduckgo]
- タイトル: Companies based in Santa Clara, California
- URL: https://duckduckgo.com/c/Companies_based_in_Santa_Clara%2C_California
- snippet: Companies based in Santa Clara, California

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 7 [duckduckgo]
- タイトル: Semiconductor companies of the United States
- URL: https://duckduckgo.com/c/Semiconductor_companies_of_the_United_States
- snippet: Semiconductor companies of the United States

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 8 [duckduckgo]
- タイトル: Fabless semiconductor companies
- URL: https://duckduckgo.com/c/Fabless_semiconductor_companies
- snippet: Fabless semiconductor companies

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 9 [duckduckgo]
- タイトル: Technology companies based in the San Francisco Bay Area
- URL: https://duckduckgo.com/c/Technology_companies_based_in_the_San_Francisco_Bay_Area
- snippet: Technology companies based in the San Francisco Bay Area

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 10 [duckduckgo]
- タイトル: Computer companies of the United States
- URL: https://duckduckgo.com/c/Computer_companies_of_the_United_States
- snippet: Computer companies of the United States

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 11 [duckduckgo]
- タイトル: Computer hardware companies
- URL: https://duckduckgo.com/c/Computer_hardware_companies
- snippet: Computer hardware companies

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 12 [wikipedia-ja]
- タイトル: NVIDIA
- URL: https://ja.wikipedia.org/wiki/NVIDIA
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 13 [wikipedia-ja]
- タイトル: NVIDIA GeForce
- URL: https://ja.wikipedia.org/wiki/NVIDIA_GeForce
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 14 [wikipedia-ja]
- タイトル: NVIDIA Quadro
- URL: https://ja.wikipedia.org/wiki/NVIDIA_Quadro
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 15 [wikipedia-ja]
- タイトル: NVIDIA Tesla
- URL: https://ja.wikipedia.org/wiki/NVIDIA_Tesla
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 16 [wikipedia-ja]
- タイトル: NVIDIA Tegra
- URL: https://ja.wikipedia.org/wiki/NVIDIA_Tegra
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 17 [wikipedia-en]
- タイトル: Nvidia
- URL: https://en.wikipedia.org/wiki/Nvidia
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 18 [wikipedia-en]
- タイトル: Nvidia DGX
- URL: https://en.wikipedia.org/wiki/Nvidia_DGX
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 19 [wikipedia-en]
- タイトル: Nvidia PureVideo
- URL: https://en.wikipedia.org/wiki/Nvidia_PureVideo
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 20 [wikipedia-en]
- タイトル: Nvidia Drive
- URL: https://en.wikipedia.org/wiki/Nvidia_Drive
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 21 [wikipedia-en]
- タイトル: Nvidia Shield TV
- URL: https://en.wikipedia.org/wiki/Nvidia_Shield_TV
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）

- [落ちた] score=0 Companies in the Dow Jones Industrial Average (duckduckgo) snippet_len=45 理由=score<=0
- [落ちた] score=0 Graphics hardware companies (duckduckgo) snippet_len=27 理由=score<=0
- [落ちた・snippet空] score=11 NVIDIA Quadro (wikipedia) 理由=over_return_limit
- [落ちた・snippet空] score=11 NVIDIA Tesla (wikipedia) 理由=over_return_limit
- [落ちた・snippet空] score=11 NVIDIA Tegra (wikipedia) 理由=over_return_limit
- [落ちた・snippet空] score=11 Nvidia DGX (wikipedia-en) 理由=over_return_limit
- [落ちた・snippet空] score=11 Nvidia PureVideo (wikipedia-en) 理由=over_return_limit
- [落ちた・snippet空] score=11 Nvidia Drive (wikipedia-en) 理由=over_return_limit
- [落ちた・snippet空] score=11 Nvidia Shield TV (wikipedia-en) 理由=over_return_limit

### 調査専用: Wikipedia extracts（snippet空候補）

- NVIDIA: extract_len=390 page_has_usable_text=True
  プレビュー: NVIDIA Corporation（エヌビディア・コーポレーション）は、アメリカ合衆国に本社を置く、主にGPGPU（汎用計算用GPU）やAI（人工知能）関連の半導体を開発・研究・販売する世界的企業である。
グローバル本部とGPUの開発拠点は米国カリフォルニア州のサンタクララに所在し、アジア本部とAIの開発拠点は台湾の台北市と高雄市に設置されている。また、日本法人のエヌビディア合同会社（法人番号：...
- NVIDIA GeForce: extract_len=200 page_has_usable_text=True
  プレビュー: GeForce（ジーフォース）は、NVIDIA社が設計開発しているGraphics Processing Unit (GPU) のブランド名である。
同社の「RIVA」シリーズの後継製品にあたり、1999年に発表されたGeForce 256を最初に、競合するアドバンスト・マイクロ・デバイセズ (AMD) のRadeonと共にパーソナルコンピュータにおけるグラフィックス・テクノロジーを先導している。...
- NVIDIA Quadro: extract_len=55 page_has_usable_text=False
  プレビュー: Quadro（クアドロ）は、NVIDIA社のグラフィックスアクセラレータ (GPU) の製品群のひとつである。...

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: C04

**質問:** ローカルLLMの事情、最近どう？
**検索クエリ:** large language model
**時間依存:** はい

### 段階件数（機械観測・事実のみ）

```text
API生: 10
hit化: 7
unique後: 6
ranking後: 2
return: 2
LLM受領: 2
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [duckduckgo]
- タイトル: Large language model
- URL: https://en.wikipedia.org/wiki/Large_language_model
- snippet: A large language model is an AI model trained on a vast amount of text for natural language processing tasks, especially language generation. LLMs can typically generate, summarize, translate, and analyze text in many contexts. They are the basis for many modern chatbots, such as ChatGPT, Claude, Gemini, Grok, and DeepSeek. LLMs are typically based on transformer architecture. Generative pre-trained transformers are a type of LLM that is pre-trained to predict the next word. GPTs are then often fine-tuned to follow instructions and to behave as assistants. Biased or inaccurate training data can make an LLM's output less reliable. Benchmark evaluations for LLMs attempt to measure model reasoning, factual accuracy, alignment, and safety.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [duckduckgo]
- タイトル: Energy consumption
- URL: https://duckduckgo.com/c/Energy_consumption
- snippet: Energy consumption

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [duckduckgo]
- タイトル: Environmental impact by source
- URL: https://duckduckgo.com/c/Environmental_impact_by_source
- snippet: Environmental impact by source

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 4 [duckduckgo]
- タイトル: Environmental impact of the energy industry
- URL: https://duckduckgo.com/c/Environmental_impact_of_the_energy_industry
- snippet: Environmental impact of the energy industry

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 5 [duckduckgo]
- タイトル: Deep learning
- URL: https://duckduckgo.com/c/Deep_learning
- snippet: Deep learning

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 6 [duckduckgo]
- タイトル: Water and the environment
- URL: https://duckduckgo.com/c/Water_and_the_environment
- snippet: Water and the environment

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 7 [duckduckgo]
- タイトル: Energy policy
- URL: https://duckduckgo.com/c/Energy_policy
- snippet: Energy policy

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 8 [duckduckgo]
- タイトル: Natural language processing
- URL: https://duckduckgo.com/c/Natural_language_processing
- snippet: Natural language processing

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 9 [wikipedia-en]
- タイトル: Large language model
- URL: https://en.wikipedia.org/wiki/Large_language_model
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 10 [wikipedia-en]
- タイトル: Large language model benchmark
- URL: https://en.wikipedia.org/wiki/Large_language_model_benchmark
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）

- [落ちた] score=0 Energy consumption (duckduckgo) snippet_len=18 理由=score<=0
- [落ちた] score=0 Environmental impact by source (duckduckgo) snippet_len=30 理由=score<=0
- [落ちた] score=0 Environmental impact of the energy industry (duckduckgo) snippet_len=43 理由=score<=0
- [落ちた] score=0 Deep learning (duckduckgo) snippet_len=13 理由=score<=0

### 調査専用: Wikipedia extracts（snippet空候補）

- Large language model: extract_len=787 page_has_usable_text=True
  プレビュー: A large language model (LLM) is an AI model (typically a neural network) trained on a vast amount of text for natural language processing tasks, especially language generation. LLMs can typically gene...
- Large language model benchmark: extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: B05

**質問:** Pythonのリストとタプルの違いを簡単に説明して
**検索クエリ:** Python tuple
**時間依存:** いいえ

### 段階件数（機械観測・事実のみ）

```text
API生: 3
hit化: 3
unique後: 3
ranking後: 3
return: 3
LLM受領: 3
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [wikipedia-en]
- タイトル: Python implementations
- URL: https://en.wikipedia.org/wiki/Python_implementations
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [wikipedia-en]
- タイトル: Python Unleashed
- URL: https://en.wikipedia.org/wiki/Python_Unleashed
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [wikipedia-en]
- タイトル: Python (nuclear primary)
- URL: https://en.wikipedia.org/wiki/Python_(nuclear_primary)
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）


### 調査専用: Wikipedia extracts（snippet空候補）

- Python implementations: extract_len=0 page_has_usable_text=False
- Python Unleashed: extract_len=0 page_has_usable_text=False
- Python (nuclear primary): extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: WB02

**質問:** Dockerコンテナの基本的な考え方を教えて
**検索クエリ:** Docker (software)
**時間依存:** いいえ

### 段階件数（機械観測・事実のみ）

```text
API生: 14
hit化: 7
unique後: 6
ranking後: 5
return: 5
LLM受領: 5
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [duckduckgo]
- タイトル: Docker (software)
- URL: https://en.wikipedia.org/wiki/Docker_(software)
- snippet: Docker is a set of products that uses operating system-level virtualization to deliver software in packages called containers. Docker automates the deployment of applications within lightweight containers, enabling them to run consistently across different computing environments. The core software that runs and manages these containers is called Docker Engine. Docker was first released in 2013 and continues to be developed by Docker, Inc. The platform includes both free and paid tiers.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [duckduckgo]
- タイトル: DevOps - DevOps is the integration and automation of software development and information technology operations. DevOps encompasses the tasks necessary for software development and can lead to both shortening development time and improving the development life cycle.
- URL: https://duckduckgo.com/DevOps
- snippet: DevOps - DevOps is the integration and automation of software development and information technology operations. DevOps encompasses the tasks necessary for software development and can lead to both shortening development time and improving the development life cycle.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [duckduckgo]
- タイトル: DevOps toolchain - A DevOps toolchain is a set or combination of tools that aid in the delivery, development, and management of software applications throughout the systems development life cycle, as coordinated by an organization that uses DevOps practices.
- URL: https://duckduckgo.com/DevOps_toolchain
- snippet: DevOps toolchain - A DevOps toolchain is a set or combination of tools that aid in the delivery, development, and management of software applications throughout the systems development life cycle, as coordinated by an organization that uses DevOps practices.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 4 [duckduckgo]
- タイトル: Kubernetes - Kubernetes, also known as K8s, is an open-source container orchestration system for automating software deployment, scaling, and management.
- URL: https://duckduckgo.com/Kubernetes
- snippet: Kubernetes - Kubernetes, also known as K8s, is an open-source container orchestration system for automating software deployment, scaling, and management.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 5 [duckduckgo]
- タイトル: Microservices - In software engineering, a microservice architecture is an architectural pattern that organizes an application into a collection of loosely coupled, fine-grained services that communicate through lightweight protocols.
- URL: https://duckduckgo.com/Microservices
- snippet: Microservices - In software engineering, a microservice architecture is an architectural pattern that organizes an application into a collection of loosely coupled, fine-grained services that communicate through lightweight protocols.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 6 [duckduckgo]
- タイトル: Open Container Initiative - The Open Container Initiative is a Linux Foundation project, started in June 2015 by Docker, CoreOS, and the maintainers of appc to design open standards for operating system-level virtualization.
- URL: https://duckduckgo.com/Open_Container_Initiative
- snippet: Open Container Initiative - The Open Container Initiative is a Linux Foundation project, started in June 2015 by Docker, CoreOS, and the maintainers of appc to design open standards for operating system-level virtualization.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 7 [duckduckgo]
- タイトル: OS-level virtualization - OS-level virtualization is an operating system virtualization paradigm in which the kernel allows the existence of multiple isolated user space instances, including containers, zones, virtual private servers, partitions, virtual environments, virtual kernels, and jails.
- URL: https://duckduckgo.com/OS-level_virtualization
- snippet: OS-level virtualization - OS-level virtualization is an operating system virtualization paradigm in which the kernel allows the existence of multiple isolated user space instances, including containers, zones, virtual private servers, partitions, virtual environments, virtual kernels, and jails.

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 8 [duckduckgo]
- タイトル: Free virtualization software
- URL: https://duckduckgo.com/c/Free_virtualization_software
- snippet: Free virtualization software

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 9 [duckduckgo]
- タイトル: Free software programmed in Go
- URL: https://duckduckgo.com/c/Free_software_programmed_in_Go
- snippet: Free software programmed in Go

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 10 [duckduckgo]
- タイトル: Operating system security
- URL: https://duckduckgo.com/c/Operating_system_security
- snippet: Operating system security

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 11 [duckduckgo]
- タイトル: Operating system technology
- URL: https://duckduckgo.com/c/Operating_system_technology
- snippet: Operating system technology

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 12 [duckduckgo]
- タイトル: Software using the Apache license
- URL: https://duckduckgo.com/c/Software_using_the_Apache_license
- snippet: Software using the Apache license

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 13 [wikipedia-en]
- タイトル: Docker (software)
- URL: https://en.wikipedia.org/wiki/Docker_(software)
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 14 [wikipedia-en]
- タイトル: Dock (software)
- URL: https://en.wikipedia.org/wiki/Dock_(software)
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）

- [落ちた・snippet空] score=3 Dock (software) (wikipedia-en) 理由=over_return_limit

### 調査専用: Wikipedia extracts（snippet空候補）

- Docker (software): extract_len=0 page_has_usable_text=False
- Dock (software): extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: P02a

**質問:** RTX 3060について教えて
**検索クエリ:** GeForce RTX 3060
**時間依存:** いいえ

### 段階件数（機械観測・事実のみ）

```text
API生: 5
hit化: 5
unique後: 5
ranking後: 5
return: 5
LLM受領: 5
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [wikipedia-en]
- タイトル: GeForce RTX 3060
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_3060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [wikipedia-en]
- タイトル: GeForce RTX 5070
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_5070
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 3 [wikipedia-en]
- タイトル: GeForce RTX 4050
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_4050
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 4 [wikipedia-en]
- タイトル: GeForce RTX 2060
- URL: https://en.wikipedia.org/wiki/GeForce_RTX_2060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 5 [wikipedia-en]
- タイトル: GeForce GTX 1060
- URL: https://en.wikipedia.org/wiki/GeForce_GTX_1060
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）


### 調査専用: Wikipedia extracts（snippet空候補）

- GeForce RTX 3060: extract_len=0 page_has_usable_text=False
- GeForce RTX 5070: extract_len=0 page_has_usable_text=False
- GeForce RTX 4050: extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---

## CASE: E02

**質問:** ChatGPTの有料プランの違いを教えて
**検索クエリ:** ChatGPT Plus
**時間依存:** いいえ

### 段階件数（機械観測・事実のみ）

```text
API生: 2
hit化: 2
unique後: 2
ranking後: 2
return: 2
LLM受領: 2
```

### API候補（人間レビュー用・自動判定なし）

#### 候補 1 [wikipedia-en]
- タイトル: ChatGPT Plus
- URL: https://en.wikipedia.org/wiki/ChatGPT_Plus
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

#### 候補 2 [wikipedia-en]
- タイトル: ChatGPT psychosis
- URL: https://en.wikipedia.org/wiki/ChatGPT_psychosis
- snippet: （空）

**候補の内容（人間記入）:** ◎ / ○ / △ / × / ？

### rankingで落ちた候補（snippetあり含む）


### 調査専用: Wikipedia extracts（snippet空候補）

- ChatGPT Plus: extract_len=0 page_has_usable_text=False
- ChatGPT psychosis: extract_len=0 page_has_usable_text=False

### 人間記入欄

| 項目 | 記入 |
|------|------|
| 有用候補の有無 | |
| 有用候補の番号 | |
| rankingで落ちた有用候補 | |
| 内容の充実度 | |
| 日本語情報の十分さ | |
| 現在性 | |
| LLMに十分な情報が渡ったか | |
| 主な問題箇所 A/B/C/D/? | |
| 人間コメント | |

---
