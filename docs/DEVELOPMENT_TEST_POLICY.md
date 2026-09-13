# Development Test Policy v1

## 1. 目的

本Policyは、Component test、mock test、Sandbox内部testのPASSだけで、Agent機能全体や実運用経路まで完成したと判断することを防ぐ。

テスト階層、E2E Goal Acceptance、Verification Budget、Evidence Reuse、およびE2E Failure後の修正手順については、本書を正本とする。

## 2. テスト階層

### Level 1 — Component Test

個別関数、Tool、Runtime部品、Schema、判定ロジックが決定論的に正しく動くことを確認する。

対象例：

- pure function、Schema validation
- Tool単体
- mock LLM、fake Tool Result、monkeypatch
- `tmp_path` fixture
- Sandbox Path Guard

Component PASSが保証するのは部品単体の正しさであり、Agent機能全体の完成ではない。

### Level 2 — Integration Test

複数部品の接続が成立することを確認する。

対象例：

- Agent Loop → Tool
- Tool Registry → Gate → Tool実行
- Tool Result Contract → Runtime
- Task Runtime → Completion
- Sandbox Session → Mutation Tool
- fake LLMを含むAgent接続

Integration PASSは対象接続を保証する。mock、fake、monkeypatchを含む場合は、実LLM E2Eの成功証明にはならない。

### Level 3 — E2E Goal Acceptance

実際の利用経路で、ユーザー要求がAgentによって最後まで完遂されたことを確認する。

```text
User Input
→ 実LLM
→ Agent Loop
→ Registry / Gate
→ 実Tool
→ Tool Result
→ Evidence
→ Task State
→ Goal State
→ Completion
→ Final Answer
→ Goal Acceptance
```

例外がない、Toolが`success`、Final Answerが存在する、という個別事実だけではE2E PASSにならない。

名前にE2Eを含んでいても、実LLM、実Agent Loop、実Tool、Goal Acceptanceを通さないテストは正式なGoal Acceptance E2Eとして扱わない。

## 3. Goal Acceptance PASS条件

対象Test Caseで要求される次の条件を、機械的なRuntime事実によりすべて満たした場合だけPASSとする。

- User Goalが記録されている
- 実LLM応答を受信している
- 必要Toolが選択されている
- 必要Toolが実行されている
- Tool ResultがRuntimeへ返却されている
- 必要Evidenceが存在する
- 必須Taskが`complete`である
- Final Goalが`complete`である
- Final Answerが存在する
- Blocking状態ではない

Test Caseで不要または観測不能な項目は`null`または`not_required`としてよい。既存のRun `status=completed`とGoal Acceptance PASSは別概念とする。

## 4. 完了判定と報告

新規Agent機能、Runtime統合、Tool連携をComponent PASSだけで「完成」と記載しない。フェーズ完了報告には必ず次を明記する。

- Component: `PASS | FAIL | NOT_RUN`
- Integration: `PASS | FAIL | NOT_RUN`
- E2E Goal Acceptance: `PASS | FAIL | NOT_RUN`

E2E未実施時は「内部実装完了」「Component/Integration確認済み」と表現できるが、「実運用確認済み」「Agentとして完了」「E2E完成」とは記載しない。

## 5. E2Eを必須とするタイミング

毎変更で実LLM E2Eを大量実行する必要はない。ただし、次の場合は最小E2Eを少なくとも1件実施する。

- 新しいAgent経路を追加した
- ToolとAgent Loopを新しく接続した
- Tool Result BridgeまたはEvidence接続を変更した
- Task / Goal RuntimeまたはCompletion判定を変更した
- Recovery経路を変更した
- Requirement / Agent Task Entry境界を変更した
- RuntimeとLLMの責務境界を変更した
- フェーズまたはマイルストーンを完了扱いする

## 6. Verification BudgetとEvidence Reuse

実LLM E2Eは時間、GPU、外部サービスや上位LLMのクレジットを消費する。再検証前に既存Evidenceを確認し、次の区分を使う。

### REUSE

- 過去Evidenceが十分
- 関連コードと環境に変更がない
- 再実行が今回の判断を変える可能性が低い

この場合は再実行しない。

### SPOT_CHECK

- 一部の境界だけを変更した
- 軽い不確実性が残る

この場合は関連部分だけ確認する。

### RERUN

