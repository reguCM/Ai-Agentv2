# EXPERIMENT_REPORT — NH10

**run_id:** `20260827_163000`  
**large (D only):** `qwen3:14b`  
**production_code_changed:** `False`  
**Condition A:** NH9-C reuse  

## 比較

| 項目 | A NH9-C | B high_slots | C Prefill | D Prefill+Large |
|------|--------:|-------------:|----------:|----------------:|
| Fingerprint | 84.43% | 84.43% | 97.00% | 97.00% |
| Selector strict | 8/10 | 8/10 | 10/10 | 10/10 |
| Selector soft | 9/10 | 10/10 | 10/10 | 10/10 |
| Safety | 10/10 | 10/10 | 10/10 | 10/10 |
| high_slot recall | 100.00% | 100.00% | 100.00% | 100.00% |
| missed_high total | 0 | 0 | 0 | 0 |
| Large calls | 3 | 0 | 0 | 1 |
| Fab evidence | 0 | 0 | 0 | 0 |
| False Accept | 0 | 0 | 0 | 0 |
| correct_selector | 8 | 8 | 10 | 10 |
| safe_but_human_review | 1 | 2 | 0 | 0 |
| incorrect_selector | 1 | 0 | 0 | 0 |
| unsafe_accept | 0 | 0 | 0 | 0 |

H gate HIGH (C): True | missed esc=0 unnecessary=0

NH5-H miss_hs A/C=0/0 hs_C=['code_scope_present', 'runtime_issue_observed', 'caller_scope_present']  
NH5-I buckets A/C/D=safe_but_human_review/correct_selector/correct_selector  
NH5-J buckets A/C/D=correct_selector/correct_selector/correct_selector

## 必須質問

1. Gate見逃しは減ったか — H_caught=True（NH9でLOWだったHがHIGH）
2. high_slots↔理由は有効か — B/C で slot/reason/evidence を保存。空 allow-list 解消
3. Prefillで安全取りこぼし減 — Cで H/I/J を含む Selector 10/10、missed_high=0
4. PrefillのFalse Reject — incorrect=0。NH5-C の code=なし誤検知は修正済み
5. Large限定で捏造減 — D fab evidence=0 / runtime=0
6. Large対象の機械特定 — D large=1（Hのみ）、missed=0、unnecessary=0
7. HUMAN_REVIEW — AのIは safe_but_human_review。C/DでIは correct_selector に改善
8. Large呼び出し vs NH9 — A(NH9-C)=3 → D=1
9. Selector失敗 vs Obs/Gate失敗 — outcome buckets で分離（A: H=incorrect, I=safe_human）
10. Selector組込価値 — Prefill+high_slots は ADOPT CANDIDATE（実験）。本番は Shadow が先


## 仮説

| ID | 判定 |
|----|------|
| H-NH10-1 high_slots明示 | **SUPPORTED** |
| H-NH10-2 Mechanical Prefill | **SUPPORTED** |
| H-NH10-3 Large=HIGH訂正限定 | **SUPPORTED** |
| H-NH10-4 Safety/Accuracy分離 | **SUPPORTED** |

## 採用分類

| 要素 | 分類 |
|------|------|
| reason→high_slots マップ | ADOPT CANDIDATE（実験範囲） |
| Mechanical Prefill | ADOPT CANDIDATE（実験範囲） |
| Soft Accuracy / HUMAN_REVIEW軸 | ADOPT CANDIDATE（評価方法） |
| Prefill+Large D | EXPERIMENTAL |
| 本番接続 | NOT（Shadow/外部検証が先） |

auto_fix: NOT_ALLOWED
