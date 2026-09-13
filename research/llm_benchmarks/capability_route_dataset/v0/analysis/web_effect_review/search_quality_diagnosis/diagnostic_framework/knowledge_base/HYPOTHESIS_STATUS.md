# HYPOTHESIS_STATUS

状態ラベル: **支持** / **条件付き支持** / **部分的支持** / **反証** / **未検証** / **単独不支持**

| ID | 仮説 | 結果要約 | 状態 | 主根拠 |
|----|------|----------|------|--------|
| H-SPEC-1 | 仕様書を渡すとコード読解が改善する | 物語は改善、実装帰属は残る | **条件付き支持** | EXP-004 |
| H-SPEC-2 | 仕様 v2（存在/使用原則）で誤帰属が減る | 最重要項目で明確優位なし | **部分的支持〜限界支持** | EXP-005 |
| H-ROUTE-1 | route 分解で経路追跡が改善する | stdout/LLM 接続は改善、他は残差 | **条件付き支持** | EXP-006 |
| H-SPLIT-1 | collect と ranking を完全分離すると混同が減る | 限定的に有効 | **条件付き支持** | EXP-007 |
| H-EVID-1 | FACT/OBSERVED/INFERENCE/UNKNOWN でログ捏造が減る | OBSERVED 捏造抑制に有効 | **支持**（範囲限定） | EXP-007 |
| H-N1 | 接続を1本ずつ Yes/No すると誤接続が減る | 提案のみ | **未検証** | NEXT_HYPOTHESES 各所 |
| H-N2 | 経路存在ゲートが偽原因を排除する | 限界明確、本命効果はシード不足 | **条件付き支持（採用候補）** | EXP-008 |
| H-N2b | 偽原因シードで N2 再現率を測る | 未実施 | **未検証** | N2 NEXT |
| H-N3 | ログなし runtime 原因を UNKNOWN/空にする | 証拠境界の残り穴への提案 | **未検証（採用候補・仮説）** | EXP-007/008 NEXT |
| H-CTX | 大きい num_ctx とコード添付が必要 | 4096 問題 vs 32768 で支持 | **支持** | EXP-002/003 |
| H-DS | DeepSeek 交換で診断が十分改善する | 不十分・ctx 制約 | **単独不支持** | EXP-009 |
| H-LARGE | 大型LLM全体診断が有望 | search_web セットで改善 | **条件付き支持（継続検証）** | EXP-010 |
| H-2STAGE | 小型局所＋大型統合が最適 | 有望と評価、パイプライン未実験 | **未検証（有望仮説）** | EXP-010 |
| H-SEL | LLM が診断方法を自律選択できる | ルールSelector暫定あり／LLM自律は未 | **未検証**（ルール部は条件付き実装） | `selector/` + knowledge_base |
| H-AUTOFIX | 診断後に安全に自己修復できる | 一貫して NOT_ALLOWED／危険 | **未検証／現状不支持（実行）** | 複数 SELF_VERIFY / EXP-010 |

| H-GOAL-1 | Goal必須レビューで更新漏れが減る（過剰は増えない） | 判定:unsupported | **実験候補（unsupported）** | `runs/20260826_172800/goal_update_experiment/` |
| H-REQ-1 | Update Request+Manager で誤Goal更新（FA）が減る | FA 6→1、C追加はFA非改善 | **条件付き支持（experimental）** | `runs/20260826_180700/update_request_pipeline_experiment/` |
| H-REV-1 | Request二次レビューが常時有効 | FA改善なし・FR増・SU07見逃し | **単独不支持（常時）** | 同上 |

| H-NH1-1 | SUPERSEDED exact Goal 再Activeを機械拒否 | Strong Support; FR非増・NH1-07許可 | **実験候補（Strong Support）** | `runs/20260826_183500/nh1_state_transition_constraints/` |

### 読み方

