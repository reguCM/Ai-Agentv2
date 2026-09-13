# COMPRESSION_SCHEMA — NH12-2

Mechanical Log Compression は原因推測を行わない。各フィールドは観測事実のみ。

## Status 語彙

| status | 意味 |
|--------|------|
| FACT | 材料に明示的な値がある |
| PRESENT | 存在は確認、詳細値は限定的 |
| ABSENT | 材料が明示的に不在 |
| UNKNOWN | 材料に記載なし（LLMに推測させない） |

## Fixed Slots

| slot | 抽出元 | 例 |
|------|--------|-----|
| runtime | runtime_log | `[OBSERVED]` 行の有無 |
| tool | agent_tools_tried | tool名リスト |
| search | tools_tried / stages | outcome, hit_count, api_raw_total |
| ranking | stages / case_trace | after_ranking, return件数 |
| evidence | raw_api_digest | digest_present |
| state | state_context | 変更要求の有無 |
| error | outcome=error, exception | error messages |
| output | stages handoff counts | llm_handoff_* |
| code_path | code_excerpt | コード抜粋の有無 |
| timestamp | execution_identity ts | ISO timestamp |

## 禁止

- 原因推測
- 意図推測
- 同義語による意味拡張
- 材料にない event type の捏造

## Failure タグ（圧縮層）

- F1 compression omission
- F4 UNKNOWN消失（圧縮後に不明が消える）
