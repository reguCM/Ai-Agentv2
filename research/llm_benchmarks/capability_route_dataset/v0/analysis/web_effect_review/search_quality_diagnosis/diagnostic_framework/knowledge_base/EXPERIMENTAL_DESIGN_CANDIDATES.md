# EXPERIMENTAL_DESIGN_CANDIDATES

本番仕様ではない。実験で有望だった設計候補のみ追記する。

## H6 Goal Mandatory Review (2026-08-26)

- **status:** `unsupported` (NOT production spec; recorded as negative experimental result)
- **run:** `runs/20260826_172800/goal_update_experiment/`
- **note:** Goal 必須レビュー・プロンプトだけでは、明示訂正（G06）で `goal_action=replace` でも goal 文字列が旧のまま残る。本番昇格なし。次は一貫性ゲート（NH1）を検討。

## Update Request Protocol (Condition B) (2026-08-26)

- **status:** `experimental candidate` (NOT production spec)
- **run:** `runs/20260826_180700/update_request_pipeline_experiment/`
- **note:** LLM→Request→Manager で False Accept が A=6→B=1。常時二次レビュー(C)は FA 改善なし・FR 増。Gate は写像。残課題は旧Goal再activeの機械拒否。昇格なし。

## NH1 NO_REACTIVATE_SUPERSEDED_VALUE (2026-08-26)

- **status:** `Strong Support` (experimental — NOT production)
- **run:** `runs/20260826_183500/nh1_state_transition_constraints/`
- **note:** exact superseded goal string の再 Active を機械拒否。 類似新文言（NH1-07）は許可。本番昇格なし。

## NH2 Change Request + History Validator (2026-08-26)

- **status:** `Supported (generalization)` (experimental — NOT production)
- **run:** `runs/20260826_190000/nh2_state_transition_generalization/`
- **note:** Goal/Claim/Hypothesis で exact 過去値の無条件再Activeを機械拒否。 REOPEN_WITH_EVIDENCE は正当再評価に必要。near-exact は UNKNOWN。 本番昇格なし。

## NH3 near-exact + evidence + sidecar (2026-08-26)

- **status:** experimental ({"H-NH3-1": "SUPPORTED", "H-NH3-2": "SUPPORTED", "H-NH3-3": "SUPPORTED", "H-NH3-4": "SUPPORTED", "H-NH3-5": "SUPPORTED", "H-NH3-6": "PARTIALLY_SUPPORTED"})
- **run:** `runs/20260826_191500/nh3_state_safety_boundary/`
- **note:** normalized再Active禁止はexactの穴を埋める。 REOPENはevidence実在+内容照合が必要。sidecarは追加拒否材料。 本番昇格なし。

## NH4 morph/timestamp/sidecar ablation (2026-08-26)

- **status:** experimental ({"H-NH4-1": "PARTIALLY_SUPPORTED", "H-NH4-1_FR_increase": "NO", "H-NH4-2": "SUPPORTED", "H-NH4-3": "SUPPORTED", "minimal_sidecar": "D (test + runtime + evidence_content)", "unknown_improves_safety": true})
- **run:** `runs/20260826_201500/nh4_state_safety_boundary/`
- **note:** 同義正規化は安全↑だがFRリスク（昇格しない）。 content+timestamp/staleは有効。sidecar最小は test+runtime+evidence_content。 本番昇格なし。method_catalog確定昇格なし。

