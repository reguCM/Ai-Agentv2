# AI-Agent Tool Calling 命名・設計規約整備指示書

## 1. 目的

本作業の目的は、単にコードをきれいにするための命名規則を作ることではない。

**Tool Calling機能をLLMが正しく理解・選択・実行できるようにすること**を最上位の目的とする。

したがって、Toolの命名・description・引数定義などに関する規則は、

> 「Tool Callingを安定して成立させるための規則」

として設計すること。

命名規則そのものを絶対視してはならない。

Tool Callingとして正常に機能している既存Toolについて、単に命名規則に合わないという理由だけで無理に変更してはならない。

---

# 2. 規則の優先順位

Toolに関する規則を以下の2段階に分ける。

## 【必須】Tool Calling成立条件

これらはTool Callingを正常に利用するための基本条件であり、原則として違反を許容しない。

例：

- Tool名が一意である
- Tool名がTool Callingで利用可能な形式である
- Tool Schemaが正しい
- 引数の型が明確である
- 必須引数・任意引数が正しく定義されている
- descriptionが存在する
- descriptionからToolの目的・用途が理解できる
- 実際の実装とSchemaが一致している
- Tool CallをAgent Runtimeが正しく受け取れる
- Tool Callの引数を検証できる
- Tool実行結果をLLMへ返却できる
- 同じ目的のToolとの区別が可能である

これらに問題がある場合は、原則として登録・利用前に修正する。

---

## 【推奨】LLMのTool選択・理解を助ける設計規則

こちらはTool Callingの成功率、Tool選択の正確性、保守性を高めるための推奨事項とする。

例：

- Tool名は「動作＋対象」を基本とする
- できるだけ具体的な名称にする
- 1つのToolに複数の無関係な責務を持たせない
- descriptionに「何をするToolなのか」を明確に書く
- 引数名は用途が分かる名前にする
- 同じ種類のToolでは命名パターンを揃える
- 曖昧な名前を避ける

ただし、これらに違反した場合は、原則として `WARNING` とする。

**推奨規則違反だけを理由としてToolを登録拒否してはならない。**

---

# 3. 基本命名パターン

新規Toolでは、原則として以下の形式を推奨する。

```text
動作_対象
```

例：

```text
get_gpu_status
get_gpu_processes
read_file
search_files
write_file
run_test
analyze_test_result
create_report
generate_image
inspect_image
```

この形式を推奨する理由は、LLMがTool名を見たときに、

> 「何をするToolなのか」

を判断しやすくするためである。

ただし、

```text
gpu_status
pytest
file_reader
```

のような名称であっても、descriptionやSchemaが適切で、Tool Callingが正常に機能するのであれば、必ずしも変更する必要はない。

---

# 4. Tool名で避けるもの

以下はTool Calling時の混同を防ぐため、原則避ける。

### 4.1 意味が曖昧な名前

```text
tool1
helper
manager
process
data
system
action
```

何をするToolなのかTool名から判断できないため。

### 4.2 複数の意味を持つ名前

```text
file_tool
system_tool
ai_tool
network_tool
```

実際の責務が広すぎる場合、LLMが適切なToolを選択しにくくなる可能性がある。

### 4.3 似すぎた名前

```text
read_file
read_files
file_read
read_file_data
```

これらが同時に存在する場合は、LLMが用途を混同する可能性がある。

ただし、実際に区別する必要があるToolであれば、descriptionや引数定義を含めて区別できる設計にする。

---

# 5. descriptionを命名規則と同等以上に重視する

Tool Callingでは、Tool名だけでなくdescriptionがLLMのTool選択に重要な情報となる。

そのため、新規Toolでは以下を明確にする。

```text
何をするToolか
何を対象とするか
いつ使用するか
何を返すか
```

例えば、

```text
get_gpu_status
```

だけではなく、

```text
GPUのモデル名、温度、使用率、VRAM使用量など、
現在のGPU状態を取得する。
GPUの現在状態を確認する必要がある場合に使用する。
```

など、LLMが利用場面を判断できるdescriptionを設定する。

---

# 6. 1 Tool = 1つの明確な責務

原則として1つのToolには1つの明確な責務を持たせる。

例えば、

```text
get_gpu_status
```

はGPU状態取得。

```text
get_gpu_processes
```

