# 自己修復システムの構成

この文書は **モデルに依存しない** 自己修復の仕様である。  
特定 LLM の context 上限・プロンプト文体・材料の短縮は `config/llm_models.yaml` と `docs/llm/` に書く。ここへ混ぜない。

## 分離方針

| 層 | 置くもの | 置かないもの |
|---|---|---|
| CONTRACT | 最小固定の修復規則、JSON 形 | モデル名、種類ごとの直し方の長文 |
| STATE | タスク終了まで持ち回る確定事項（意味・単位・範囲） | 取得コマンド、LLM の推測 |
| MATERIALS | source、warnings、errors、research の command/sample | 契約条文、`rules` |
| PROFILE | 言語、密度、context 予算 | repair / research の分岐、契約条項の削除 |

実行時は `config/pipeline.yaml` の `active_model` が LLM プロファイルを指すだけである。分岐ロジックはプロファイルを読まない。  
一時的な上書きは環境変数 `AI_AGENT_MODEL`（プロファイル ID）で行う。

## ディレクトリ

```text
AI-Agent/
├─ agent.py
├─ tools/
│  ├─ system/          # 機械側: 検証・適用・調査・LLMクライアント
│  └─ ai/              # LLM に渡す材料と、モデル別プロンプト包装
│       ├─ state/      # TaskState。LLM は書き換えない
│       ├─ prompts/    # CONTRACT と STATE の文章化
│       └─ llm/        # PROFILE 包装
├─ registry/
├─ tests/
├─ config/
│  ├─ pipeline.yaml    # ベース
│  └─ llm_models.yaml  # LLM のみ
├─ docs/
│  ├─ architecture.md
│  ├─ scoring.md       # ベンチ採点仕様
│  ├─ validator.md
│  ├─ repair_types.md
│  └─ llm/             # モデル別メモ
└─ research/
   └─ llm_benchmarks/  # 実測。仕様ではない
```

## パイプライン

```text
USER_REQUEST
  → PROJECT_CONTEXT（事前に確定。実装手段は Agent）
  → CLARITY CHECK   「何が欲しい？」
      ├─ clear ──────────────────────────→ RESEARCH
      │
      └─ needs_clarification
         / insufficient_information
            ↓
         ASK_USER   （成果物だけ。実現方法は聞かない）
            ↓
         USER_REPLY
            ↓
         STATE 確定（source=user のみ）
            ↓
         RESEARCH   「どうやって取れる？」
            ↓
         JUDGE      「どの方法を採用するか」
            ↓
         IMPLEMENT → VALIDATOR → REPAIR
```

Clarity は **ユーザーが何を作りたいか** だけを判断する。実現方法は聞かない。

| status | 意味 | 次工程 |
|---|---|---|
| `clear` | 作りたい成果物が要求文で確定 | 質問せず Research |
| `needs_clarification` | 要求文から複数の成果物が成立し、選ぶと仕様が変わる | ユーザーに確認 |
| `insufficient_information` | 何を作るか分からない | ユーザーに確認 |

例: 「メモリを取得するTool」は `needs_clarification`（使用率・空き容量・総容量）。  
「メモリ使用率」は `clear`。  
「便利なメモリTool」は `insufficient_information`。

「PowerShell と CIM どちらがいいですか？」は Clarity の失敗である。エージェントが自分の仕事をユーザーに返している。PROJECT_CONTEXT の `implementation_method_selection: Agent` がそれを禁じる。

**Research で曖昧さを解決しない。** Research は確定した要求の実現方法を探す。候補が複数あってもユーザーには聞かない。Judge が採用する。

ユーザーが選んだ成果物だけを `source=user` で STATE へ昇格する。  
「使用率です」なら機械が `status.meaning=Windowsのメモリ使用率`、`status.unit=%`、`status.range=0-100` を書く。LLM の option.decisions は信じない。

実装:

- PROJECT_CONTEXT: `tools/ai/context/project_context.py`（Clarity の前。repair 孤立ベンチには入れない）
- 契約: `tools/ai/prompts/create.py` の `CLARITY_CONTRACT`
- 材料: `tools/ai/tool_builder/clarity.py`（調査 findings は入れない）
- 分岐と問答: `tools/system/tool_builder/clarity.py`
- 上限: `config/pipeline.yaml` の `max_clarity_rounds`

