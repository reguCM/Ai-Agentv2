# Generic Policy Authoring and Audit Policy

## 1. Scope

本書は、汎用Policyを作成、分類、明示的に監査し、特定版の監査証明を再利用するための正本である。
通常の開発作業ではAudit systemを起動せず、Policy監査が明示された場合だけAudit Preflightを使用する。

## 2. Responsibility

- 汎用Policyの必須構造とProject Leakage判定基準を定義する。
- Policy単体Hashと監査基準Versionに結び付くAudit Certificateを定義する。
- 有効Certificateによる二重監査防止と、再監査条件を定義する。

常時監査、Semantic Judge、自動書換え、自動Canonical化、CI常設Audit、全Policy一括監査は責務外である。

## 3. Policy Scope

- `GENERIC`: Project固有実装にNormativeに依存せず、他Projectへ適用できる原則。
- `PROJECT_SPECIFIC`: 現Projectの構造、運用、ContractまたはStateを規範対象とするPolicy。
- `ADAPTER`: GENERIC原則を特定Project、ToolまたはRuntimeへ接続する薄い文書。

GENERIC PolicyのProject-specific assumptionsは原則`None`とする。適用Adapterへの参照や、明示した
`NON_NORMATIVE_EXAMPLE`は許可する。

## 4. Policy Authoring Contract

Policyは最低限、次を明示する。

- Scope
- Responsibility
- Inputs
- Outputs
- Invariants / Principles
- Non-goals
- Relationship to other policies
- Project-specific assumptions
- ExampleがNormativeかNon-normativeか

GENERIC判定の中心質問は次である。

> Project固有の名称、具体例および実装をすべて除去しても、規範部分は意味を保ち、他Projectへ適用可能か。

YESならGENERIC候補、NOならPROJECT_SPECIFICまたはADAPTER候補とする。抽象度ではなくNormative Dependencyで
判定する。

## 5. Project Leakage Candidate

次は文脈を確認すべき候補であり、文字列の存在だけで違反としない。

- Repository絶対Path、Worktree、Branch
- Model名、Tool名、Python class / function
- Project固有Failure Code、Task ID、固定Benchmark件数
- 現RuntimeまたはUI構造だけを普遍前提とする記述
- 特定機能だけに成立する原則の無条件な一般化
- 一時Todo、Current State
- Project固有Permission、RecoveryまたはTool仕様を一般法則とする記述

`NON_NORMATIVE_EXAMPLE`、`PROJECT_APPLICATION`または`ADAPTER_REFERENCE`として規範部分から分離され、
その記述を削除しても原則が成立する場合は許容できる。

## 6. Inputs / Outputs / Invariants

Inputsは対象Policy、宣言Scope、現在のPolicy bytes、Generic Policy Rules、既存Certificateおよび明示監査要求である。
OutputsはAudit Certificateと任意の人間向けReportである。

主要Invariant:

- 監査対象identityは`policy_path + policy_sha256 + audit_rules_version`である。
- Git revisionだけを監査単位にしない。
- Registryは索引であり、Certificateが監査証明の正本である。
- Certificateを自動で`AUDITED_CLEAN`にしない。
- Project固有例とNormative Ruleを分離する。
- 通常作業ではCertificate探索やHash照合を発火させない。

## 7. Audit Status

- `NOT_AUDITED`: 未監査。
- `AUDITED_CLEAN`: 現行基準で重大な汎用性問題なし。
- `AUDITED_WITH_FINDINGS`: 監査済みだが修正候補あり。
- `AUDITED_WITH_EXCEPTIONS`: 意図的例外があり、理由とScopeが明示されている。
- `REVIEW_REQUIRED`: Policyまたは基準変更等により既存結果をそのまま適用できない。

## 8. Audit Certificate / Report / Registry

CertificateはPolicy Hash、Rules Version、結果、findings、exceptions、監査方法、auditor role、Git provenance、
working tree状態およびReport参照を保持する。未CommitでもPolicy bytesのSHA-256によって証明可能とする。

人間向けReportは監査対象、Scope、Rules、確認項目、findings、exceptions、最終判定、Policy Hash、再監査Triggerを
含む。Certificateは機械判定、Reportは説明・追跡を担当する。RegistryはCertificate探索索引であり、
Certificate内容を上書きする正本ではない。

### PROJECT_APPLICATION

- 機械可読Rules: `ai_tool/policy/generic_policy_rules.json`
- Certificate Schema: `ai_tool/policy/policy_audit_certificate.schema.json`
- Certificate保存候補: `reports/policy_audits/<POLICY>_audit_<date>.json`
- 人間向けReport: 同じbasenameの`.md`
- Registry: `docs/policy_audit_registry.json`

Registryは`policy_id / policy_path / latest_certificate / audited_hash / audit_rules_version / audit_status`を保持できるが、
Certificate内容を上書きする正本ではない。

## 9. Explicit Audit Preflight

Policy監査が明示された場合だけ次を行う。

```text
Target Policy
→ Audit Registry
→ Certificate
→ Current Policy SHA-256
→ Certificate Hash照合
→ Audit Rules Version照合
→ Audit Result確認
```

Policy path、Hash、現行Rules Versionが一致し、結果が`AUDITED_CLEAN`、またはRulesが明示的に再監査不要とする
有効Statusなら`ALREADY_AUDITED_VALID`として本監査を省略できる。その場合、既存証明により再監査しなかったことを
報告する。

上位Authorityが有効Certificateにかかわらず再監査を明示した場合だけ`FORCED_REAUDIT`で省略を上書きする。

## 10. Reaudit / Reopen Conditions

次の場合は本監査またはReviewが必要である。

1. Policy SHA-256変更
2. Generic Policy Audit Rules Version変更
3. 前回Statusが`AUDITED_WITH_FINDINGS`
4. Certificateが不完全または不正
5. 新しい重大なProject Leakage Evidence
6. Human / Authorityによる明示的再監査要求

対象PolicyのHashとRules Versionが不変なら、無関係なPolicy、Runtime、Model、TestまたはProject Adapterの変更だけで
自動的に再監査しない。TypeまたはMachine Factと矛盾する場合はRegistryではなくCertificateと現在bytesを照合する。

## 11. Dormant Operation

通常作業ではAudit systemはDormantである。AGENTS、通常Prompt、Runtime LoopへRules本文、Certificate探索または
Hash照合を常設しない。将来のRule Router接続は未実装であり、本FoundationではLLM callやToken消費を発生させない。

## 12. Relationship / Non-goals

### ADAPTER_REFERENCE

- Test Designの内容正本は`TEST_DESIGN_AND_GENERATION_POLICY.md`であり、本書はその汎用Scope監査方法だけを扱う。
- 開発・検証の正本は`DEVELOPMENT_TEST_POLICY.md`である。
- Policy Distribution Contractを変更せず、監査基盤を常時配布対象にしない。
- 現時点で既存Policyの監査実施やCertificate発行は行わない。

### NON_NORMATIVE_EXAMPLE

Test Design Policyは将来、明示的なGeneric Scope Auditを受け、特定HashとRules Versionに対するCertificateが
`AUDITED_CLEAN`になった場合に、その版を監査済み汎用正本として扱える。本例は今回の監査完了を意味しない。
