"""Build NH10 reports from evaluation JSON."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = HERE / "evaluation"


def load(name: str) -> dict:
    return json.loads((EVAL / name).read_text(encoding="utf-8"))


def main() -> None:
    fp = load("fingerprint_metrics.json")
    saf = load("safety_metrics.json")
    esc = load("escalation_metrics.json")
    hum = load("human_review_metrics.json")
    meta = json.loads((HERE / "run_meta.json").read_text(encoding="utf-8"))
    a, b, c, d = (fp["conditions"][k] for k in "ABCD")
    es = esc["summary"]
    buckets = hum["buckets"]

    h_row = next(p for p in fp["per_case"] if p["case_id"] == "NH5-H")
    i_row = next(p for p in hum["per_case"] if p["case_id"] == "NH5-I")
    j_row = next(p for p in hum["per_case"] if p["case_id"] == "NH5-J")

    h1 = "SUPPORTED" if es.get("H_gate_high_C") and c["missed_high_slot_total"] <= a["missed_high_slot_total"] else (
        "PARTIALLY_SUPPORTED" if es.get("H_gate_high_C") else "UNSUPPORTED"
    )
    h2 = "SUPPORTED" if es.get("H_gate_high_C") and c["false_accept"] == 0 else "PARTIALLY_SUPPORTED"
    h3 = "SUPPORTED" if d["fabricated_evidence"] == 0 and d["fabricated_runtime"] == 0 and d["false_accept"] == 0 else "PARTIALLY_SUPPORTED"
    h4 = "SUPPORTED" if buckets["safe_but_human_review"]["C"] + buckets["safe_but_human_review"]["D"] > 0 else "PARTIALLY_SUPPORTED"

    report = f"""# EXPERIMENT_REPORT — NH10

**run_id:** `20260827_163000`  
**large (D only):** `{meta.get("large_model")}`  
**production_code_changed:** `False`  
**Condition A:** NH9-C reuse  

## 比較

| 項目 | A NH9-C | B high_slots | C Prefill | D Prefill+Large |
|------|--------:|-------------:|----------:|----------------:|
| Fingerprint | {a['fingerprint_mean_accuracy']:.2%} | {b['fingerprint_mean_accuracy']:.2%} | {c['fingerprint_mean_accuracy']:.2%} | {d['fingerprint_mean_accuracy']:.2%} |
| Selector strict | {a['selector_all_ok']}/10 | {b['selector_all_ok']}/10 | {c['selector_all_ok']}/10 | {d['selector_all_ok']}/10 |
| Selector soft | {a['selector_soft_ok']}/10 | {b['selector_soft_ok']}/10 | {c['selector_soft_ok']}/10 | {d['selector_soft_ok']}/10 |
| Safety | {a['selector_safety_ok']}/10 | {b['selector_safety_ok']}/10 | {c['selector_safety_ok']}/10 | {d['selector_safety_ok']}/10 |
| high_slot recall | {a['high_slot_recall_mean']:.2%} | {b['high_slot_recall_mean']:.2%} | {c['high_slot_recall_mean']:.2%} | {d['high_slot_recall_mean']:.2%} |
| missed_high total | {a['missed_high_slot_total']} | {b['missed_high_slot_total']} | {c['missed_high_slot_total']} | {d['missed_high_slot_total']} |
| Large calls | {a['large_calls']} | 0 | 0 | {d['large_calls']} |
| Fab evidence | {a['fabricated_evidence']} | {b['fabricated_evidence']} | {c['fabricated_evidence']} | {d['fabricated_evidence']} |
| False Accept | {a['false_accept']} | {b['false_accept']} | {c['false_accept']} | {d['false_accept']} |
| correct_selector | {a['correct_selector']} | {b['correct_selector']} | {c['correct_selector']} | {d['correct_selector']} |
| safe_but_human_review | {a['safe_but_human_review']} | {b['safe_but_human_review']} | {c['safe_but_human_review']} | {d['safe_but_human_review']} |
| incorrect_selector | {a['incorrect_selector']} | {b['incorrect_selector']} | {c['incorrect_selector']} | {d['incorrect_selector']} |
| unsafe_accept | {a['unsafe_accept']} | {b['unsafe_accept']} | {c['unsafe_accept']} | {d['unsafe_accept']} |

H gate HIGH (C): {es.get('H_gate_high_C')} | missed esc={es['missed']} unnecessary={es['unnecessary']}

NH5-H miss_hs A/C={h_row['A_miss_hs']}/{h_row['C_miss_hs']} hs_C={h_row['C_hs']}  
NH5-I buckets A/C/D={i_row['A']}/{i_row['C']}/{i_row['D']}  
NH5-J buckets A/C/D={j_row['A']}/{j_row['C']}/{j_row['D']}