環境調査ベンチは **すでに clear な要求**（メモリ使用率）から始める。Clarity は測らない。

```text
実行 → Validator
  ├─ pass            → 完了
  ├─ repair          → LLM に修理材料を渡す → 再実行 → 再 Validator
  ├─ research        → 調査 → repair
  └─ research_repair → 調査済み → repair
```

エージェント状態:

- **pass**: 完了
- **warning**: 許容指摘のみ
- **fail / repair**: やり方は分かっているがコードが間違っている
- **blocked**: 実装に必要な情報がない → research

実装:

- 分岐: `tools/system/tool_builder/validate/warning_actions.py` の `first_pipeline_step`
- Repair 家族 R1〜R5: `tools/system/tool_builder/repair_family.py`（測定用。分岐をモデル別に変えない）
- 結果検証: `tools/system/tool_builder/validate/result.py`
- 適用: `tools/system/tool_builder/apply.py`
- 修理材料: `tools/ai/tool_builder/repair.py`（ファイルは触らない）
- プロンプト包装: `tools/ai/llm/adapter.py`（モデル別）

## 調査ゲート

`usable_findings` に `evidence.command` と `evidence.sample` があるときだけ、取得方法を実装してよい。  
この条件はベース仕様であり、LLM の得意不得意では変えない。

Research の候補は Verifier の前に機械が実行形へ直す。PowerShell がスクリプト本体だけで来ても `-NoProfile -NonInteractive -Command` に包む。許可リストはその実行形に対して判定する。LLM が argv を正しく書けたかは、実行可否の条件にしない。

コマンドが実行できたことは、要求を満たしたことではない。  
research のあと LLM が要求との差分を判断し、足りなければ `missing` を次の調査質問にして再調査する。  
停止は機械側が判定する。

- 要求を満たした / missing が解消した → 実装
- 新しい usable finding がある、または missing が変わった → 継続（停滞リセット）
- 同一 finding の重複だけ、または missing が同じ → 停滞 +1
- 連続 3 回進展なし、または `max_research_rounds`（10）到達 → 実装せず失敗

満たさないと判断した finding は `insufficient_findings` に移し、実装根拠にしない。

Judge はキー名ではなく sample の意味で要求充足を見る。`status` / `value` / `result` のような一般的なキー名だけを理由に不十分としない。

## 空 code の拒否

`code` が空の repair 案は適用しない。メッセージは `code がない repair 案は適用しない`。  
検証 NG、エージェントが捨てる、`apply_repair` が拒否する、の三段で同じ規則を守る。

## プロンプトの流れ

空の契約は使わない。最小限の固定契約がベースである。

```text
SYSTEM / CONTRACT     tools/ai/prompts/base.py（項目はモデルで消さない）
+ PROJECT CONTEXT     tools/ai/context/ + tools/ai/prompts/context.py（Clarity の前）
+ TASK STATE          tools/ai/state/ + tools/ai/prompts/state.py（確定事項）
+ TASK MATERIALS      tools/ai/tool_builder/repair.py（今回必要な事実だけ）
+ LLM PROFILE         tools/ai/llm/adapter.py（言語・密度・context 予算）
= 実際に LLM へ送る Prompt
```

1. CONTRACT は常に付ける。PROFILE は翻訳と圧縮だけで、条項を削除しない
2. Clarity には PROJECT_CONTEXT を STATE / MATERIALS より先に置く。実装手段の選択は Agent
3. STATE があるときだけその次に置く。MATERIALS より先に読ませる
4. MATERIALS はベースが選ぶ（source、warnings、errors、research の command/sample）
5. PROFILE は `current_source` の切り詰めと compact JSON など予算だけを変える
6. `tools/system/llm.py` が timeout / num_predict / keep_alive で呼ぶ

STATE はタスク終了まで持ち回る。LLM は読めるが直接は書けない。Clarity でユーザーが選んだ成果物は、機械カタログ経由で `source=user` で昇格する。Judge が `satisfies_request` のとき `proposed_decisions` を出し、機械側が確認してから `source=judge` で昇格する。実装層・修理層の孤立ベンチは `state=None` かつ PROJECT_CONTEXT なしのままなので、従来のプロンプトは変わらない。

## 環境調査ベンチ

