# HISTORY — NH1〜NH14 実験履歴

判定は各 run の `EXPERIMENT_REPORT.md` および `FW/knowledge_base/HYPOTHESIS_STATUS.md` の原文に準拠する。本書では改変しない。

パス接頭辞: `FW/runs/` = `research/llm_benchmarks/.../diagnostic_framework/runs/`

---

## 背景（NH 以前）

EXP-001〜010（20260824〜20260825）で `search_web` 診断の基礎を確立。コード読解・仕様・route 分解・証拠境界・N2・DeepSeek 比較・大型 LLM を実施。詳細は [EXPERIMENT_INDEX.md](../../research/llm_benchmarks/capability_route_dataset/v0/analysis/web_effect_review/search_quality_diagnosis/diagnostic_framework/knowledge_base/EXPERIMENT_INDEX.md)。

---

## NH1 — State Transition Constraints

| 項目 | 内容 |
|------|------|
| **Run** | `20260826_183500/nh1_state_transition_constraints/` |
| **目的** | LLM に依存せず、機械的 State 遷移制約で危険遷移を防ぐ |
| **検証内容** | exact SUPERSEDED 値の再 Active を機械拒否できるか |
| **主な結果** | 条件 B で FA 2→0、FR 非増、validation 11/11 |
| **判定** | **Strong Support** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH2 — State Transition Generalization

| 項目 | 内容 |
|------|------|
| **Run** | `20260826_190000/nh2_state_transition_generalization/` |
| **目的** | NH1 の exact 再 Active 禁止を Goal/Claim/Hypothesis へ一般化 |
| **検証内容** | 一般化制約、REOPEN 例外（条件 D） |
| **主な結果** | Supported (generalization); C で危険 FA=0、D で REOPEN 例外 |
| **判定** | **Supported** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH3 — State Safety Boundary

| 項目 | 内容 |
|------|------|
| **Run** | `20260826_191500/nh3_state_safety_boundary/` |
| **目的** | near-exact 正規化、Evidence 検証、sidecar 観測の安全境界 |
| **検証内容** | normalization、Evidence 実在、content validation、sidecar |
| **主な結果** | H-NH3-1〜6 いずれも SUPPORTED |
| **判定** | **SUPPORTED** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH4 — State Safety Boundary（拡張）

| 項目 | 内容 |
|------|------|
| **Run** | `20260826_201500/nh4_state_safety_boundary/` |
| **目的** | 形態素/同義正規化、timestamp/freshness、sidecar 最小セット |
| **検証内容** | Morph/Synonym 正規化、Evidence 鮮度、最小 sidecar |
| **主な結果** | 正規化は PARTIALLY_SUPPORTED（FR 増なし）; timestamp/sidecar は SUPPORTED |
| **判定** | **PARTIALLY_SUPPORTED**（正規化）/ **SUPPORTED**（他） |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH5 — Selector Selection

| 項目 | 内容 |
|------|------|
| **Run** | `20260827_134500/nh5_selector_selection_experiment/` |
| **目的** | 問題指紋から適切な検証手法をルール Selector で選択 |
| **検証内容** | 10 ケース gold、SUPPORTED vs experimental 区別、ESCALATE |
| **主な結果** | 10/10 gold; hard_reject、LARGE_LLM、mechanical_validator_priority |
| **判定** | **SUPPORTED in sim** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH6 — Fingerprint + Selector

| 項目 | 内容 |
|------|------|
| **Run** | `20260827_140500/nh6_fingerprint_selector_experiment/` |
| **目的** | 問題材料から LLM が指紋を生成し Selector に接続 |
| **検証内容** | LLM 指紋品質、二段分離、UNKNOWN 使用 |
| **主な結果** | B avg acc 45%; sel 7/10; safety 10/10; 品質がボトルネック |
| **判定** | **PARTIAL** |
| **現在の扱い** | experimental — 機械 mapping 優先の動機 |

---

## NH7 — Observation to Fingerprint

| 項目 | 内容 |
|------|------|
| **Run** | `20260827_143100/nh7_observation_to_fingerprint/` |
| **目的** | Observation 抽出と機械 mapping を分離 |
| **検証内容** | LLM obs、gold mapping、NH6 直出しとの比較 |
| **主な結果** | E fp 100% sel 10/10; D fp 83% vs B 43% |
| **判定** | **SUPPORTED in sim** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH8 — Uncertainty Gated Escalation

| 項目 | 内容 |
|------|------|
| **Run** | `20260827_145000/nh8_uncertainty_gated_escalation/` |
| **目的** | 不確実性の機械検出で大型 LLM 呼び出しを限定 |
| **検証内容** | Gate、large call 削減、誤選択減、ルール保存 |
| **主な結果** | B sel 9/10 → D 10/10; large 2 vs 10; safety 10/10 |
| **判定** | **SUPPORTED in sim** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH9 — Fixed Observation Escalation

