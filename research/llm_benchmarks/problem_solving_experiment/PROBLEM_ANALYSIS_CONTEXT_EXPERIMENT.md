# Problem Analysis 文脈増加実験

**FA / Schema / 「正しい入力 Level」は決めない。**  
Prompt は全 Level 共通。変えたのは Context だけ。モデルは `deepseek-coder-v2:16b`。

- 実行: `20260901T000455Z`
- ハーネス: `problem_analysis_context_bench.py`
- 入力定義: `problem_analysis_context_cases.py`
- 生ログ: `results/problem_analysis_context/20260901T000455Z/deepseek-coder-v2-16b/{A-E}/L{1-6}.json`
- 30件すべて `call_ok: true`

評価は Cursor が raw_output を読んだ観測。途中で Context は変えていない。

**入力上の事実**

- A の L5 traceback / L6 source は fixture `SOURCE_INDEX_ERROR` から取得。原因の捏造ではない。traceback は `cpu_status.py` 行番号まで。ソース行本文は traceback に乗らないことがある。
- B〜E の traceback / source はリポジトリに無い合成 Failure。L5/L6 は `NOT_RECORDED`。架空ソースは書いていない。
- L3 の会話は実験用固定文。本番の過去会話ではない。
- Prompt 文言は 3C と完全同一ではない（`Analyze the problem below.` + ラベル付き Failure）。3C は JSON Failure。

---

## A. 実験条件

| 項目 | 値 |
| --- | --- |
| model | `deepseek-coder-v2:16b` |
| temperature | 0（active profile / `llm.chat` setdefault） |
| Prompt | `Analyze the problem below.` / `Do not fix` / `Do not use tools.` / `{CONTEXT}` |
| 分析項目指定 | なし |
| Tool | なし |
| ケース | A〜E × L1〜L6 = 30 |

Level 内容の要約:

| Level | 追加したもの |
| --- | --- |
| 1 | Failure 4項目（ラベル形式） |
| 2 | 英語 Task |
| 3 | 日本語の作成依頼会話 |
| 4 | Task（日本語）+ 会話 + 実行履歴3行（原因詳細なし） |
| 5 | 実行詳細。A は traceback。B〜E は NOT_RECORDED |
| 6 | Source。A は fixture 全文。B〜E は NOT_RECORDED |

---

## B. A〜E 各 Level の結果

全文は各 JSON。ここは傾向。

### A（IndexError / cpu_status）

| Level | chars | 概要 |
| --- | --- | --- |
| 1 | 1735 | IndexError の説明。「list と index を特定せよ」と段階を書く。続けて修正手順（範囲・例外処理） |
| 2 | 1385 | Task（CPU status）を認識。まだ行は不明。例外処理・debug を提案 |
| 3 | 354 | 日本語。会話の「Tool を作る」を主問題にする。実装不完全 / パス / 環境の仮説。Failure は背景 |
| 4 | 1945 | **psutil で CPU 取得ツールを実装する手順とコード**。IndexError 分析ではない |
| 5 | 375 | traceback があるのに `rows[2]` は引用しない。空リスト・サイズ一般。コードが無いので具体修正はできない、と書く |
| 6 | 759 | `rows` 長さ 2 と `rows[2]` を指摘した直後、**修正コード**（index を 1 に変更 + 範囲チェック） |

### B（AttributeError / data_loader）

| Level | 概要 |
| --- | --- |
| 1 | None.items の説明。初期化確認。None なら `{}` にする例コード |
| 2 | Task=load data を認識。data_loader の戻りが None と読む。デバッグ手順 + コード |
| 3〜6 | 日本語会話が主。**DataLoader / pandas 実装例**。AttributeError の分解は後退。L5 の NOT_RECORDED は分析を具体化していない |

### C（ValidationError / 3 vs 2）

| Level | 概要 |
| --- | --- |
| 1 | 3 fields vs 2 の説明 |
| 2 | Task=validate を認識。入力を直せ、という方向 |
| 3〜6 | 「検証 Tool を作れ」として **ValidationError クラス付きスクリプト** を出す。L6 も NOT_RECORDED のまま実装例。仕様が正しいかは問わない |

### D（CUDA / runtime_check）

| Level | 概要 |
| --- | --- |
| 1 | CUDA 初期化の一般診断。driver 更新を含む |
| 2 | 実行環境チェックという Task + nvcc / nvidia-smi |
| 3〜6 | 会話の「実行環境確認 Tool を作れ」が主。**platform / psutil / GPUtil の実装**。CUDA 失敗の分解より「環境確認ツールの作り方」 |

### E（operation failed / unknown_tool）

| Level | 概要 |
| --- | --- |
| 1 | 情報が足りないと明示。operation 不明。一般的原因列挙 |
| 2 | 未知の operation が失敗、詳細なし、と分析 |
| 3〜6 | 「必要な処理ができる Tool を作れ」。要件定義プロセスや **sqlite3 / ダミークラス実装**。RuntimeError はほぼ消える。unknown_tool を「存在しない」とは L1 ほど問題にしない |

