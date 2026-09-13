# Problem Analysis 切り分け実験

**Schema / Tool Mapping / FA / 採用判断はしない。**  
変えたのは Failure に足す情報の種類だけ。Prompt は全件同一。

- 実行: `20260901T001627Z`
- ハーネス: `problem_analysis_context_split_bench.py`
- 入力: `problem_analysis_context_split_cases.py`
- 生ログ: `results/problem_analysis_context_split/20260901T001627Z/{deepseek,qwen3_14b}/{A-E}_F{1-5}.json`
- 50件すべて `call_ok: true`

評価は Cursor が `raw_output` を読んだ観測。thinking（Qwen）は比較軸にしない。途中で Prompt は変えていない。

必要情報の具体性は指示書の Level 0〜4。Tool Mapping は人間が後から見た接続可能性であり、LLM に Tool 名は出させていない。

---

## 1. 実験目的

Failure にどの種類の情報を足すと、事実・未知・次に必要な情報・修正飛躍がどう変わるかを切り分ける。

---

## 2. 固定条件

| 項目 | 値 |
| --- | --- |
| モデル | `deepseek-coder-v2:16b`, `qwen3:14b` |
| temperature | 0 |
| Tool | なし（`think=` も渡していない） |
| Prompt | `Analyze the problem below.` / `Do not fix the problem.` / `Do not use tools.` |
| Failure | 既存 A〜E の JSON 4フィールド |
| 架空 traceback / source | なし |

F5 の会話は **前回文脈実験の固定文** を改変せず使用（本番チャットではない）。新規の架空会話は作っていない。

A の traceback は fixture `SOURCE_INDEX_ERROR` を `cpu_status.py` として exec した実例外。スタックに実験関数 `_traceback_for_a` が混ざる（後述）。

B〜E の traceback / source は `NOT_RECORDED`。

Qwen は全件 `thinking_observed: true`。比較は content のみ。

---

## 3. F1〜F5 の入力差

| 条件 | 入力 |
| --- | --- |
| F1 | Failure JSON のみ |
| F2 | Failure + traceback（無ければ NOT_RECORDED） |
| F3 | Failure + source（無ければ NOT_RECORDED） |
| F4 | Failure + traceback + source（実データのみ） |
| F5 | Failure + 会話（前回 fixture）。traceback/source は付けない |

---

## 4. A〜E の結果（要約）

全文は JSON。必要情報 Level は観測用。

### A IndexError / cpu_status（実 traceback・source あり）

| 条件 | DeepSeek | Qwen |
| --- | --- | --- |
| F1 | 4フィールド言い直し。どの list かは出さない。必要情報 **L0〜1**。修正コードなし | IndexError の一般説明。CPU metrics 仮説。`No further action`。必要情報 **L1** |
| F2 | **cpu_status.py 4行目** と関数名を使う。list 名は出ない。範囲確認を勧める。必要情報 **L2〜3**。修正コードなし、手順あり | 4行目を使う。list 名は不明と書く。スタックの `_traceback_for_a` を文脈として読む。必要情報 **L2〜3** |
| F3 | `rows` 長さ2、`rows[2]` を特定。**rows[1] に直すパッチ**。必要情報は不要になる。**修正へ飛躍** | 同じ構造を短く述べる。パッチなし。必要情報 **L4**（すでに source 上で特定済み） |
| F4 | F3 と同じ特定。パッチ全文は短い説明に留まる。`rows[2]` を問題行として引用 | F3 と同型。パッチなし |
| F5 | **psutil で CPU Tool を実装**。IndexError を psutil 失敗に誤接続。分析崩壊 | IndexError 一般論。会話の「作れ」には乗らない。パッチなし。list 名は出ない |

### B AttributeError / None.items（traceback/source なし）

F2〜F4 は NOT_RECORDED なので F1 と大きくは変わらない。DeepSeek F2 は traceback が無いと書く。F5 DeepSeek は短く確認項目。Qwen F5 は None ガード不足に寄り、会話で実装クラスまでは出さない。必要情報はおおむね **L1〜2**。Mapping は「data_loader のコード」程度で粗い。