| 項目 | 内容 |
|------|------|
| **Run** | `20260827_151000/nh9_fixed_observation_escalation/` |
| **目的** | Fixed slot、Observation/Fingerprint 分離、大型は HIGH slot のみ |
| **検証内容** | slot 充足、捏造 evidence 抑制、HUMAN_REVIEW |
| **主な結果** | C sel 8/10; fab evidence 0 vs 4; large 3 vs 10 |
| **判定** | **PARTIAL**（全体）/ 個別仮説は SUPPORTED in sim |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH10 — Mechanical Prefill Gate

| 項目 | 内容 |
|------|------|
| **Run** | `20260827_163000/nh10_mechanical_prefill_gate/` |
| **目的** | high_slots を機械 Prefill し Gate 取りこぼしを減らす |
| **検証内容** | H ケース修正、大型限定、Safety/Accuracy 分離 |
| **主な結果** | C sel 10/10; D large=1; soft safety 10/10 |
| **判定** | **SUPPORTED in sim** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH11 — Real-Log Shadow

| 項目 | 内容 |
|------|------|
| **Run** | `20260827_195500/nh11_real_shadow/` |
| **目的** | 実ログ（R=13, H=6）で Shadow パイプライン成立 |
| **検証内容** | Prefill、Gate、unsafe、HUMAN_REVIEW 分離 |
| **主な結果** | unsafe=0; validation 成立; human_review_rate 47%; large 47% |
| **判定** | **SUPPORTED in shadow** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH12 — Real-Log Shadow Expansion

| 項目 | 内容 |
|------|------|
| **Run** | `20260828_110500/nh12_real_shadow_expansion/` |
| **目的** | Shadow ケース +30 で経路安定性を確認 |
| **検証内容** | 拡張 30 件の Safety、HUMAN_REVIEW 率、材料不足 |
| **主な結果** | n=30 unsafe=0 missed=0; required slot missing 30; shortage 検出 |
| **判定** | **SUPPORTED in shadow** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH12-2 — Observation Compression

| 項目 | 内容 |
|------|------|
| **Run** | `20260828_114000/nh12_2_observation_compression/` |
| **目的** | 機械圧縮で material_shortage を解消 |
| **検証内容** | Compression → Observation mapping |
| **主な結果** | A→B shortage 29→0; verdict=SUPPORTED |
| **判定** | **SUPPORTED** |
| **現在の扱い** | experimental knowledge / adoption candidate |

---

## NH13 — Glossary Context Augmentation

| 項目 | 内容 |
|------|------|
| **Run** | `20260828_123600/nh13_glossary_context_experiment/` |
| **目的** | Glossary Context のみ変えて診断品質への影響を測定 |
| **検証内容** | 条件 A〜G（No/Full/Relevant/Definition/Boundary/LLM select 等） |
| **主な結果** | Full は unsafe=2; Relevant(D) が token 効率・Safety で最有力; 全体 PARTIALLY_SUPPORTED |
| **判定** | **PARTIALLY_SUPPORTED**（個別仮説は UNSUPPORTED / INCONCLUSIVE 多数） |
| **現在の扱い** | experimental — LLM 推論改善の主要手段とはしない |

---

## NH13-7 — Mechanical Glossary Selection

| 項目 | 内容 |
|------|------|
| **Run** | `20260828_131500/nh13_7_mechanical_glossary_selection/` |
| **目的** | 機械的に Relevant Glossary を選択 |
| **検証内容** | recall、token 効率、Safety、LLM 選択との比較 |
| **主な結果** | recall 0.76; D tok362 vs B tok1291; D unsafe=0 vs F |
| **判定** | **PARTIAL**（個別: token 効率 SUPPORTED） |
| **現在の扱い** | experimental — 条件付きで Relevant 選択を検討 |

---

## NH14 — Real-Log Shadow + External Help

| 項目 | 内容 |
|------|------|
| **Run** | `20260828_134500/nh14_real_log_shadow_external_help/` |
| **目的** | LLM 0 回で実ログ 12 件に機械パイプライン + External Help 生成 |
| **検証内容** | Compression→Obs→FP→Validator→Gate→Selector→Help |
| **主な結果** | SELF_RESOLVED 7 / EXTERNAL_HELP 5; unsafe=0; validation_ok 12/12 |
| **判定** | **PARTIAL_READY** |
| **現在の扱い** | experimental — 暫定完成形（安全引き渡しまで） |

---

## 関連実験（NH 番号外）

| Run | 内容 | 備考 |
|-----|------|------|
| `20260826_172800/goal_update_experiment/` | Goal 更新 | H-GOAL-1 unsupported |
| `20260826_180700/update_request_pipeline_experiment/` | Update Request + Manager | H-REQ-1 条件付き支持 |

これらは State 管理の前段研究として HYPOTHESIS_STATUS に記録されている。

---

## 時系列サマリー

```text
20260824-25  EXP-001〜010  search_web 診断基盤
20260826     NH1〜NH4       State 安全制約
20260827     NH5〜NH11      Selector〜実ログ Shadow
20260828     NH12〜NH14     拡張・圧縮・Glossary・External Help
```

仮完成版の区切り: **NH14 完了時点（2026-08-28）**