- 関連コード、Contract、環境が変わった
- 過去Evidenceが矛盾している
- 前回FAILした
- 保証範囲がComponentからE2Eへ変わった

「念のため」「実行できるから」だけを理由に全テストを再実行しない。

## 7. E2E Failure時の修正手順

E2E Failureが発生しても、同時に複数層を修正しない。

1. 最初の因果的Failureを特定する
2. `failure_stage`を記録する
3. その境界だけを最小修正する
4. 必要最小限の決定論的テストを行う
5. 同じE2Eを1回だけ再実行する
6. 次の停止地点を観測する
7. 次のFailureへ進む

例えば`TASK_CREATION`を直した再実行で`EVIDENCE`が次の停止地点になった場合、その時点で初めてEvidence境界を次工程として扱う。Evidence、Completion、Recovery、Gateを一度に修正しない。

## 8. Failure Stage

共通の最小分類は次とする。必要に応じた追加は可能だが、細分化しすぎない。

- `INPUT`
- `REQUIREMENT`
- `LLM`
- `TASK_CREATION`
- `TOOL_SELECTION`
- `TOOL_GATE`
- `TOOL_EXECUTION`
- `TOOL_RESULT_BRIDGE`
- `EVIDENCE`
- `TASK_COMPLETION`
- `GOAL_COMPLETION`
- `FINALIZATION`
- `RECOVERY`
- `ENVIRONMENT`
- `UNKNOWN`

## 9. mock / fake test

fake LLM、fake Tool Result、monkeypatch、deterministic Tool selection、synthetic fixture、Sandbox内部testは、高速で再現性が高く、回帰検出に有効である。削除対象ではない。

ただし、結果報告ではComponent / Integrationと実LLM E2Eを明確に分離する。

## 10. Test Fixture

- Component testはGit管理された小型fixtureを使用する
- Integration testは再生成可能なfixtureを優先する
- 過去Run artifactが必要な場合は`artifact-required integration test`と明示する
- E2Eは実Runを新規生成する
- Git管理外artifactを暗黙の前提にしない

artifact不足による失敗をAgentロジックFAILと誤判定しない。

## 11. 環境問題

次はAgentロジックFAILと分離し、必要に応じて`ENVIRONMENT_BLOCKED`または`SETUP_FAIL`として扱う。

- fixture missing
- permission / ACL
- temp directory
- model unavailable
- Ollama unavailable
- dependency missing
- wrong worktree / wrong commit
- Sandbox Session unavailable

環境失敗をGoal Acceptance PASSにはしないが、AgentロジックFAILとも混同しない。

## 12. Communication Reliability

LLM、Agent間通信、CLI、API、Transport等の通信依存機能は、正常通信だけをもって
実運用品質確認済みとは扱わない。確認した範囲と未対応項目を分離して報告する。

### Normal

- 正常なRequest / Responseを最小の実通信で確認する
- 実providerとmodelへ到達可能であることを確認する
- profile IDとprovider固有のmodel IDを区別し、正しく解決する

### Timeout

- timeout上限を設け、無限待機を禁止する
- timeoutは通信Failureとして分類する
- Runtime StatusまたはFailure Evidenceへ停止理由を残す
- Long Running表示とtimeoutによる停止を混同しない

### Busy / Overload

- 観測可能な場合はBusy / Overloadを明示的に分類する
- 自動retryを行う場合も限定回数とする
- 未対応の場合はその事実を明示し、通常のAgent Logic Failureと混同せず、AlertまたはCommunication Failureとして扱う

### Retry

retryを導入する場合は、最低限次を定義する。

- `max_retries`
- retry対象Error
- retry禁止Error
- waitまたはbackoff

無限retryは禁止する。retryを実装していない場合は「未対応」と明示する。

### Request / Response対応

既存構造で可能な範囲において、次を確認する。

- correlation IDまたはrequest ID
- stale responseの拒否
- Cancel後に到着したResponseの拒否
- duplicate responseの誤採用防止

存在しない仕組みを確認済みと報告しない。未導入項目は「未対応」と明示する。

### Failure分類

最低限、次を区別する。

- Agent Logic Failure
- Communication Failure
- Environment Blocked

通信Failureを`TOOL_SELECTION`、Task Failure、Goal Failureへ誤分類しない。

### Test方法