### C ValidationError 3 vs 2

F1 で件数不一致は分かる。欠けた field 名は出ない。DeepSeek F5 は **validator 実装コード**。Qwen F5 は「3必須なのに2」と短く、実装は弱い。Qwen F1 は Failure JSON の4キーを「validator の出力」と **混同** しうる。必要情報 **L1〜2**（どの field が欠けたか）。

### D CUDA

F1 から環境仮説（driver / toolkit / GPU）。F2 で traceback 無しと明示しても診断リストは同じ系統。DeepSeek F5 は **torch の RuntimeCheck 実装**。必要情報 **L1〜2**（環境）。`nvidia-smi` 相当は文章になるが Tool 名は出さない。

### E unknown_tool / operation failed

F1 DeepSeek は短い言い直し。F2 は NOT_RECORDED を認め、docs/logs。F5 は JSON 再掲。Qwen は unidentified + 詳細不足。PATH 断定は弱い。必要情報 **L1**。会話で sqlite 実装までは、DeepSeek 前回文脈実験ほど強くない（F5 は短い）。

---

## 5. F1〜F5 比較（特に A）

必要情報 Level は A が切り分けの主材料。B〜E は実 traceback/source が無い。

| 観測 | F1 | F2 | F3 | F4 | F5 |
| --- | --- | --- | --- | --- | --- |
| 事実認識 | 4フィールド | + 発生ファイル/行（A） | + `rows` / `rows[2]` / 長さ2（A） | F2+F3 | 会話の「Toolを作れ」が事実のように先行しうる |
| 未知の認識 | 弱い〜一般 | 行は分かる、list 内容は未知（traceback に name が無い） | 未知が消える（A） | 同左 | 分析対象が実装課題にずれる（DeepSeek） |
| 未知の具体性 | L0〜1 | L2〜3（場所） | L4（変数と index） | L4 | 低下 |
| 必要情報の具体性 | 「コードを見よ」未満〜弱 | 「4行目の index を確認」 | 入力に既にある | 同左 | 実装方法 |
| Tool Mapping可能性 | 粗い（read_file に落ちにくい） | **cpu_status.py:4 → read_file 相当** | 既に source あり。次は仕様（rows[2] の意味） | 同左 | 接続しにくい（新規実装） |
| 仮説の質 | 一般的 IndexError | データ不足仮説 | ほぼ不要 | ほぼ不要 | 誤った原因（psutil）がありうる |
| 事実/仮説混同 | 低 | Qwen がハーネスフレームを文脈化 | 低 | 低 | 高（DeepSeek） |
| 修正への飛躍 | 手順レベル | 手順 | **パッチ（DeepSeek）** | 記述中心 | **新規実装（DeepSeek）** |
| 根拠のない断定 | CPU監視の含意（弱） | 中 | 低 | 低 | IndexError と psutil の接続（DeepSeek） |

### F1 → F2

A では「どこで起きたか」（ファイルと行）が具体化する。list 名・index 値は traceback だけでは出ない（行ソースが traceback に載っていない）。B〜E は NOT_RECORDED の確認が増える程度。

### F1 → F3

A ではコード構造（`rows` 長さ2、`rows[2]`）が一気に分かる。未知の列挙より **原因特定 +（DeepSeek）修正** に飛ぶ。

### F2 → F4

相乗: F2 の場所 + F3 の意味。A では F3 だけでも構造は分かる。F4 は F3 を補強。traceback 単独より「なぜその行で落ちるか」が source で閉じる。

### F4 → F5

会話を足すと、DeepSeek は前回文脈実験と同様 **作業指示・実装** へ引っ張られる。Qwen A_F5 は実装には乗らず、ただし source が無いので F3/F4 より粗い。

---

## 6. DeepSeek / Qwen 比較