- **支持:** 当該範囲で再現された効果がある  
- **条件付き支持:** 効く条件・効かない条件が報告されている  
- **単独不支持:** 「それだけで十分」は否定された（部品としての利用を否定しない場合あり）  
- **未検証:** 提案または一回限りで一般化不能
| H-NH2-1 | exact再Active禁止をGoal/Claim/Hypothesisへ一般化 | Supported (generalization); Cで危険FA=0, DでREOPEN例外 | **実験候補** | `runs/20260826_190000/nh2_state_transition_generalization/` |
| H-NH3-1 | near-exact normalizationで安全性向上 | SUPPORTED; punct/NFKCをCが拒否、Bはすり抜け | **実験候補** | `runs/20260826_191500/nh3_state_safety_boundary/` |
| H-NH3-2 | normalizationでFR増 | SUPPORTED; 新Goal非拒否、語尾はUNKNOWN | **実験候補** | 同上 |
| H-NH3-3 | Evidence実在確認でREOPEN安全 | SUPPORTED | **実験候補** | 同上 |
| H-NH3-4 | content validationで架空/不一致防止 | SUPPORTED | **実験候補** | 同上 |
| H-NH3-5 | sidecar観測が判断品質改善 | SUPPORTED | **実験候補** | 同上 |
| H-NH3-6 | 安全性は機械制約追加で安定 | SUPPORTED（FA/unsafe_acceptが制約追加で低下; experimental） | **実験候補** | 同上 |
| H-NH4-1 | 形態素/同義正規化で安全性↑ | PARTIALLY_SUPPORTED; FR増=NO | **実験候補** | `runs/20260826_201500/nh4_state_safety_boundary/` |
| H-NH4-2 | Evidence timestamp/freshness | SUPPORTED | **実験候補** | 同上 |
| H-NH4-3 | sidecar最小セット | SUPPORTED; minimal=D (test + runtime + evidence_content) | **実験候補** | 同上 |

| H-NH5-1 | 問題指紋から適切な検証手法を選択 | 10/10 gold; rule+委譲合成 | **実験候補（SUPPORTED in sim）** | `runs/20260827_134500/nh5_selector_selection_experiment/` |
| H-NH5-2 | SUPPORTED vs experimental 区別 | status付与; experimentalをadopt扱いしない | **実験候補** | 同上 |
| H-NH5-3 | 方法を選ばない判断 | hard_reject全ケース適用 | **実験候補** | 同上 |
| H-NH5-4 | 情報不足でUNKNOWN/ESCALATE | H/E/F/Jで発火 | **実験候補** | 同上 |
| H-NH5-5 | 小型LLM→大型エスカレーション | I/A/BでLARGE_LLM | **実験候補** | 同上 |
| H-NH5-6 | State変更で機械Validator優先 | C/Dでmechanical_validator_priority | **実験候補** | 同上 |

| H-NH6-1 | 問題材料からLLM指紋生成 | B avg acc=45%; parse 8/10 | **実験候補（PARTIAL）** | `runs/20260827_140500/nh6_fingerprint_selector_experiment/` |
| H-NH6-2 | LLM指紋でSelector維持 | B sel 7/10, C 4/10; safety 10/10 | **実験候補（PARTIAL）** | 同上 |
| H-NH6-3 | UNKNOWN使用 | uncertainties使用例あり; 空出力も | **実験候補（PARTIAL）** | 同上 |
| H-NH6-4 | 二段階切り分け | fingerprint vs selector分離成功 | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH6-5 | 前段LLM指紋の実用価値 | 接続成立; 品質がボトルネック | **実験候補（PARTIAL）** | 同上 |

| H-NH7-1 | LLM観測抽出が成立 | C slot 89%; parse 10/10 empty 0 | **実験候補（SUPPORTED in sim）** | `runs/20260827_143100/nh7_observation_to_fingerprint/` |
| H-NH7-2 | 機械mappingがgold obsからFP復元 | E fp 100% sel 10/10 | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH7-3 | obs→map が NH6直出しより優れる | D fp 83% sel 9/10 vs B 43% 7/10; F2/F3=0 | **実験候補（SUPPORTED in sim）** | 同上 |

| H-NH8-1 | 小型Observationを基本経路 | B sel 9/10 safety 10/10 | **実験候補（SUPPORTED in sim）** | `runs/20260827_145000/nh8_uncertainty_gated_escalation/` |
| H-NH8-2 | 不確実性の機械検出 | J/FをHIGH; A/C/GはLOW | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH8-3 | 常時大型より効率 | large 2 vs 10; missed 0 | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH8-4 | ゲートで誤選択減 | B 9/10 → D 10/10（JをHUMAN_REVIEW） | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH8-5 | エスカレーション条件をルール保存 | uncertainty_gate.py + rules.json | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH8-6 | 大型もMapping/境界を通す | D safety 10/10; auto_fix false; ログ捏造0 | **実験候補（SUPPORTED in sim）** | 同上 |

| H-NH9-1 | Fixed Observation slot で取りこぼし減 | C fp 84% sel 8/10; ceiling 10/10; slot~53% | **実験候補（PARTIAL）** | `runs/20260827_151000/nh9_fixed_observation_escalation/` |
| H-NH9-2 | Observation と Fingerprint 分離 | LLMはslotのみ; gold mapping ceiling 10/10 | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH9-3 | 大型を不確実slot再観測に限定 | C large 3 vs D 10; fab evidence 0 vs 4; F7=0 | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH9-4 | 大型回答の Mechanical Validation | I disagreement捏造拒否; C fab evidence 0 | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH9-5 | 残HIGH→HUMAN_REVIEWでSafety維持 | J/I remain→HUMAN; false accept 0; HはGate見逃し | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH9-6 | NH8より再現性・監査性 | 監査単位は改善; Selectorは8/10<NH8の10/10 | **実験候補（PARTIAL）** | 同上 |