- 正常系は実provider/modelへの最小通信で確認する
- Busy、timeout、retry、stale、duplicate等は、可能な限りmock / fakeを用いたTransportまたはAdapter層の決定論的テストで確認する
- 実LLM/APIを大量消費する反復試験は避ける
- 再確認範囲には本PolicyのREUSE / SPOT_CHECK / RERUNを適用する

### B-3R参考例

- profile ID `qwen3_14b`をOllama model IDとして直接送信した結果、`ResponseError`になった
- provider上の実名`qwen3:14b`へ解決することで正常通信した
- timeout上限、Long Running、Cancel後およびstale TurnのResponse拒否は実装済み
- Busy明示分類、retry、backoff、duplicate response検出は未対応
- Requirement通信Failureは`COMMUNICATION_FAILURE` / `ENVIRONMENT_BLOCKED`としてAgent Logic Failureから分離する

## 13. E2E実行Evidence

可能な範囲で次を保存する。Recorderが既に保持する情報は再実装しない。

- run_id、timestamp
- Git HEAD、branch、cwd
- model、Registry hash
- Test Case ID、prompt
- tool_calls、tool_results
- evidence_count
- task_states、goal_state
- final_answer_present
- stop_reason、recovery_count
- llm_call_count、tool_call_count、elapsed_time
- goal_acceptance
- failure_stage、failure_category

## 14. Phase Bの適用例

### Phase B-1

- Tool実行とFinal Answerは成功
- Goal 0 / Task 0 / Evidence 0
- Goal AcceptanceはFAIL
- 最初の因果的Failureは`TASK_CREATION`

### Phase B-2

- `TASK_CREATION`境界だけ修正
- Goal 3 / Task 2へ前進
- Tool実行は成功
- Evidence 0
- 次の停止地点は`EVIDENCE`

これは、最初のFailureだけを修正し、同じE2Eを1回再実行して次の境界を発見する運用例である。

## 15. Generation-Time Assumption Check

Runtime、Tool、Capability、Model、Provider、Registryの連携を新規実装または変更する場合、
実装前またはdiff確定前に最低1回、固定前提を作っていないか軽量確認する。毎回の大規模監査は
要求しない。

### Identityと正本

- Registry ID、internal ID、provider ID、display name、schema上のnameを混同しない
- Tool name、Capability、category、visibility、keywords、observation source、output field、
  provider model ID、permission / execution metadataは、既存Registry、Schema、Contractから
  取得できるならそれを正本とする
- 正本にある動的値を別の固定allowlistやliteral集合へ複製しない

### 新しい固定表現

keyword list、regex、Tool allowlist、Tool名・field名・model名の集合、capability→tool map、
provider固有literalを追加する場合は、次のいずれかに分類して理由を確認する。

- A: 正式Contract。必要な固定値として許容する
- B: 汎用処理から分離された意図的なDomain固有処理として許容する
- C: 暫定heuristic。暫定であることを明示し、正本metadataへ移せないか確認する

固定値そのものは禁止しない。`success` / `failure`等の正式enum、`visibility: agent`、
provider正式schemaの`function.name`、file workflowやprovider互換などの明示されたDomain専用処理は
許容する。

### helper重複と拡張耐性

Tool名取得、Registry entry解析、Model ID解決、provider schema変換、Capability lookup、
Tool一覧取得、output/schema参照について既存の正本helperがないか確認し、同等処理を再実装しない。

diff確定前に「新しいTool / Model / CapabilityをRegistryへ追加した場合、コード変更なしで認識できるか」
を一度確認する。認識できない場合は、意図したDomain制約か不要な固定前提かを区別し、後者だけを
修正候補またはTodoとする。この確認を理由に大規模リファクタリングしない。

## 16. Cross-Cutting Assumption Audit

Registry、Schema、Capability、Contractから取得すべき動的情報について固定前提の不具合を
1箇所で発見した場合は、同じ前提を使う箇所をREAD-ONLYで横断監査する。

対象には、固定Tool名やkeywordによるCapability代用、profile IDとprovider model IDの混同、
汎用Runtimeの特定DomainやResult fieldへの暗黙依存、内部形式とprovider形式の片方だけを
前提とする処理、および同じ意味を持つ複数の独自helperを含む。

発見事項は次のいずれかへ分類する。

- A: 正式Contractの固定値。原則変更しない
- B: Registry / Schema / Capabilityから取得すべき固定前提。修正候補
- C: 現在は動くが新Tool / 新Model / 新Capabilityで壊れる技術的負債
- D: 汎用処理から分離された意図的なDomain固有処理
- E: Evidence不足で追加調査が必要