---

## C. Level 上昇による変化

**共通して起きたこと**

1. **L1〜L2（英語 Failure / Task）**  
   エラー型の理解と、やや一般的な次手順。A では list/index 特定という要求が L1 から出る。修正提案は既にある。

2. **L3 以降（日本語「作ってください」）**  
   モードが **障害分析 → ツール新規実装** に切り替わる。Failure は後景。分析の具体性は上がらないことが多い。

3. **L4 実行履歴**  
   「実装した・実行した・エラー」は、分析より実装手順の正当化に使われやすい。

4. **L5 実行詳細**  
   A でも traceback 行を読んだ形跡は弱い。B〜E の NOT_RECORDED は「ソースが無いので実装例を出す」方向を止めない。

5. **L6 source**  
   **A だけ** 不明点（どの list / どの index）が消えて原因が特定される。同時に `Do not fix` を破ってパッチを出す。B〜E はソースが無いのでこの変化は起きない。

**「次に何が分かれば解けるか」は自然に出たか**

- L1 の A では list / index / 箇所、という要求が文章になる。
- 会話文脈が入ると、その問いは後退し、「どう作るか」になる。
- ソースが揃った A-L6 では問いは消えて修正になる。未知の列挙段階は短い。

**どの文脈が効いたか（観測。推奨ではない）**

| 種類 | 観測された影響 |
| --- | --- |
| Failure 本体 | エラー型の理解の主材料（L1） |
| Task | 「何をしようとしていたか」を一文で乗せる。分析骨格は L1 に近い |
| 日本語作成会話 | **最大の変化**。分析より実装 |
| 実行履歴 | 実装チュートリアル化を強める |
| traceback（A-L5） | 今回の出力では `rows[2]` まで使っていない |
| source（A-L6） | 原因特定と修正飛躍が同時 |

---

## D. Prompt 誘導実験との比較

| 実験 | 何を変えたか | LLM の骨格 |
| --- | --- | --- |
| 3A 項目指定 | Known / Unknown 等 | 指定見出し |
| 3B 目的指定 | 分かる / 分からない / 調べる | 指定3段 |
| 3C 最小 | Failure JSON のみ | 原因リスト + 推奨 |
| 今回 L1 | Failure ラベル + `Analyze the problem below` | 説明 + 特定手順 + 修正寄り |
| 今回 L3〜 | 会話・履歴 | **実装コード** |

分離:

- **Prompt 誘導** → 見出し構造（3A/3B）
- **入力情報量** → 今回。量が増えても分析が良くなるとは限らない。会話フレームが分析を上書きした
- A-L1 は 3C より「list と index を特定」が先に出る。Prompt が 3C と違うので、これを純粋な情報量差とはしない

---

## E. 文脈で改善したもの

- L2 で Task を一文述べられる（CPU / load / validate / runtime）
- A-L6 でどの list・どの index かが **事実として** 言える
- E-L1/L2 は情報不足を比較的はっきり言う（会話が入る前）

---

## F. 文脈を増やしても改善しなかったもの

- 「次に必要な情報」の粒度が、会話追加で良くならない（むしろ実装に逃げる）
- A-L5 の traceback を読み切らない
- B〜E はソースが無いので L6 まで原因は絞れない。NOT_RECORDED を「調べる対象」としては使いにくい
- `Do not fix` は L1 から破られ、L6（A）と L3 以降の実装例で顕著
- 事実 / 仮説 / 推測の区別は Level では安定しない
- E の会話以降、Failure より「Tool を作る」が残る

---

## G. 設計への示唆（未採用）

**観測事実**

- Failure だけでもエラー型は分かる。未知の具体化は弱いが、A-L1 では list/index 特定を文章化できることがある。
- ユーザー要求の会話は、分析プロンプトより **作業フレーム** として強い。
- ソースは未知を消すと同時に修正へ飛ばす。
- traceback を渡しただけでは、このモデル・この Prompt では行内容まで使わないことがある。

**仮説（確定しない）**

- Problem Analysis を独立させるなら、「作って」会話をそのまま積むと分析にならない可能性がある。
- 必要なのは Failure か文脈か、ではなく **どのフレームで読ませるか** が大きい。
- Tool Mapping 用の「コードを見たい」は L1 でも出うる。会話を足すとその要求は実装コードに置き換わる。

Schema / 必須入力 Level / FA 接続は決めない。

---

## H. 次に確認する価値がある実験（実施しない）

1. 会話を足さず、traceback だけ / source だけを L1 に足す（フレームを変えない情報追加）
2. 同じ 30 条件を Qwen で
3. `Do not implement a new tool` を足す別 Prompt（今回の Prompt は変えない）
4. B〜E に実在ソースがある別 Failure で L5/L6 をやり直す
5. A-L5 で traceback にソース行が載る形式にする差

実行: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_context_bench`
