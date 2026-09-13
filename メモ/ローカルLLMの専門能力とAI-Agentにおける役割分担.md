# ローカルLLMの専門能力とAI-Agentにおける役割分担

## 1. 目的

AI-Agentでは、1つのLLMですべての処理を行わせるのではなく、モデルごとの得意分野を活かして役割を分担する。

基本方針は、

> **Agent本体が判断し、専門モデルが必要な処理を担当し、既存ソフトウェアやToolを実行する**

とする。

これにより、各モデルに無理にすべての能力を持たせる必要をなくし、ローカル環境の計算資源も有効利用する。

---

## 2. 主な能力

### Tool Calling

LLMが構造化された形式で外部Toolを呼び出す能力。

```text
LLM
 ↓
Tool Calling
 ↓
Tool実行
 ↓
結果
 ↓
LLM
```

AI-Agentの中心的な能力。

ファイル操作、テスト実行、GPU確認、画像生成、ネットワーク確認など、外部機能を利用するときに使用する。

---

### Thinking

Toolを呼ぶ前などに、より深く考えて計画・判断する能力。

```text
ユーザー要求
 ↓
状況を考える
 ↓
必要なToolを判断
 ↓
Tool Calling
 ↓
結果を確認
 ↓
次の行動を判断
```

複数Toolを組み合わせるAgentでは特に有用。

---

### Vision

画像を入力として受け取り、画像の内容を理解して判断する能力。

```text
画像
 ↓
Visionモデル
 ↓
画像の内容・問題点を説明
```

用途例：

- スクリーンショットの確認
- エラー画面の確認
- 生成画像の評価
- 人物・物体・構図の確認
- 2枚の画像の比較
- 画像が要求内容を満たしているかの確認

特に画像生成との組み合わせでは、

```text
画像生成
 ↓
Visionによる検査
 ↓
問題点の抽出
 ↓
Agentが改善方法を判断
 ↓
プロンプト修正
 ↓
再生成
```

という自動改善ループに利用できる。

---

### Embedding

文章やデータの「意味」を数値ベクトルとして表現する能力。

通常のLLMのように回答を生成するためではなく、**意味の近い情報を検索するため**に利用する。

用途例：

- 過去のエラー検索
- 過去の修正履歴検索
- 過去のTASK検索
- REPORT検索
- プロジェクト資料検索
- Agentの長期記憶
- RAG

例えば、

```text
「GPUの温度が高すぎる」

「グラフィックボードが熱くなっている」

「GPU temperature exceeded」
```

のような表現の違う文章から、意味的に近い情報を検索できる。

将来的なAgentの「記憶」機能に重要。

---

### Reranker

検索で得られた候補をさらに評価し、関連性の高いものを上位に並べる能力。

```text
大量の資料
 ↓
Embedding検索
 ↓
候補20件
 ↓
Reranker
 ↓
重要な5件
```

Embeddingと組み合わせることで、大量の過去資料から必要な情報を効率よく取り出せる。

---

### Audio / 音声認識

音声を入力して文字などの情報に変換する能力。

```text
音声
 ↓
音声認識モデル
 ↓
テキスト
 ↓
Agent
```

用途例：

- 音声によるAgent操作
- 音声メモ
- 会話の文字起こし
- 動画・音声の字幕作成
- 音声からの作業指示

既存のWhisper系ツールなどをToolとして接続することも可能。

---

## 3. 現在のローカルモデル

### Qwen3 14B

確認結果：

```text
parameters    14.8B
context       40960
quantization  Q4_K_M

Capabilities
  completion
  tools
  thinking
```

現時点での**Agent本体の第一候補**。

役割：

- ユーザー要求の理解
- 状況判断
- 計画
- Thinking
- Tool選択
- Tool Calling
- 複数Toolを使った処理
- 結果の評価

---

### Qwen3 8B

確認結果：

```text
parameters    8.2B
context       40960
quantization  Q4_K_M

Capabilities
  completion
  tools
  thinking
```

Qwen3 14Bと同じく、

- Tool Calling
- Thinking

を持つ。

14Bより軽量なので、Agentの軽量版・補助Agentなどの候補。

