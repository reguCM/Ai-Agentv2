# Specification Convergence Policy（仕様収束Policy）

## 1. 役割

本書は、不明な仕様を推測で即時確定せず、探索、Evidence、反証およびHuman Clarificationを通じて
Canonical Specificationへ収束させるための設計Policy正本である。

本書はProduction Runtimeの実装仕様ではない。Specification Convergence Runtime、Production向けSchema、
状態遷移、Human Clarification UIおよびInput InterpretationからGoal / Task RuntimeへのBridgeは
`DESIGN_ONLY / NOT_IMPLEMENTED`である。

上記実装状態は`PROJECT_APPLICATION`であり、本Policyの汎用規範ではない。

## 2. 基本Flow

`User Requirement / Machine Fact / Existing State`

`→ Known / Unknown / Ambiguousの分離`

`→ Specification Hypothesis`

`→ Exploration → Evidence → Hypothesis Update`

`→ Canonicalization Gate → Canonical Specification`

Critical Unknownが残る場合は、`HUMAN_CLARIFICATION_REQUIRED`へ遷移するか、ユーザーが明示的に許可した
範囲だけを`PROVISIONAL`として継続する。LLM推論だけでCanonical化してはならない。

## 3. Information Sourceの責務

| Source | 意味 | Canonical化での扱い |
|---|---|---|
| User Requirement | ユーザーがどうしたいかを示すNormative Source | 明示要求として保持する |
| Machine Fact | Repository、Test、Artifact、実行結果等のDescriptive Source | 現状・成立性・矛盾のEvidenceとして扱う |
| Human Clarification | 曖昧な仕様に対するユーザーの追加決定 | 対象と範囲をprovenance付きで反映する |
| Model Inference / Interpretation | 意味や仕様の仮説 | Canonical Truthとして扱わない |
| Tool / Research / Benchmark Result | 仕様判断を支援するEvidence | 自動的にRequirementまたは採用済みCapabilityへ変換しない |

Machine FactとUser Requirementは別軸である。Machine FactがRequirementと矛盾してもRequirementを黙って
書き換えない。例えば「安全な圧縮」が要求され、現方式でCritical Lossが観測された場合は、Requirementを
削除せず`Implementation Gap / Alternative Required`として扱う。

## 4. Specification Status

Input InterpretationのSemantic Statusとは別Contractとして、次の概念状態を用いる。

- `UNKNOWN`: 判断に必要な情報が不足している。
- `AMBIGUOUS`: 複数の妥当な仕様解釈が残る。
- `HYPOTHESIS`: 現在のEvidenceから推測した仕様候補。未確定である。
- `PROVISIONAL`: 仮仕様として進めることを明示的に許可された状態。許可範囲と仮定を保持する。
- `CANONICAL`: Canonicalization Gateを通過した仕様。
- `REOPENED`: 新Evidenceまたは要求変更により再検討が必要になったCanonical仕様。

これらは現時点の設計語彙であり、Production Runtime enumの実装済み宣言ではない。

## 5. Explorationの2経路

### Goal-driven Exploration

現在のGoal、FailureまたはUnknownから情報需要を仮定し、候補Capability、Tool、ModelまたはTestを用いて
Evidenceを得る。

`Problem → Information Need Hypothesis → Candidate Capability → Tool / Model / Test → Evidence`

### Open Exploration

興味深いTool、Model、Architectureまたは手法を隔離環境で試し、Capability、Limitationまたは想定外の
Failureを観測して、既存のNeedや仕様仮説を更新する。

`Interesting Candidate → Isolated Trial → Benchmark → Machine Evidence → Hypothesis Update`

両経路を正規の探索とする。Open Explorationを無条件に寄り道または失敗として扱わない。

## 6. Exploration Result

探索結果は採否だけで評価せず、必要に応じて複数の分類を持てる。

- `DIRECT_FIT`: 現在の問題を直接改善する。
- `SPECIALIZED_FIT`: 限定された用途で有効である。
- `NEGATIVE_EVIDENCE`: 方式、仮説またはArchitecture候補を反証・制約する。
- `DISCOVERY`: 想定外のCapability、Failureまたは別用途を発見する。

`NOT_ADOPTED`は`FAILED_EXPLORATION`を意味しない。仮説空間を狭めるEvidenceまたは新しい発見が残れば、
探索成果として保持する。

## 7. Canonicalization Gate

Canonical化判断では最低限、次を照合する。

- Explicit User Requirement
- Human Clarification
- Machine Fact
- Test / Schema / Evidence
- Critical Unknown
- 未解決Contradiction
- Assumptionとprovenance

Critical Unknownまたは未解決矛盾が残る場合は`CANONICAL`へ昇格させない。具体的な自動昇格条件は、
Production Runtime Contractが未設計の現段階では固定しない。

## 8. Human Clarification

Human ClarificationはFailureではなく、仕様収束の正常なTransitionである。

- 自動確定可能: `CANONICAL`
- 明示された範囲で仮進行可能: `PROVISIONAL`
- Criticalで判断不能: `HUMAN_CLARIFICATION_REQUIRED`

Automatic Specification Determinationの成功を「AIだけですべて決定すること」と定義しない。

## 9. Reopen Rule

Canonical Specificationも永久不変ではない。新Machine Fact、新User Requirement、Test Failure、Benchmark
EvidenceまたはContract contradictionが既存仕様と矛盾する場合、Reopen Triggerとして記録し、
`CANONICAL → REOPENED → Specification Convergence Loop`へ戻す。

Reopen時は、以前の仕様、Trigger、矛盾するEvidenceおよび変更判断のprovenanceを保持する。

## 10. Non-equivalence

- `HYPOTHESIS ≠ CANONICAL`
- `PROVISIONAL ≠ CANONICAL`
- `Model Inference ≠ Machine Fact`
- `Machine Fact ≠ User Requirement`
- `Tool Candidate ≠ Adopted Capability`
- `NOT_ADOPTED ≠ FAILED_EXPLORATION`
- `NEGATIVE_EVIDENCE ≠ 無駄`
- `Benchmark PASS ≠ Canonical Specification`
- `Canonical Specification ≠ Runtime Implementation Complete`
- `FIXED ≠ E2E_VERIFIED`

## 11. NON_NORMATIVE_EXAMPLE: Input Interpretation実験

詳細値の正本はInput Interpretationの比較Reportと現在状態文書を参照する。

- SudachiPyは形態解析補助として`SPECIALIZED_FIT`を示したが、typoの意味復元を保証しない。
- LLMLingua-2は日本語Agent Instructionで8.55%削減に対してCritical Loss 7/22が観測され、現構成の標準入力
  圧縮には`NEGATIVE_EVIDENCE`となった。Document Context等の別用途は未評価であり、非採用はTool全体の否定ではない。

## 12. PROJECT_APPLICATION: 将来Architectureとの位置関係

設計上の候補Flowは次である。

`Input Interpretation → RequestIR → Specification Hypothesis → Specification Convergence`

`→ Canonical Requirement → Goal / Task Runtime → Runtime Authority → Execution`

現在実装済みなのは隔離Playground内のInput Interpretation / RequestIR proposalまでである。
Specification Hypothesis以降を接続するProduction Runtimeは未実装であり、本Policyの制定だけで実装済み、
検証済みまたはE2E成立とは扱わない。

仕様状態をTest Goldへ反映し、必要EvidenceからTest Needを設計する責務は
`TEST_DESIGN_AND_GENERATION_POLICY.md`を参照する。本書はTest Case生成・実行の第二正本を持たない。