`research/llm_benchmarks/environment_benchmark.py` は、正解コマンドを渡さずに新規Tool作成を測る。

```text
clear な要求（Clarity 済み。ベンチはメモリ使用率）
  → 設計
  → RESEARCH → JUDGE
      ├─ 要求を満たした → 確定事項を STATE へ → 実装
      └─ 不足 → RESEARCH
            ├─ 新しい情報 → 継続
            └─ 進展なし → 停滞。連続3回または10回で実装せず失敗
  → 実行
  → Validator
  → 必要なら自己修復（STATE は消さない）
```

`Get-CimInstance Win32_OperatingSystem` などは MATERIALS に入れない。  
Verifier の安全許可リストは実行可否であり、プロンプトではない。

種類ごとの直し方は CONTRACT に書かず、MATERIALS の `warning.fix` に載せる。

## 実装層の評価

Research / Judge と Implementation は分けて測る。

```text
Research → Judge → Implementation → Validator → Repair
                      ├─ finding 採用
                      ├─ code 生成
                      └─ command 一致
```

失敗分類は `tools/system/tool_builder/implementation_classify.py`。
所要時間は `tools/system/timing.py` が記録する。採点にはまだ使わない。

| class | 意味 |
|---|---|
| `ok` | 要求を満たす finding だけを使う |
| `finding_not_used` | 要求を満たす finding を使わない |
| `unnecessary_finding` | 正解に加えて不要な finding も使う |
| `empty_code` | code が空 |
| `wrong_command` | usable_findings にないコマンドを実装する |

固定 findings で実装だけを回す: `python -m research.llm_benchmarks.implementation_benchmark`

比較: `python -m research.llm_benchmarks.history`

class は機械分類、PASS / score / grade は `docs/scoring.md`。必要な finding がすべてあれば PASS。単一選択で余分を足すのは軽微減点。複数必要なのに1つだけ使うのは FAIL。

単一選択 `implement_single_select_memory_usage`、複数選択 `implement_multi_select_usage_and_available`、組み合わせ `implement_combine_total_and_used_to_usage`。

工程別モデルは `stage_model_id` まで用意してあり、本番パイプラインはまだ `active_model` 一つである。

## Context Persistence ベンチ

`research/llm_benchmarks/persistence_benchmark.py` は、モデルの推論力ではなく **確定した意味を後半まで維持できるか** を測る。

第一テスト `persist_status_unit_baseline` は STATE なし。要求と Tool 結果（`status=43.2`）を MATERIALS に残し、「statusの単位は何ですか？」と聞く。記録は `%` 正誤だけではなく、

* メモリ使用率の話として認識したか
* status を今回のToolの値として認識したか
* `%` と判断したか

の3つに分ける。ラベルは LLM に渡さない。

曖昧化テスト `persist_unit_ambiguous` は質問を「この値の単位は？」だけにする。質問から status / メモリ / 使用率 を消し、MATERIALS は `status=43.2` だけ。根拠は `state_based` / `value_inference` / `general_knowledge` / `unknown` に分ける。

時間・作業を挟むテスト `persist_unit_gap` は同じ最終質問で、間に無関係な処理を 0 / 1 / 4 回入れる。STATE オブジェクトは持ち回り、最終プロンプトにも再注入する。`STATE_LOST` ならエージェントの保存漏れ、reason が value_inference に落ちるなら LLM が STATE を参照しなくなった、と切り分ける。

```text
python -m research.llm_benchmarks.persistence_benchmark
```

## Clarity ベンチ

`research/llm_benchmarks/clarity_benchmark.py` は Research の前の明確さ判断だけを測る。PROJECT_CONTEXT を渡し、Research findings は渡さない。

| ケース | 要求 | 期待 |
|---|---|---|
| `clarity_memory_usage` | Windowsのメモリ使用率を取得するTool | `clear` → research |
| `clarity_memory_ambiguous` | Windowsのメモリを取得するTool | `needs_clarification`（使用率・空き・総容量） |
| `clarity_memory_vague` | 便利なメモリToolを作って | `insufficient_information` |

採点は status だけでなく質問内容も含む。

1. 要求が明確か判断できた（`status_ok`）
2. 必要な場合だけ質問した（`asked_only_when_needed`）
3. 質問内容がユーザーの決定事項だった（`user_decision_question`）
4. 実装方法をユーザーに丸投げしなかった（`did_not_delegate_method`）
5. Research に正しく引き渡した（`handed_to_research`。隔離と PROJECT_CONTEXT を含む）