横断監査と無制限な横断修正は分離する。修正範囲は、最初の因果的Failureを起点に定義した
同一root causeへ限定し、別Contract・別Runtime境界・根拠の弱い推測を同時に修正しない。

共通helper候補を発見しても、現在のFailure修正に不要なら実装しない。候補例は
canonical Tool identity、model identity resolver、Registry Capability lookup、
Registry output/schema lookupである。

## 17. Causal Scope Repair Loop

Cross-Cutting Assumption Auditで固定前提または正本bypassを確認した場合、最初の因果的Failureを
root causeと修正範囲の起点にする。そのうえで、同じidentity解決、同じRegistry / Schema /
Contract bypass、同じhelper責務に属し、新Tool・新Model・新Capability追加時に高確率で再発する
高リスク箇所について、次を反復する。

1. 同一root causeの高優先度箇所だけを最小修正する
2. 修正後にREAD-ONLYで置換漏れと同根リスクを再監査する
3. 同根・高リスクなら追加修正する
4. 同根でも低リスクならTodo、別root causeなら別工程へ送る
5. 正式Contractまたは意図的なDomain固有処理は変更しない
6. Evidence不足なら必要最小限だけ追加調査する

同根の高優先度候補、共通helperの明確な置換漏れ、既知の高リスクbypassがなくなった時点で
ループを終了する。その後にVerification Budgetを適用して、まとめた決定論的テストと必要最小限の
E2E SPOT_CHECKを行う。修正ループ中のcommitは行わない。

Generation-Time Assumption Checkは生成時の予防、Cross-Cutting Assumption Auditは問題発見後の
横断調査、Causal Scope Repair Loopは同一root causeの高リスク問題の収束、Verification Budgetは
不要な再調査・再テストの抑制を担当する。

## 18. Cross-Boundary Decision Consistency Rule（判断由来の横断整合性ルール）

Runtime判断を修正する場合は、判断を生成した境界だけでなく、同じ判断を後段で参照、再評価、
変換または上書きする消費境界までを同一Causal ScopeとしてREAD-ONLYで横断確認する。本ルールは
Causal Scope Repair Loopを置き換えず、第一原因に関係する同一判断の生成者と消費者までScopeへ
含めるよう、その定義を強化する。別判断、別Failure Stage、別Contractは分離する。

対象にはAction選択・優先順位、Tool Expectation、Action Relevance、Evidence Support、Completion、
Recovery / Replan、Human Approval、Goal / Task状態遷移を含む。修正前に、対象判断について
`生成境界 → 中間変換 → 消費境界 → 最終状態`のDecision Flowを短く再構成し、最低限次を確認する。

- decision origin / reason
- task_id / action_id / evidence_id
- parent / child relation
- priority / execution order
- downstream consumers
- override points / override reason
- final consumed state

必須原則:

1. 同じ判断の生成者と消費者を横断確認し、単独関数だけの修正で終了しない。
2. 後段で再評価する場合は、元判断のorigin、reason、provenanceを確認する。
3. 後段が元判断を上書きする場合は、明示的な根拠を必要とする。
4. Runtime自身が生成したActionや状態も無条件ACCEPTせず、Taskとの因果関係を保持・検証する。
5. 横断調査で見つけた別問題はKnown Issueとして記録し、現在のCausal Scopeから分離する。
6. 修正後は同一Decision Flow上の主要境界をdeterministic testで確認する。
7. E2Eは必要最小限のSPOT_CHECKとし、別Failure Stageの修正を混ぜない。

アンチパターン:

- 失敗assertionの直前だけを直す
- 特定Tool名または状態名だけを除外する
- 同じ判断を使う後段境界を確認しない
- Runtime BridgeとRelevance Auditを独立した判断として扱う
- Semantic Judge結果とCompletion結果の整合性を確認しない
- provenanceを失った状態で後段から再判定する

Decision Flow例:

```text
Action系:
User / LLM / Runtime → Action Proposal → Action Selection → Tool Expectation
→ Tool Execution → Action Relevance → Evidence Adoption

Evidence系:
Tool Result → Evidence Creation → Semantic Evidence Support → Completion Condition
→ Task Completion → Goal Acceptance
```

毎回Flow全体を全面レビューするのではなく、今回修正する判断を生成・消費する境界だけを対象とする。