実際の処理速度と判断品質を比較し、用途によって14Bと使い分ける。

---

### Qwen2.5-Coder 7B

確認結果：

```text
parameters    7.6B
context       32768
quantization  Q4_K_M

Capabilities
  completion
  tools
  insert
```

コード作成・コード修正を主目的としたモデル。

`tools` を持つためTool Callingにも対応可能。

`insert` はコードの途中にある空白部分を補完するような用途に使われる能力。

Agent本体よりも、

> **コード作業担当**

として利用する候補。

---

### Gemma3 12B

確認結果：

```text
parameters    12.2B
context       131072
quantization  Q4_K_M

Capabilities
  completion
  vision
```

`Vision` を持つ画像対応モデル。

現時点ではTool Calling対応モデルとして扱わず、

> **画像を見る・画像を評価する専門モデル**

として利用する。

特に生成AIとの連携では、

```text
A1111 / ComfyUI
 ↓
画像生成
 ↓
Gemma3 12B
 ↓
画像検査
 ↓
問題点を文章化
 ↓
Qwen3 14B
 ↓
改善方法を判断
```

という構成を想定する。

---

### DeepSeek-Coder-V2 16B

確認済み：

```text
Tool Calling
非対応
```

Tool Callingを渡した実行では、

```text
supported: false
HTTP 400
```

となった。

したがって現在のAgent本体には使用せず、**非Tool Calling系の研究・互換経路を残すためのモデル**として扱う。

---

## 4. 現時点で想定する役割分担

```text
                         ユーザー
                            │
                            ▼
                  ┌─────────────────┐
                  │   Qwen3 14B     │
                  │   Agent本体      │
                  │ Thinking        │
                  │ Tool Calling    │
                  └────────┬────────┘
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
   Qwen2.5-Coder       Gemma3 12B       Embedding
      7B                  Vision           │
   コード担当             画像担当         │
          │                │                ▼
          │                │          過去資料・記憶検索
          │                │
          └────────────────┴──────┐
                                   ▼
                              各種Tool
                                   │
             ┌─────────────────────┼─────────────────────┐
             ▼                     ▼                     ▼
          pytest              A1111/ComfyUI          OS / File
```

必要になった場合、さらに、

```text
音声認識
Reranker
動画対応
その他専門モデル
```

を追加する。

---

## 5. 重要な設計方針

### 1つのモデルですべてを処理する必要はない

モデルごとに、

```text
Qwen3 14B
→ 考える・判断する

Qwen2.5-Coder
→ コードを扱う

Gemma3
→ 画像を見る

Embedding
→ 過去情報を探す

音声認識
→ 音声を文字にする
```

という分担を行う。

---

## 6. 「既存ソフトウェア優先」の原則

専門モデルを見つけたからといって、すぐに独自機能を作るわけではない。

優先順位は、

```text
既存ソフトウェア/API/CLIがある
        ↓
それをToolとして利用
        ↓
既存ソフトウェアの組み合わせで対応
        ↓
プラグイン・拡張で対応
        ↓
それでも不足する場合のみ
独自Tool・独自機能を開発
```

とする。

例えば、

- 画像生成 → A1111 / ComfyUI
- テスト → pytest
- LLM → Ollama
- 音声認識 → Whisper系
- GPU情報 → OS/NVIDIA関連Tool
- Git → Git
- 意味検索 → Embeddingモデル

のように、既存の仕組みを最大限利用する。

---

## 7. 今後のAI-Agentの発展形

最終的には、単純な「質問に答えるLLM」ではなく、

```text
ユーザー
 ↓
Qwen3 Agent
 ↓
必要な専門能力を判断
 ↓
専門モデル / Tool / 既存ソフトウェアを選択
 ↓
実行
 ↓
結果確認
 ↓
必要なら別のTool・モデルを使用
 ↓
問題解決
```

という構造を目指す。

つまり、

> **LLMを1つの万能AIとして扱うのではなく、LLM・専門モデル・既存ソフトウェア・Toolを組み合わせて1つのAgentシステムを構築する。**

これを今後のAI-Agent設計の基本方針とする。