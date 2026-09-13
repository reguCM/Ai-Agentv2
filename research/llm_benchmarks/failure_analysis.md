# 失敗パターン分析（qwen 3回 / deepseek 3回）

通常の unittest とは別。自己修復の分岐仕様ではない。

条件は両モデル共通: `temperature: 0`, `num_predict: 2048`, `context_limit: 4096`, `max_repair_rounds: 3`。

## 成功率

| モデル | run1 | run2 | run3 |
|---|---|---|---|
| qwen3_8b | 6/6 | 6/6 | 6/6 |
| deepseek_coder_v2_16b | 3/6 | 3/6 | 3/6 |

deepseek の NG は3回とも同じ3ケース。PASS も同じ（②③⑥）。

## なぜ3回とも同じか（共通原因）

1. **temperature=0** でほぼ決定的に同じ出力になる
2. 入力（fixture・MATERIALS・CONTRACT・PROFILE）が毎回同じ
3. 3ラウンド回しても、モデルが同じテンプレを出し直す。ループが学習しない

再現しているのは「運」ではなく、**同じ入力に対する同じ事前分布**である。

## deepseek の3失敗

### ① unparsed_output → `runtime_exception_after_repair`

生成コード（3回とも同型）:

```python
lines = result.stdout.strip().split('\n')
load_percentage = lines[1].split('\t')[1].strip()
```

実際の stdout は PowerShell 表:

```
LoadPercentage
--------------
            28
```

`lines[1]` は区切り線。`split('\t')[1]` で `IndexError`。

- **分類**: 機械側で補助する。既知の PowerShell 表は Validator が `header` / `separator` / `value` に分解する。LLM は `parsed_table.value` を status に入れる
- **やらないこと**: 「最初の数値を正規表現で取れ」をベース仕様にしない。DeepSeek 専用ルールも入れない
- **将来**: Tool が JSON/CSV で表を取る標準になれば、この種の repair 自体が減る

### ④ subprocess_result_handling → 同じ `runtime_exception_after_repair`

fixture は returncode 未確認 **かつ** stdout 生出力。開始時の codes は `unparsed_output` + `subprocess_result_handling`。

生成コードは returncode を見るように直したうえで:

```python
result.stdout.splitlines()[1].split(': ')[1]
```

subprocess の穴は塞がるが、①と同じ固定パースで落ちる。

- **分類**: ①と同じ機械補助。④の NG を「returncode が直せない」と読むと誤る
- **注意**: 生出力が残っているなら `parsed_table` を subprocess の evidence にも載せる

### ⑤ stub_value → `stub_not_implemented`

生成コード（3回とも）:

```python
def cpu_status():
    return {'status': '未実装'}
```

`usable_findings` に command / sample があるのに、スタブをそのまま返す。JSON は通るので apply され、3ラウンド後も同じ。

- **分類**: LLM に任せる領域。stub → research → command/sample/finding → 実装、は推論が必要
- **機械側ではない**: research_repair 分岐は正しい。プロンプト強化はしない
- **残す事実**: research があるのに未実装のまま返した、は `repair_failures.json` に残す
- **将来**: `tools/system/llm_failure_memory.py` で「このモデルは research 結果を実装しなかった」を参照する。いまは repair ループに接続しない

## qwen 側

後続3回は 6/6。temperature=0 後は ④⑤ も安定して通る。  
以前の 5/6（④で `{'status':'error'}`）は条件固定前の揺れ。分析対象は固定後の6回を優先する。

## 機械側 / LLM依存の切り分け（確定）

| 現象 | 機械側 | LLM依存として残すこと |
|---|---|---|
| 3回同一 | temperature=0 で再現性は取れている | — |
| ①④ の IndexError | Validator が表を `header` / `separator` / `value` に分解する | 分解済み value をキーへ入れる作業 |
| ④ の二重指摘 | 表材料は両方の warning に載せる | モデルが両方を一気に「直したつもり」になること |
| ⑤ のスタブ据え置き | 失敗履歴を残し、後から参照できる形にする | stub → findings → 実装 |
| ②③⑥ PASS | — | 構造修正・コマンド置換 |

DeepSeek 向けにプロンプトを増やすのは止めた方針を維持する。