「使用率・総容量・空き容量のどれですか？」は適切。「PowerShell / WMI / CIMのどれですか？」は不適切。

```text
python -m research.llm_benchmarks.clarity_benchmark
```

## Clarity → STATE → Research

`research/llm_benchmarks/clarity_state_research.py` は、最初から STATE がある持続性ベンチではない。会話から作る。

```text
「Windowsのメモリを取得するToolを作って」
  → Clarity「どれが必要ですか？」
  → 「使用率です」
  → 機械が STATE を生成（source=user）
  → Research / Judge に同じ STATE を渡す
  → MATERIALS は status=43.2 だけ。「このToolが返した 43.2 は何を表していますか？単位も答えてください。」
```

見る点は4つ。

1. ユーザー回答が STATE になる（meaning / unit / range、`source=user`）
2. Research に STATE が渡る
3. Research/Judge が 43.2 を Windowsのメモリ使用率として扱う
4. Research が user の confirmed を書き換えない

```text
python -m research.llm_benchmarks.clarity_state_research
```

## Research → Implementation

`research/llm_benchmarks/research_implement.py` は、Research で確定した実現方法を Implementation が実際の Tool にできるかを測る。Repair は見ない。

```text
「Windowsのメモリを取得するToolを作って」
  → Clarity「どれが必要ですか？」
  → 「使用率です」
  → STATE を保持
  → 「Windowsのメモリ使用率を取得するToolを作ってください。」
  → RESEARCH → JUDGE → IMPLEMENT
  → Registry 登録 → 実行
```

見る点は6つ。

1. Research が適切な方法を選ぶ（command と sample がある usable finding）
2. Judge が採用する（`satisfies_request`）
3. Implementation が実際にコードを生成する
4. 生成コードが Research で採用した方法と一致する
5. Tool が既存 Registry / Tool 構造に入る（`tools.system.*`）
6. 実行できる（例外なく return する）

失敗したときだけ工程を分ける。`fail_stage` は `research` / `judge` / `implementation`（設計案が出せないときだけ `proposal`）。  
実行結果の整形や Validator 指摘の直しは ⑤ Repair に残す。

④本体はいったん止める。保存ケースは `cases/judge_verify_failed_retry.json`。

## Verifier 失敗 → Judge 再調査

`research/llm_benchmarks/judge_verify_retry.py` は、Verifier が候補を実行して失敗したあと、Judge が JSON で `missing` を返し再調査に戻れるかだけを見る。Implementation は回さない。

保存した実測では、候補は実行されたが 0 除算で sample が空、Judge は `no_json` でループが止まった。

```text
Research → 間違った候補 → Verifier（実行できたが要求を満たさない）
  → Judge → missing → 再調査
```

見る点は、JSON が取れることではなく **missing の質** である。再調査へ戻れること自体は確認済み。

| 判定 | 意味 |
|---|---|
| A | 要求達成に必要な不足対象（総物理メモリ、使用中メモリなど）を具体化できる |
| B | エラーは認識するが、方法だけを示す曖昧な missing |
| C | エラー文をそのまま missing に入れる |
| FAIL | JSON を返さない、または成功扱いする |

正解コマンドは契約にも採点にも入れない。A が揃ってから ④ 本体に戻る。

契約修正前の C baseline は `judge_verify_retry_baseline_c.json` に固定。修正後は同じケース・同じ材料で再試験し、A を合格基準とする。

```text
python -m research.llm_benchmarks.judge_verify_retry
```

## 機械的補助（表）

PowerShell の

```text
LoadPercentage
--------------
28
```

のような既知の表は、Validator が `header` / `separator` / `value` に分解して evidence に載せる。  
LLM に「どうパースするか」を考えさせない。

将来の選択肢: Tool 側で JSON/CSV を取る標準にし、この種の自己修復自体を減らす。

## 失敗履歴

`research/llm_benchmarks/repair_failures.json` は残す。  
環境調査の既知失敗は `research/llm_benchmarks/cases/` と `environment_blacklist.yaml`。  
参照 API は `tools/system/llm_failure_memory.py`。いまは repair ループに接続しない。
