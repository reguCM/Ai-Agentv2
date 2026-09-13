# Input Interpretation Playground Architecture v1

## 目的と境界

本書は自然言語入力の候補生成、比較、圧縮評価を行う隔離実験環境の正本である。Production Agent Runtime、Tool Expectation、Action Relevance、Evidence、Completionへは接続しない。

```text
Raw Input → InputEnvelope → Adapter候補 → Semantic Comparator → RequestIR
```

`RequestIR`まではSemantic Proposalであり、Actionや実行可否を決定しない。将来Runtimeへ接続する場合もRuntime Authorityによる検証が必要である。

## Canonical Contract

- `InputEnvelope`: raw input、input mode、profiles、protected spans、metadataを保持する。`raw_input`は変換後も不変。
- `InterpretationCandidate`: Adapter出力。correction、uncertainty、confidence、input provenanceを持つ。
- `CompactionDecision`: spanごとの`KEEP / SUPPRESS / MERGE / REPLACE / UNCERTAIN`候補。圧縮の実行命令ではない。
- `SemanticSelection`: Candidate選択、fusion、none-of-the-above、clarificationを明示する。
- `RequestIR`: intent、target、operation、order、constraint、condition、negation、output requirement、ambiguityとsource provenanceを保持する。
- `InterpretationResult`: Raw Envelope、全Adapter実行、候補、Compaction、選択、RequestIR、計測値を一括保持する。

## Raw Input / Protected Span

Raw Inputは正規化・圧縮で上書きしない。path、URL、code、JSON/ID候補、quoted textをProtected Spanとして位置と原文で保持する。Safe Normalizerはspan外だけをUnicode NFKC正規化し、span内をbyte-equivalentな文字列として維持する。spanとRaw Inputが一致しない場合はfail-closedとする。

## Adapter Contract

Adapterは`InputEnvelope → InterpretationCandidate[] / CompactionDecision[]`のみを担当し、Tool Actionを決定しない。全Candidateは`input_id` provenanceを持つ。

| Adapter | v1の責務 | Production依存 |
|---|---|---|
| raw | 原文候補を返す | なし |
| safe_normalizer | Protected Span外の安全なUnicode正規化 | なし |
| sudachi | surface / lemma / reading / normalized formを補助情報として返す | optional |
| llmlingua | configured compressorからPrompt Compression候補を返す | optional。Productionではmodelをロードしない |

optional dependencyがない場合は`UNAVAILABLE`、実行時例外は`ERROR`として局所化し、Playground全体やProductionを失敗させない。

### External Tool Comparison Phase

実験依存は`requirements-input-interpretation-experimental.txt`に分離し、Production requirementsへ追加しない。`tool_comparison.py`はSudachiとconfigured LLMLingua compressorを同じ22入力へ適用し、次を別々に記録する。

- `TOOL_OUTPUT_QUALITY`: token解析、圧縮本文、latency、resource、critical fragment loss。
- `REQUEST_IR_BENCHMARK`: baseline Semantic Selection / RequestIRの既存評価。

Tool出力の生成成功をRequestIR成功へ変換しない。圧縮結果はCandidateであり、Raw InputまたはCanonical Inputを上書きしない。比較Reportは`reports/input_interpretation/external_tool_comparison_20260907.{json,md}`に保存する。

2026-09-07実測ではSudachiPy 0.6.11 + core dictionary 20260723、LLMLingua 0.2.2 + multilingual BERT-base meetingbank modelを隔離venvで使用した。LLMLinguaはCPU固定であり、GPUを使用していない。

## Semantic Comparator

Comparatorは複数候補からselectionとRequestIR proposalを返す。候補の強制選択は禁止し、fusion、none-of-the-above、needs-clarificationを表現できる。未知Candidate IDはRuntime側Contract validationで拒否する。

v1の`ConservativeComparator`はdeterministic baselineである。実LLM Comparator、Ollama Structured Output、Pydantic Schema接続は将来拡張であり、現在は実装済みと扱わない。

## Benchmark

Black-boxは最終RequestIRと期待値を比較する。White-boxはEnvelope、Adapter availability、候補、Compaction、Selection、RequestIR、各処理時間を保存して失敗位置を示す。

評価値はraw/working文字数、概算token数、削減率、latency、RequestIR accuracy、Constraint/Negation/Execution Order Preservation、False/Redundancy Removalである。

**Meaning Preservation > Prompt Reduction** とし、constraint、negation、execution orderのいずれかを失った結果は削減率に関係なくPASSにしない。

### Benchmark Level

- `MICRO`: 活用、typo、voice、dialect、曖昧性など局所能力の診断。日本語理解全体の単独スコアにはしない。
- `CONTEXTUAL`: 主語・目的語・動詞省略、照応、Topic継続、言い直し、婉曲依頼、否定Scope、条件、文をまたぐ順序を含む自然な複数文。
- `REALISTIC`: 過去説明、現在要求、重複、filler、self correction、path/code/URL、禁止、条件、古い指示と新しい指示を組み合わせた実運用寄り入力。

MicroとContextualは`pair_id`でtypo / voice / dialect / ambiguity / negation / order等を対応付け、局所成功と文脈内成功を区別する。

### Evaluation Type / Certainty

- `HARD_GOLD`: ほぼ一意な期待RequestIR。
- `ACCEPTABLE_SET`: 複数の解釈をFull Accept可能。
- `RUBRIC`: `CRITICAL / MAJOR / MINOR / OPTIONAL`の重み付き要件。CRITICAL欠落は総合点に関係なくFAIL。
- `HUMAN_ADJUDICATED`: 一意に決めず、曖昧性、clarification、provisionalの扱いを評価する。

Semantic SelectionとRequestIRは`KNOWN / LIKELY / AMBIGUOUS / UNKNOWN / PROVISIONAL`を持つ。PROVISIONALではassumption、source、provisional fieldを保持し、KNOWNへ昇格しない。Benchmark Caseはacceptable / forbidden interpretation、critical requirement、clarification expectationを表現できる。

Capability reportは3 Level、Hard Gold Accuracy、Critical Preservation、Acceptable Interpretation、Ambiguity Handling、Clarification Decision、Unsafe Overcommit、Provisional Handling、Prompt Reduction、Constraint Lossを分離する。未実装能力を総合PASSで隠さない。

実行例:

```powershell
python -m ai_tool.input_interpretation.benchmark
python -m ai_tool.input_interpretation.benchmark --json result.json --markdown report.md
```

## v1で実装しないもの

- Production Agent Runtimeへの接続
- 実LLM Comparator
- typo / IME / voice / dialect / slang / domain jargon専用Adapter
- tokenizer正本または外部modelの自動download
- Chat UI統合
- RequestIRからのTool実行
