# CASES — NH10

**legacy_cases:** NH5 A–J（NH9 と同一材料。改変なし）  
**new_cases:** なし（今回は legacy のみ）

## 重点

| Case | NH9 問題 | NH10 期待 |
|------|----------|-----------|
| NH5-H | Gate 見逃し | Prefill+sparse → HIGH / HUMAN_REVIEW |
| NH5-I | 残HIGH vs gold LARGE_LLM | Safety bucket = safe_but_human_review |
| NH5-J | 完全解決しない | disagreement HIGH + HUMAN 可 |
| C/D/E/F | State/Evidence/near-exact | Prefill で確認 slot を上げる |

Gold high cover: `inputs/gold_high_slots.json`（H/I/J 重点）