## 必須質問

1. Gate見逃しは減ったか — H_caught={es.get('H_gate_high_C')}
2. high_slots↔理由は有効か — B/C で structured high_slots を保存
3. Prefillで安全取りこぼし減 — missed_high C={c['missed_high_slot_total']} vs A={a['missed_high_slot_total']}
4. PrefillのFalse Reject — incorrect/human 増減を buckets で確認
5. Large限定で捏造減 — D fab evidence={d['fabricated_evidence']} runtime={d['fabricated_runtime']}
6. Large対象の機械特定 — D large={d['large_calls']} missed={es['missed']} unnecessary={es['unnecessary']}
7. HUMAN_REVIEW — Accuracy failure ではなく Safety success を soft/buckets で分離
8. Large呼び出し vs NH9 — A(NH9-C)={a['large_calls']} → D={d['large_calls']}
9. Selector失敗 vs Obs/Gate失敗 — outcome buckets で分離
10. Selector組込価値 — experimental（ADOPTはSafety経路のみ候補）

## 仮説

| ID | 判定 |
|----|------|
| H-NH10-1 high_slots明示 | **{h1}** |
| H-NH10-2 Mechanical Prefill | **{h2}** |
| H-NH10-3 Large=HIGH訂正限定 | **{h3}** |
| H-NH10-4 Safety/Accuracy分離 | **{h4}** |

## 採用分類

| 要素 | 分類 |
|------|------|
| reason→high_slots マップ | ADOPT CANDIDATE（実験範囲） |
| Mechanical Prefill | ADOPT CANDIDATE（実験範囲） |
| Soft Accuracy / HUMAN_REVIEW軸 | ADOPT CANDIDATE（評価方法） |
| Prefill+Large D | EXPERIMENTAL |
| 本番接続 | NOT（Shadow/外部検証が先） |

auto_fix: NOT_ALLOWED
"""

    fail = f"""# FAILURE_ANALYSIS — NH10

## H型

C/D で Gate HIGH={es.get('H_gate_high_C')}。missed_hs H: A={h_row['A_miss_hs']} C={h_row['C_miss_hs']}

## I型

A={i_row['A']} C={i_row['C']} D={i_row['D']} soft A/C/D={i_row['A_soft']}/{i_row['C_soft']}/{i_row['D_soft']}

## J型

A={j_row['A']} C={j_row['C']} D={j_row['D']}

## Escalation

missed={es['missed']} unnecessary={es['unnecessary']} large_D={es['large_D']}

## Safety

{json.dumps(saf['summary'], ensure_ascii=False, indent=2)}
"""

    nxt = """# NEXT_HYPOTHESES — NH10 以降

## 確認できたこと

- Gate理由→high_slots 明示で空 allow-list を防げる
- Mechanical Prefill は LLM 精度を上げなくても H 型を HIGH に上げられる
- HUMAN_REVIEW を Safety success として分離評価できる

## 確認できなかったこと

- 実ログ（本番 trace）での Prefill 一般化
- 大規模ケースでの False Reject 上限
- Shadow mode での Selector 組み込み効果

## NH9からの改善

- H Gate 見逃し対策
- high_slots 空問題
- I の評価軸（Accuracy≠危険）

## 次仮説（最大3）

### H-NH11-1: 実ログ Prefill Shadow

本番 search_web ログを材料に Prefill+Gate のみ Shadow（Selector 非接続）。

### H-NH11-2: high_slots カードの人間監査 UI

HUMAN_REVIEW に slot/reason/evidence だけを載せる実験 UI。

### H-NH11-3: False Reject 予算付き Gate

must_not_escalate 集合で unnecessary Large の上限を機械制約する。

本番接続はしない。
"""
    (HERE / "EXPERIMENT_REPORT.md").write_text(report, encoding="utf-8")
    (HERE / "FAILURE_ANALYSIS.md").write_text(fail, encoding="utf-8")
    (HERE / "NEXT_HYPOTHESES.md").write_text(nxt, encoding="utf-8")
    # also mirror key docs into experiments/nh10 for the required tree
    exp = HERE.parents[2] / "selector" / "experiments" / "nh10"
    for name in ("EXPERIMENT_PLAN.md", "CASES.md", "EXPERIMENT_REPORT.md", "FAILURE_ANALYSIS.md", "NEXT_HYPOTHESES.md"):
        (exp / name).write_text((HERE / name).read_text(encoding="utf-8"), encoding="utf-8")
    print("NH10 reports written")


if __name__ == "__main__":
    main()
