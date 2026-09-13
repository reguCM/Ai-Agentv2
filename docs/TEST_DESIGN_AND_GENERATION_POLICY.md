# Test Design and Generation Policy

## 1. 役割と責務境界

本書は、Requirement、Specification、Failure、Change、Hypothesis、RiskおよびEvidenceから、何をなぜテストするかを
決定する汎用Test Design / Test Generationの正本である。中心原則は次のとおりである。

> 先にTest Caseを考えない。先に何を証明・確認する必要があるかを決める。

本書はInput Interpretation専用ではなく、Specification Convergence専用の下位機能でもない。

- 本書: 何を確認すべきか、必要Evidence、Test Need、Candidate、規模および実施要否を決める。
- `DEVELOPMENT_TEST_POLICY.md`: 作成済みTestの階層、実行、Verification、Failure後の再検証を扱う。
- `SPECIFICATION_CONVERGENCE_POLICY.md`: 仕様仮説、Canonicalization、Human Clarification、Reopenを扱う。

## 2. Canonical Process

```text
Requirement / Specification / Failure / Change / Hypothesis / Risk / Evidence
→ 今回のDecision Question / Purpose
→ Capability / Invariant / Responsibility Boundary
→ Required Behavior / Forbidden Behavior / Unknown
→ Required Evidence
→ Existing Evidence確認
→ Missing EvidenceだけをTest Need化
→ 最小Test Candidate
→ 内容・期待値・責任境界・測定整合の確認
→ 必要に応じHuman / Judge Review
→ Canonical Testへの昇格
→ DEVELOPMENT_TEST_POLICYによる実行・検証
```

仕様から自然言語Test Caseへ直接変換しない。最低限、
`Capability / Invariant → Required Evidence → Test Need → Test Candidate`を経由する。

## 3. 入力Source

Test Designは次を独立した入力として扱える。

- User Requirement
- Canonical / Provisional Specification
- Machine Fact
- Failure / Bug
- Development Hypothesis
- Design / Implementation Change
- Risk
- Existing Evidence / Regression Need
- Exploration Result
- Human Clarification

各入力のsource ID、status / certainty、provenanceを保持し、異なる種類のSourceを暗黙に同一視しない。

## 4. Required Evidence中心の判断

中心質問は「現在の開発判断を進めるため、次に何を観測できればよいか」である。Required Evidenceから、
動作確認、最小実験、網羅、Regression、Integration、E2E、結果比較、比較実験、追加調査、Human Clarification、
または新規Test不要を選択する。固定Stageを消化すること自体を目的にしない。

Existing Evidenceを新規Test設計より先に確認する。

- `REUSE`: 必要Evidenceが既存結果で足りる。新規実験を作らない。
- `SPOT_CHECK`: 一部不足または接続確認だけが必要。不足分だけ追加する。
- `RERUN`: 現在条件に対応するEvidenceがなく、最小Testが必要。

この判断は`DEVELOPMENT_TEST_POLICY.md`のVerification Budgetへ接続する。

### Vertical Viability Principle

新しいArchitecture、Pipeline、Cross-Boundary Contract、または複数Component間の接続成立そのものが未証明の場合、
広範なCoverage、多数ケース、Model / Implementation比較、Robustness、Performanceまたは大規模反復等の
Horizontal Expansionより先に、必要な主要Boundaryを通過する最小Vertical SliceでArchitecture Viabilityを
確認することを優先する。

これは「すべての開発で必ずE2Eを先に実行する」という固定Workflowではない。現在必要なEvidenceが接続成立を
示すVertical Evidenceか、横方向の能力・差・品質を示すHorizontal EvidenceかをTest Purposeから判断する。

- `VERTICAL_NOT_PROVEN`: 接続成立のEvidenceが不足。原則として最小Vertical Evidenceを先に取得する。
- `VERTICAL_PROVEN`: Required Boundaryの成立が既存または新規Evidenceで確認され、必要なHorizontal Expansionへ進める。
- `VERTICAL_FAILED`: Vertical Sliceで成立しなかった。大規模Horizontal Expansionより先にFailureを扱う。
- `VERTICAL_NOT_REQUIRED`: 独立Component等でCross-Boundary成立確認を必要としない。

次の場合、新しいVertical Testを機械的に追加しない。

- Existing Evidenceによって対象範囲のVertical Viabilityが十分に証明されている。
- 対象が独立Componentであり、今回のDecision QuestionがCross-Boundary接続を必要としない。
- Horizontal Evidenceを先に得る合理的なTest Purpose、Riskおよびprovenanceが明示されている。

Vertical SliceのBoundary数やTest形式を固定せず、Architecture成立の判断に必要な最小Evidenceから逆算する。

## 5. Default Test Pattern

次は選択可能なDefault Templateであり、固定工程ではない。

### 動作確認

測定器と経路自体（例: Input → Prompt → Model / Function → Structured Output → Schema Validation → Evaluator）を
原則1ケース程度で確認する。性能や一般能力の証明には使用しない。

### 開発用・実験最小

現在のFailure、課題、Hypothesisまたは修正方針を、必要最小限のEvidenceで確認する。件数は固定せず、通常は
少数を優先する。

### 開発用・実験網羅

対象Capability、Invariant、ChangeまたはRiskを十分に確認する。ケース数を先に決めず、Required EvidenceとRiskから
逆算する。

### 結果比較

候補間で比較可能な既存Evidenceが揃っている場合に、再実験せず既存結果を比較する。