### Canonical Ownership Rule（同一意味・判断・Invariantの正本化ルール）

同じ意味、判断、InvariantまたはContract上の正本情報を複数のRuntime Boundary、helper、Schema、
Stateが独立して保持または再解釈している場合、局所修正を続ける前にCanonical Ownershipを確認する。

- 正しいSource of Truthを特定する。
- 共通State、Schema、helperのうち自然な正本を選ぶ。

### Existence / Activation Separation Rule（存在・実行権分離ルール）

Runtime Object、Task、Candidate、Evidenceの存在・検出・保持は、`current`、`selected`、`authorized`、
`accepted`または`executable`を意味しない。実行・採用を抑止するために、本来保持すべきObjectの削除や未生成を
要求せず、`pending`、`deferred`、`blocked`、dependency、selection、Authority等のStateで表現する。
TestではExistence StateとActivation / Authority Stateを別Invariantとして検証し、「今実行してはいけない」を
「存在してはいけない」へ強めたassertionを置かない。

### Cross-Boundary Design Map Update Rule

Cross-Boundary Design Knowledgeの正本は[`CROSS_BOUNDARY_DESIGN_MAP.md`](CROSS_BOUNDARY_DESIGN_MAP.md)とする。
修正、Causal Scope監査、Cross-Boundary監査またはdeterministic testによって、新しいCross-Boundary Fact、
Canonical owner、State transitionまたはInvariantがMachine Factとして確定した場合は、作業完了前に関連entryを
同じ作業内で追加または更新する。既存Mapと実装が矛盾する場合は、取得時点、branch / HEAD、diff、Artifact、
test条件を照合し、実装のMachine Factを優先してMapのstale状態を明示する。

新しいCross-Boundary Factがない場合、または変更が単一Boundary内のlocal implementation detailだけの場合は
Map更新を要求しない。`REVIEW / UNKNOWN`の事項を推測で`CONFIRMED`へ昇格せず、長い修正履歴や未確認の将来設計を
Mapへ正本として追加しない。

### Cross-Boundary Design Map Consultation Rule

Cross-Boundary Concept、Canonical State、Authority、TransitionまたはInvariantに関係するFailure、修正、E2E評価では、
Repositoryを広く横断調査する前に[`CROSS_BOUNDARY_DESIGN_MAP.md`](CROSS_BOUNDARY_DESIGN_MAP.md)の関連entryを
確認し、現在のMachine Factとの関係を次の3つだけで判定する。

- `MATCH`: `CONFIRMED` entryと現在のMachine Factが一致する。今回の変更による影響根拠がないBoundaryは、
  原則として再調査対象から除外する。
- `MISMATCH`: Mapと現在のMachine Factが一致しない。実装が誤りと即断せず、Repository、Runtime Artifact、
  Test Result、取得時点、branch / HEADおよびdiffを照合し、ImplementationとMapのどちらがstaleかを確認する。
- `NOT_KNOWN`: 関連entryがない、Statusが`REVIEW / UNKNOWN`、または今回必要なDesign Factが不足している。
  不足しているBoundaryだけを追加調査する。

`MISMATCH / NOT_KNOWN`の調査で新しいCross-Boundary FactがMachine Factとして確定した場合は、既存の
Cross-Boundary Design Map Update Ruleへ接続する。Design MapをRepositoryより上位の絶対正本として扱わず、
`MATCH`した既知Designを無理由に再調査しない。

### Cross-Boundary Unnecessary Map Consultation Rule

Failure、E2Eまたは修正調査では、関連Design Map entryと合わせて
[`CROSS_BOUNDARY_UNNECESSARY_MAP.md`](CROSS_BOUNDARY_UNNECESSARY_MAP.md)を確認する。現在RunのMachine Factが
`CONFIRMED` entryのExclusion Conditionをすべて満たす場合に限り、そのBoundaryを今回の調査Scopeから除外できる。
これはBoundaryが永久に不要または実装上無関係であることを意味しない。

「除外可能」と「未到達」を同義にせず、Exclusion Typeは現在のMachine Factから次の3つで記録する。

- `NOT_REACHED`: 対象Boundaryへ実際に到達していない。
- `DERIVED_NOT_CAUSAL`: Boundaryは実行・評価されたが、上流Failureを反映した結果であり最初のCausal Failureではない。
- `DIFFERENT_CAUSAL_SCOPE`: Boundaryまたは既知Issueは存在するが、今回のFailureとは別Causal Scopeである。