| H-NH10-1 | high_slotsを理由付き明示で取りこぼし減 | H Gate HIGH; missed_high=0; reason→slot保存 | **実験候補（SUPPORTED in sim）** | `runs/20260827_163000/nh10_mechanical_prefill_gate/` |
| H-NH10-2 | Mechanical Prefillで安全取りこぼし減 | C sel 10/10; H修正; LLM再観測なし | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH10-3 | LargeはHIGH slot訂正に限定 | D large=1; fab 0; unnecessary/missed=0 | **実験候補（SUPPORTED in sim）** | 同上 |
| H-NH10-4 | SafetyとAccuracy分離評価 | soft 10/10; Iをsafe_but_human_reviewとして分離 | **実験候補（SUPPORTED in sim）** | 同上 |

| H-NH11-1 | 実ログでもObs→Prefill→Gate→Shadow成立 | R13+H6; unsafe/auto_fix/fab=0; large 47% | **実験候補（SUPPORTED in shadow）** | `runs/20260827_195500/nh11_real_shadow/` |
| H-NH11-2 | Prefill/high_slotsがRealでも機能 | content_empty→HIGH; WB02 unnecessary Large=0 | **実験候補（SUPPORTED in shadow）** | 同上 |
| H-NH11-3 | HUMAN_REVIEWを失敗とせず制御可能 | safe_HUMAN_REVIEW=9 / unsafe=0; rate≈47% | **実験候補（SUPPORTED in shadow）** | 同上 |

| H-NH12-1 | Shadowケース+30でも経路安定 | n=30; unsafe=0; missed=0 | **実験候補（SUPPORTED in shadow）** | `runs/20260828_110500/nh12_real_shadow_expansion/` |
| H-NH12-2 | 拡張でHUMAN_REVIEW率急上昇しない | rate=0% vs NH11 47% | **実験候補** | 同上 |
| H-NH12-3 | 材料不足LOWを検出可能 | shortage=29 cases | **実験候補** | 同上 |
| H-NH12-2-1 | Compressionでmaterial_shortage改善 | A→B shortage 29→0; verdict=SUPPORTED | **実験候補（SUPPORTED）** | `runs/20260828_114000/nh12_2_observation_compression/` |

| H-NH13-1 | Glossary ContextでObservation品質改善 | slot微増のみ; Safety悪化あり; UNSUPPORTED | **experimental** | `runs/20260828_123600/nh13_glossary_context_experiment/` |
| H-NH13-2 | Boundary/DO-NOTがDefinitionより有効 | F slot+1.4%だがfp-16%; INCONCLUSIVE | **experimental** | 同上 |
| H-NH13-3 | Relevant≈Fullでtoken効率優位 | D fp+1% tok186 vs B tok1291; PARTIAL | **experimental** | 同上 |
| H-NH13-4 | Role Contextが定義より有効 | G≈A; UNSUPPORTED | **experimental** | 同上 |
| H-NH13-5 | Safety維持しAccuracy改善 | 改善条件でunsafe>0; UNSUPPORTED | **experimental** | 同上 |
| H-NH13-6 | 改善はKnowledge vs Reasoning | terminology混同0; 主因はMixed/Reasoning; PARTIAL | **experimental** | 同上 |

| H-NH13-7-1 | 機械的Relevant Glossary選択 | recall 0.76; reproducible; PARTIAL | **experimental** | `runs/20260828_131500/nh13_7_mechanical_glossary_selection/` |
| H-NH13-7-2 | MechanicalはFullよりtoken効率 | D tok362 vs B tok1291; SUPPORTED | **experimental** | 同上 |
| H-NH13-7-3 | MechanicalはNo Glossary以上 | D slot=0.527≈A; PARTIAL | **experimental** | 同上 |
| H-NH13-7-4 | MechanicalはLLM選択より安全・再現 | D unsafe=0 vs F; F recall低; PARTIAL | **experimental** | 同上 |
| H-NH13-7-5 | Glossary過多で副作用増 | B fab=2; D/E/F=0; INCONCLUSIVE | **experimental** | 同上 |

| H-NH14-1 | 実ログ機械Shadow+External Help | 12 cases; unsafe=0; ext_help=5; PARTIAL_READY | **experimental** | `runs/20260828_134500/nh14_real_log_shadow_external_help/` |