### 比較実験

既存Evidenceでは公平または十分な比較ができない場合だけ、不足Evidenceを取得するために実施する。

Default Patternは省略・追加・統合できる。逸脱理由とprovenanceを残し、既存Evidenceだけで十分なら新規Testを
作らない。

## 6. Capability / InvariantとResponsibility Boundary

正式Testは、どのSourceから生まれ、どのCapability / Invariantを、どのEvidenceで確認するか追跡可能にする。
最低限`source_ids`、`capability_ids`または`invariant_ids`、`purpose`、`required_evidence`、`provenance`を持つ。

Gold / Rubricを作る前に、その期待値を所有するBoundaryを特定する。Semantic Interpreter、Runtime Authority、
Scheduler、Executor、Recovery、UI、Human Approval等の責任を混同しない。

例えば曖昧な読取依頼では、Semantic側の「READらしいがTarget未解決」と、Runtime側の「安全・低コストなら探索、
高RiskならClarification / Block」を分離する。「必ず質問する」をSemantic側の唯一Goldへ暗黙に固定しない。

上記は`NON_NORMATIVE_EXAMPLE`であり、特定InterpreterやRuntime構造を汎用Policyの前提にしない。

## 7. Expected Resultの強度とSpecification Status

User RequirementまたはSource Meaningより強いGoldを作らない。Expected Resultにもsource、status / certainty、
provenanceを保持する。

- `UNKNOWN / AMBIGUOUS`: Canonical Goldを固定せず、探索またはHuman Clarificationを優先する。
- `HYPOTHESIS`: exploratory / development testには使用できるが、Canonical Regressionの唯一Goldにはしない。
- `PROVISIONAL`: Development Testへ利用できるが、期待値もPROVISIONALとして保持する。
- `CANONICAL`: Canonical Test / Regressionへの昇格候補にできる。
- `REOPENED`: 関連Test、Gold、Rubricを再確認する。

## 8. Test Candidate Lifecycle

- `DRAFT`: 入力Sourceまたは必要Evidenceを整理中。
- `CANDIDATE`: Test Needから生成された未承認候補。
- `REVIEWED`: Source、責任境界、測定方法、期待値強度を確認済み。
- `CANONICAL`: Gateと必要な承認を通過した正式Test。
- `REOPENED`: Source変更または反証により再確認が必要。

自動生成はCapability / Invariant候補、Required Evidence候補、Test Need候補、Test Candidate候補までとする。
Human / Judge Reviewなしで重要なGoldやRubricを自動Canonical化しない。

## 9. Test Design Gate

高コストまたは大規模Testへ進む前に、次を確認する。

1. **Test Purpose Gate**: Decision Questionと確認目的を説明できる。
2. **Source / Status Gate**: Source、status / certainty、provenanceが分かる。
3. **Capability / Invariant Gate**: 対象能力または法則を説明できる。
4. **Responsibility Boundary Gate**: 各期待値のownerが明確である。
5. **Evidence Need Gate**: 成否判断に必要な観測を説明できる。
6. **Measurement Gate**: Prompt、Schema、Fixture、Evaluator、Rubricが同じ意味を測る。
7. **Existing Evidence Gate**: REUSEまたは既存結果比較で代替できないことを確認する。
8. **Coverage Gate**: 網羅Testではケース集合と必要Coverageの対応を説明できる。
9. **Comparison Need Gate**: 比較実験では既存結果だけでは不足する理由を説明できる。

未達Gateがある場合、先にその不足を解消し、高コスト・大規模Testへ進まない。

## 10. Experiment Budget Preflight

実LLM、外部Tool、長時間または高コスト処理では、実行前に次を記録する。

`cases × configurations/views × models/implementations × repeats = planned executions`

可能なら既存実測から`estimated_duration`と`estimated_resource_use`も算出する。大規模実験ではTest Purpose、
Required Evidence、前段Gate、Evidence再利用可否、Full Runが必要な理由、planned executions、推定時間を提示する。
Human Approvalによる実行Gateは将来候補であり、現時点のProduction実装済み機能ではない。

## 11. 機械可読Contract Foundation

Test Design交換形式の土台は`tests/specs/test_design_schema.json`とする。これはProduction Runtime Schemaではなく、
Capability / Invariant Requirement、Required Evidence / Test Need、Test CandidateおよびExperiment Budgetを
provenance付きで表現するFoundationである。

## 12. PROJECT_APPLICATION: Legacy Test / Benchmark

既存Input Interpretationの22ケースとQwen / Gemma比較Artifactは削除しない。ただし、本ProcessによるPurpose、
Responsibility Boundary、Gold強度、MeasurementおよびBudgetの再評価前は`LEGACY_EXPLORATORY_BASELINE`とする。
Canonical Benchmark / Canonical Goldへ自動昇格させない。

この実験は「Benchmark設計が十分収束する前に比較へ進むと、高コストで解釈困難な結果になり得る」という
Development Evidenceである。

### NON_NORMATIVE_EXAMPLE: Input Interpretation Vertical Slice

現在Projectでは、`Raw Input → Interpretation → RequestIR → Runtime → Tool → Evidence → Completion / E2E`の
最小接続を確認してから、Model比較、方言、typo、voiceまたは多数ケースへ広げる適用が考えられる。これは
Project固有の例であり、汎用PolicyがこのBoundary列またはE2E形式を必須にするものではない。