実行済みBoundaryを`NOT_REACHED`として扱わない。例えば上流Failureを受けてGoal AcceptanceがFAILを記録した場合、
その評価を否定せず、条件を満たす場合だけ`DERIVED_NOT_CAUSAL`としてroot-cause調査から除外する。

次のいずれかを確認した場合は除外を解除する。

- entryのReopen Triggerが成立した。
- Exclusion Conditionと矛盾するMachine Factまたは未説明Failureがある。
- 今回の変更が対象Boundaryへ直接影響する根拠がある。
- entryが`REVIEW / REVOKED`である。
- 現在のMachine FactがentryのExclusion Typeと矛盾する。

誤除外が確認された場合はCounterexampleをMachine Factとして記録し、entryの条件を修正・縮小するか、
安全な限定条件を維持できなければ`REVOKED`とする。未到達と無関係を混同せず、Design MapはProjectのCanonical
Design、本Mapは条件付きの調査Scope除外知識として責務を分離する。

### Decision Support Maps Common Rule

判断支援MAP群のRegistryと参照関係は
[`DECISION_SUPPORT_MAPS.md`](DECISION_SUPPORT_MAPS.md)を正本とする。各MAPは関連entryだけを選択的に参照し、
機械的に全MAPを毎回読むことを要求しない。基本的な参照順は次とする。

- Failure / E2E: Machine Fact → Failure Routing Map → Design Map → UNNECESSARY Map →
  Verification / Coverage Map → Targeted Investigation
- 修正: Targeted Investigation → Change Impact Map → 修正 → Verification →
  新しいMachine Factがあれば該当MAP更新

共通原則:

- 優先順位はMachine Fact、Decision Support Maps、LLM推測の順とする。
- MAPはRuntime Stateそのものの正本ではなく、各MAPは自分の質問だけに答える。
- 同じCanonical Design詳細を複数MAPへコピーせず、Design Mapの関連entryを参照する。
- MAP間の矛盾を黙って統合せず、Repository、Artifact、Test Result、branch / HEAD、diff等のMachine Factで
  stale側を特定して更新する。
- `REVIEW / UNKNOWN / REVOKED`を推測で`CONFIRMED`へ昇格しない。

次を混同しない。

- Failure Routing候補とRoot Cause確定
- Change Impact対象とCurrent Failure Cause
- Design `MATCH`と`E2E_VERIFIED`
- Verification済みと現在Designとの一致
- UNNECESSARY除外と永久的無関係
- `NOT_REACHED`と`DERIVED_NOT_CAUSAL`
- `REVIEW`とBug確定

E2E後にFailure Route、Cross-Boundary Fact、Impact relation、Exclusion Condition、Verification Fact、
`REVIEW / UNKNOWN`またはCounterexampleが新しく確定した場合だけ、該当MAPの追加・更新要否を判断する。
新しい情報がなければMAP変更は不要とする。

### Machine Fact Authority

現在のRepository、`git diff`、実行結果、Test Result、Run Artifact、Schema validation等から機械的に確認できる
事実は、LLMの推測、自己申告、過去の要約より優先する。Fact同士が矛盾する場合は、対象Causal Scopeとの対応、
取得時点、branch / HEAD、実行条件およびprovenanceを照合し、現在の実態に対応するFactを採用する。
機械確認できない事項を、推測だけで`FIXED`、`PASS`または実装済みとして扱わない。

### Runtime Authority Boundary Rule（Runtime権限境界ルール）

RuntimeにCanonicalなConstraint、Decision、State、Permission、Dependency、Execution Order、Approval、
Recovery stateが存在する場合、LLM、PlannerまたはRecoveryが生成したAction / Tool Callは実行命令ではなく
Proposalとして扱う。Tool Executionへ到達する前に、必ず現在のCanonical Runtime Stateによる実行可否判定を
通過しなければならない。

正規の実行Flowは次とする。

`LLM / Planner / Recovery → Action Proposal → Runtime Authority → Executable Action → Tool`

`LLM / Planner / Recovery → Tool Executor`というRuntime Authorityを迂回する経路は禁止する。
Executor / SchedulerはRuntime Decisionを再生成するownerではなくconsumerであり、独自の順序、Permission、
DependencyまたはRecovery規則を別の正本として持たない。必要な変換はCanonical Runtime Stateを参照する
明示的Adapter / validatorとして実装する。