はGPUを使用しているプロセス取得。

とする。

一方、

```text
gpu_manager
```

に

- GPU状態取得
- プロセス取得
- プロセス停止
- ドライバ変更
- GPU設定変更

などをすべて詰め込むことは避ける。

ただし、既存ソフトウェアのAPIや外部仕様によって合理的な理由がある場合は例外を認める。

---

# 7. 既存ソフトウェア・外部APIは無理に改名しない

本プロジェクトでは、

> 「既存ソフトウェアを利用できるなら、まず利用する」

という方針を採用する。

そのため、外部API・CLI・既存ソフトウェアをTool化する際、

```text
外部仕様の名前
        ↓
Toolとして登録
```

する必要がある場合、その名前を無理にプロジェクト内の命名規則へ変更しない。

必要であればAdapterを設ける。

```text
Agent
 ↓
Project Tool
 ↓
Adapter
 ↓
既存ソフトウェア/API
```

この場合、重要なのは名称の美しさではなく、

**LLMがToolを正しく選択でき、Tool Callingが正常に成立すること**

である。

---

# 8. Tool名だけで判断しない

AgentはTool選択時に、

```text
Tool名
+
description
+
parameters
+
現在のユーザー要求
+
Toolの過去の実行結果
```

などを総合して判断する。

したがって、

> 「Tool名が分かりやすければ十分」

とは考えない。

命名規則はTool Calling設計の一部分である。

---

# 9. Tool登録時のValidator

Tool Registryへの登録時には、Tool Calling成立条件を自動検査するValidatorを設ける。

Validatorは少なくとも以下を確認する。

### ERROR

Tool Calling成立に影響する問題。

例：

```text
Tool名が存在しない
Tool名が重複している
Schemaが不正
引数型が不正
実装とSchemaが一致しない
descriptionが存在しない
必須引数の定義が不正
Tool Callを実行できない
```

→ 登録・使用を原則停止する。

### WARNING

Tool Calling自体は成立するが、LLMによる理解・選択・保守性に問題がある可能性。

例：

```text
動詞＋対象になっていない
名前がやや曖昧
descriptionが短すぎる
類似Toolとの名前が近い
責務がやや広い
```

→ 原則として登録は可能。

必要に応じて改善する。

---

# 10. Tool Calling実測テストを規約改善に利用する

命名規則やdescription規則は、机上で完全なものを決めない。

実際のLLMを使用してTool Callingテストを行い、その結果を規約改善に利用する。

最低限、以下を確認する。

```text
ユーザー要求
 ↓
LLM
 ↓
正しいToolを選択できるか
 ↓
正しい引数を生成できるか
 ↓
Tool実行
 ↓
結果を正しく理解できるか
```

さらに複数Toolが存在する場合、

```text
Tool A
Tool B
Tool C
```

の中から正しいToolを選択できるかを確認する。

---

# 11. 例外を正式に記録する

規約から外れるToolが必要になった場合、

> 「規約違反だから無条件に修正する」

とはしない。

以下を確認する。

```text
なぜ例外が必要なのか
↓
Tool Callingに問題はあるか
↓
実際のテスト結果はどうか
↓
既存ソフトウェアの制約はあるか
↓
規約自体を変更すべきではないか
```

例外が合理的である場合は、例外として記録する。

---

# 12. 規約はバージョン管理する

この規約は固定された絶対的な正解ではない。

実験・障害・LLMの変更・Tool数の増加・既存ソフトウェアとの統合などによって、より適切なルールが発見された場合は更新する。

例：

```text
v1.0
 ↓
Tool Callingテスト
 ↓
問題発見
 ↓
原因分析
 ↓
v1.1
 ↓
再テスト
```

規約の変更履歴を必ず残す。

---

# 13. 規約変更の理由を知識として残す

単純な変更履歴だけではなく、可能な限り以下を残す。

```text
変更対象
変更前
変更後
発生した問題
発生条件
原因候補
実施した実験
実験結果
考察
変更理由
変更後の期待効果
残っている問題
今後の検証事項
```

特に重要なのは、

> 「なぜ以前の規則では不十分だったのか」

を残すこと。

これにより、将来別のLLMや別のTool構成へ変更した際に、過去の問題を再調査するための資料として利用できる。

---