| 観点 | DeepSeek | Qwen |
| --- | --- | --- |
| F2 の行特定 | 使う | 使う。ハーネス名 `_traceback_for_a` を文脈に混ぜる |
| F3/F4 の変数特定 | 使う。パッチを出しやすい | 使う。**パッチを出さず分析で止める** ことが多い |
| F5 | 実装コードへ強い | A/C/E は短く分析寄り。完全には免れない |
| Do not fix | F3 で破る | A_F1 で「これ以上しない」と書く。F3 は説明のみ |
| Tool Mapping 材料 | F2 の行、F3 の変数 | 同様。F3 の方が Mapping 不要なくらい閉じる |

「賢い」ではなく、source 付きでは DeepSeek が修正、Qwen が短文分析、会話付きでは DeepSeek が実装、という差。

---

## 7. 予想外の挙動

- A の traceback に実験用 `exec` のフレーム（`_traceback_for_a`）が入り、Qwen がそれを実行経路として読む。
- F3 で source を渡すと、次情報の要求が減り、**分析段階が短くなる**（すでに答えがある）。
- NOT_RECORDED を DeepSeek は時々「無い」と明示する。分析の具体性はあまり上がらない。
- Qwen C_F1 が Failure JSON のキー数と「3 fields」を混線しうる。

---

## 8. Tool Mapping 可能性（人間評価。未実装）

| 出力の種類 | 接続しやすさ | 例 |
| --- | --- | --- |
| cpu_status.py の 4 行目 | 高い | `read_file`（パスと行） |
| `rows` と `rows[2]` を source 上で既知 | Mapping より「もうコードがある」 | 次は仕様・期待値 |
| code / logs 一般 | 低い | どのファイルか不明 |
| 新規 Tool 実装 | Mapping 対象外 | F5 DeepSeek |

LLM に Tool 名は出させていない。

---

## 9. 修正への飛躍

- DeepSeek A_F3: `rows[1]` への書き換え（意味的にも元データの 3 行目取得にはならない）。
- DeepSeek A_F5 / C_F5 / D_F5: 新規実装。
- Qwen A_F3/F4: 飛躍が小さい。
- F1 でも「直す手順」は文章で出ることがある（コードブロック未満）。

情報が増えると **分析 → 仮説 → 修正** が早まるのは A の F3 で顕著。F2 はまだ「確認せよ」。

---

## 10. 事実と仮説の混同

- 入力事実: error_type / error /（A F2）ファイルと行 /（A F3）`rows` 定義。
- 妥当な仮説: None の生成元、CUDA 環境、3 番目 field の欠落。
- 根拠の弱い推測: cpu_status = CPU 監視、data_loader の API。
- 断定に近い誤り: DeepSeek F5 の psutil 原因、Qwen F2 の `_traceback_for_a` を本番経路のように読むこと。

---

## 11. 設計上の示唆（未採用）

**観測事実**

- Failure だけでは Mapping 粒度に届きにくい。
- traceback だけで **発生箇所** は具体化する（行ソースが無いと変数名は残る）。
- source だけで **変数と index** は具体化する。同時に修正へ飛びやすいモデルがある。
- traceback + source は場所と意味を閉じる。次は仕様側の未知。
- 会話（「作ってください」）は分析を悪化させうる。

**仮説（確定しない）**

- Problem Analysis を独立させるなら、入力は Failure ± traceback ± source の方が、会話履歴より分析に残しやすい。
- source を先に渡すと「次に何が必要か」を聞く段階が省略される。Mapping 前に置きすぎると Repair になる。
- 正式採用・Schema・Mapping 位置はまだ決めない。

---

## 12. 未決事項

- traceback にソース行を載せる形式の差
- ハーネスフレームを除いた traceback
- 実ソースがある B〜E 相当ケース
- thinking を切った Qwen
- `Do not implement` を足す別 Prompt（今回は禁止どおり足していない）
- Problem Analysis を独立段階にするか
- 構造化の要否
- Tool Mapping を Analysis の前に置くか後に置くか

実行: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_context_split_bench`