ExecutionOrderConstraintが存在する場合、LLMが返した`tool_calls`配列順はExecution OrderのSource of Truthではない。
Runtime current actionだけが実行可能であり、そのActionがcontinuation中なら後続Proposalは実行しない。
次ActionはRuntimeが現在Actionの完了を確認した後にのみ許可する。

以下をRuntime Authority bypassとして扱う。

- Canonical ConstraintがあるのにLLM `tool_calls`をそのまま実行する。
- Runtime current actionと異なるActionを直接executorへ渡す。
- Human Approval待ち、Dependency未完了、またはRecovery継続中に後続Actionを実行する。
- Recovery stateを無視して元Actionを再実行する。

Runtime側に該当Constraintが存在しない通常Chat等は、それだけではAuthority bypassとしない。ただし、次のE2E
Active Pathで必要なConstraintがAgent Task Entry等により生成されず、Proposalが直接Executionへ到達した場合は、
生成入口からScheduler / Executorまでを同一Causal Scopeとして扱う。Active Path上のbypassは
`OBSERVED / DOCUMENTED`で止めず、最小修正とdeterministic regressionを完了してから次E2Eへ進む。

### Canonical Concept Sharing / Commonization Completion Rule

同じConcept、Decision、InvariantまたはContractを共通State、Schema、helperへ移しただけでは共通化完了としない。
対象Causal Scopeについて、Canonical definition、Producer、Canonical storage、Consumer、final Authority、
Scheduler / Executor境界、Recovery / Continuation、および旧bypassの不在までを確認する。

完了には`Canonical Concept → Producer → State → Authority → Consumer → Executor`が同じ正本へ接続され、
同根の高優先度bypassが収束していることを要求する。Recovery / Continuationは元のCanonical Stateから独立した
別順序や別状態を正本として持たない。

### Commonization Escalation

同じ意味・判断・Invariantを複数Boundaryが独立保持または再解釈している場合、局所的なif、allowlist、queue操作を
追加する前に、既存Canonical State / Schema / helperへ統合できるか確認する。現在または次E2EのActive Path上では、
必要な最小共通化と再横断確認まで閉じる。別Contract、別Failure Stage、大規模Runtime再設計へは広げない。

- 各Boundaryを正本のconsumerにできるか確認する。
- Boundary固有変換は明示Adapterとして分離する。
- 独立した再解釈や重複所有を残す必要性を確認する。

現在または次のE2E Active Path上にある問題は確認だけで終了せず、同一Causal Scope内の最小共通化・
最小修正、deterministic regression、再横断確認を完了してから次のE2Eへ進む。Active Path外は
Deferred、TodoまたはDesign Hypothesisとして分離できる。異なるContract、Failure Stage、責務まで
無理に統合してはならない。

### Composite Test Cross-Boundary Preflight（複合テスト事前横断確認）

E2E、Integration、その他の複合テスト前に、そのテストが実際に通るActive Pathだけを対象として、
次を最小確認する。Repository全体のArchitecture Reviewには広げない。

1. 主要Boundary
2. Boundary間で共有されるDecision、State、ID、Contract
3. 同じ意味、判断、Invariant、正本情報の独立保持
4. Source of Truthの一意性
5. Boundary間変換が明示されているか
6. 後段が前段Decisionを独立再判定できるか
7. Override時に元Decision、reason、provenanceを保持できるか
8. Active Path上にOBSERVEDまたはDOCUMENTEDの未修正Known Issueがないか

問題がなければテスト実行可能とする。問題がActive Path上にあれば次のE2Eへ進まず、同一Causal
Scope内の修正対象へ昇格する。Active Path外ならDeferredまたはTodoとする。

### Active-Path Repair Requirement

Cross-Boundary AuditまたはPreflightで現在・次回の実行経路上に問題を確認した場合、確認済み、
Known Issue記録済み、Policy記載済みだけでは完了としない。次のE2E前に以下を閉じる。

1. first causal failureまたはInvariant違反の確認
2. 同一Causal Scopeの生成、変換、消費、最終状態の確認
3. 必要な最小修正
4. 再横断確認
5. deterministic regression
6. 必要最小限のE2E

別Failure Stageまたは別Contractは同時修正しない。

### Failure-Type Investigation Pattern