# 14. 推奨ファイル構成

以下のような構成を検討する。

```text
docs/
└── tool_calling/
    ├── TOOL_CALLING_RULES.md
    ├── TOOL_CALLING_CHANGELOG.md
    ├── TOOL_CALLING_EXCEPTIONS.md
    └── experiments/
        ├── ...
        └── ...
```

役割は以下とする。

### TOOL_CALLING_RULES.md

現在有効な規約。

### TOOL_CALLING_CHANGELOG.md

規約のバージョン変更履歴。

### TOOL_CALLING_EXCEPTIONS.md

現在存在する例外と、その理由。

### experiments/

Tool Callingに関する実験結果。

---

# 15. 「指示書に書かなくても機能する」仕組みにする

重要なのは、毎回Cursorへの指示書に、

```text
Tool名は○○にしてください
descriptionは○○にしてください
```

と書かなくても、この規約が適用される状態を作ることである。

そのため、プロジェクトの基本ルールとして、

```text
TOOL_CALLING_RULES.md
```

を正式なプロジェクト規約として扱う。

Cursor、Local Agent、その他の開発担当がToolを新規作成・変更するときは、原則としてこの規約を参照する。

さらに可能であれば、Tool Registry登録時にValidatorを実行し、

```text
実装者が忘れる
        ↓
Validatorが検出
```

できるようにする。

つまり、

```text
人間の指示
   ↓
規約
   ↓
実装
   ↓
自動Validator
   ↓
Tool Calling実測テスト
   ↓
結果
   ↓
規約改善
```

という構造を目指す。

---

# 16. 規約よりTool Callingの実測結果を優先する

規約と実測結果が矛盾した場合は、その矛盾を記録して検討する。

例えば、

```text
規約：
「動詞から始めるとTool Callingに適している」

実験：
動詞から始めないToolでも同等以上の選択精度だった
```

場合、

> 「規約が間違っている可能性」

を検討する。

逆に、

```text
規約：
「descriptionを具体的にする」

実験：
descriptionを改善した結果、
類似Tool間の選択ミスが減少した
```

のであれば、その結果を規約の根拠として記録する。

---

# 17. 最上位原則

本規約における最上位原則を以下とする。

> **Toolの命名・Schema・description等は、Tool CallingをLLMが正しく理解・選択・実行するために設計する。**

そして、

> **命名規則そのものを目的にしない。**

さらに、

> **現在の規約は現時点で得られた実験結果・問題・考察に基づく「現在の最適解」であり、新しい実験結果によって変更され得る。**

例外が発生した場合は単に規約違反として処理するのではなく、

```text
例外
 ↓
原因
 ↓
実験
 ↓
考察
 ↓
規約変更の必要性を判断
```

という流れで扱う。

---

# 18. 今回の作業範囲

今回の作業では、いきなり大量のToolを変更しない。

まず現在のTool Registry、既存Tool、Tool Calling実装、Validator等を確認し、

1. 現在のTool Calling構造を確認
2. 現在の命名状況を確認
3. 必須条件と推奨条件を分類
4. `TOOL_CALLING_RULES.md` を作成
5. `TOOL_CALLING_CHANGELOG.md` を作成
6. 必要に応じて `TOOL_CALLING_EXCEPTIONS.md` を作成
7. Tool登録時のValidator方針を整理
8. 現在のToolでTool Calling実測テストを行う
9. 問題があれば規約を修正
10. TASK / REPORT / STATEとして作業結果を記録

という順序で進める。

既存のToolや過去の実験資料については、規約に合わないという理由だけで削除・大規模変更しない。

---

# 19. 今後の位置付け

この規約は、今後のAI-Agent開発における共通基盤とする。

Cursor、Local Agent、その他のAI開発担当がToolを追加・変更する場合でも、個別の作業指示書に詳細な命名規則を毎回記載することを前提としない。

各担当はプロジェクト規約を参照し、Validatorと実測テストによって規約への適合性を確認する。

また、Tool Calling対応モデル、専門LLM、モデル変更等によって新しい問題が発生した場合は、その結果を実験記録へ残し、必要に応じて規約をバージョンアップする。

**最終的な目的は「規約を守ること」ではなく、「AI-AgentがTool Callingを安定して使いこなせる状態を作ること」である。**