Failure調査の開始時は、種類に応じて最初に確認するBoundaryを次のPatternで絞る。これは固定Architectureを
要求するものではなく、最初のCausal Scopeを限定するための初期経路である。実コードに存在しないBoundaryを
新設せず、確認中に別Failure Stageまたは別Contractが判明した場合は分離する。

- Validation / Schema系: `Producer → Transform → Contract / Schema → Transport → Consumer`
- State系: `Canonical Owner → Producer → Transition → Consumer / Override`
- Execution系: `Proposal → Authority → Scheduler → Executor`

Pattern上でも、現在のFailureに関係する生成者・変換・消費者だけを確認し、Flow全体の無制限なレビューへ広げない。

### 問題状態

- `OBSERVED`: 問題を観測しただけ。
- `DOCUMENTED`: 原因、Known IssueまたはRuleへ記録したが、Runtimeは未修正の可能性がある。
- `MITIGATED`: 局所回避策があるが、根本原因が残る可能性がある。
- `FIXED`: 対象Causal Scopeを修正し、deterministic regressionを確認済み。
- `E2E_VERIFIED`: 修正後の実Active PathをE2Eで確認済み。

`OBSERVED / DOCUMENTED`は`FIXED`ではなく、`FIXED`は`E2E_VERIFIED`ではない。

### Policy Distribution Contract

Codex、Cursor、Local Agentへ共通Policy本文を複製しない。配布Manifestと機械契約の正本は
`ai_tool/policy/development_policy.json`の`distribution`とし、共通文書、Consumer Adapter、
`policy_version`を宣言する。Canonical Policy Identityは宣言された文書の実体からdeterministicな
SHA-256として生成する。

- CodexとCursorには正本への参照とConsumer固有の最小指示だけを置く。
- Local Agentは既存Policy Loaderからversion、hash、canonical file一覧を取得する。
- Test Run Artifactには実行時に取得したPolicy Identityを保存する。
- Canonical file、Adapter参照、version marker、Local Agent Loaderの不一致はfail-closedで検出する。
- 記録済みversion/hashと現在値が一致しなければstaleとして扱い、確認済みにしない。
- Cursor、Codex、Local Agentなど、AI Consumer自身または別AIによる完了報告は、それ単独では完了の証拠にしない。
  完了判定は対象Repositoryのコード、実行経路、状態、差分および必要なテストEvidenceで再確認する。

Policy本文の語義・重複整理は`Rulebook Language Cleanup`の別Todoであり、本Contract導入時に
広範囲な書換えを行わない。

## 19. 関連Policy

- Git操作は[`GIT_OPERATION_POLICY.md`](GIT_OPERATION_POLICY.md)に従う
- 作業開始・再同期は[`AI_DEVELOPMENT_SESSION_START_POLICY.md`](AI_DEVELOPMENT_SESSION_START_POLICY.md)に従う
- 現在の実装状態は[`current_system_specification.md`](current_system_specification.md)と実Repositoryを照合する
- 仕様仮説、探索、Canonicalization Gate、Human ClarificationおよびReopenの原則は
  [`SPECIFICATION_CONVERGENCE_POLICY.md`](SPECIFICATION_CONVERGENCE_POLICY.md)を正本とする
- Test Case作成前のCapability / Invariant、Required Evidence、Test Need、Candidate、Design Gateおよび
  Experiment Budgetの決定は[`TEST_DESIGN_AND_GENERATION_POLICY.md`](TEST_DESIGN_AND_GENERATION_POLICY.md)を正本とする
- 汎用Policyの作成・Scope分類・明示監査・Certificate再利用は、Policy監査作業時に限り
  [`GENERIC_POLICY_AUTHORING_POLICY.md`](GENERIC_POLICY_AUTHORING_POLICY.md)を参照する。通常作業ではAudit Preflightを起動しない
# UI Requirement Preservation Rule

UIを追加・変更・削除する場合は、広い変更前に`docs/UI_REQUIREMENT_MAP.md`の関連entryを確認する。
`IMPLEMENTED / VERIFIED`の要求を、明示的なユーザー要求変更なしに削除・弱体化しない。意図的に廃止する場合は
理由とともに`DEPRECATED`へ遷移させる。変更後はRegression Guardを確認し、新しいMachine Factが確定した場合だけ
Mapを更新する。UI Requirement Mapは画面実装やRuntime Stateの第二正本として扱わない。
