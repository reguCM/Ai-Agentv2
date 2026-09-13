# KSS-1.4 Information Loss & Discarded-Hit Answer Audit

- experiment_dir: `D:\AI-Agent\research\llm_benchmarks\knowledge_source_obs\kss14_20260820_155500`
- cases: 5 (success=1, fail=4)
- routing_implemented: `False`
- not_for_decision: `True`

## Answer presence totals

- total_web_hits (sum over annotated): 175.0
- kept_hits: 175.0
- dropped_hits: None
- direct/core/lead in kept: 0.0/136.0/0.0
- direct/core/lead in dropped: None/None/None
- unknown_count: 0.0
- failed_runs_with_answer_in_dropped_hit: 0
- failed_runs_with_answer_in_kept_hit: 3
- failed_runs_with_no_answer_found: 1

> Historical KSS-1.1/1.3 JSON usually lack `dropped_hits` → dropped_* may be missing/0. Live `web_hit_partition` fixes this.

## Focus trajectories

### cpu_temperature

- pass=False fail_stage=judge stop=max_research_rounds
- labels: ['JUDGE不足', 'PROGRESS不足', 'STAGNATION']
- first_loss: {'round': 1, 'label': 'VERIFICATION不足', 'stage': 'candidate_verified'}
- web_vs_llm: ['case6_gain_then_no_gain_streak', 'case4_candidate_verify_ng', 'case2_hit_no_candidate', 'round_no_gain', 'case5_usable_judge_ng']
- answer_run: `{"aggregates_sum": {"total_web_hits": 59.0, "kept_hits": 59.0, "direct_in_kept": 0.0, "core_in_kept": 59.0, "lead_in_kept": 0.0, "unknown_count": 0.0}, "answer_in_kept_hit": true, "answer_in_dropped_hit": "missing", "valuable_only_in_dropped": "missing", "dropped_hits_observed": false, "lead_then_next_gain": {"lead_rounds": 0, "next_gain_true": 0, "next_gain_false": 0, "next_gain_missing": 0}}`

  - r1: hit=5 cand=2 linked=2 usable=0 gain=False no_gain=False new_term=102 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r2: hit=5 cand=1 linked=1 usable=0 gain=False no_gain=False new_term=0 action=continue/new_information loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r3: hit=8 cand=0 linked=0 usable=0 gain=False no_gain=True new_term=0 action=continue/no_progress loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r4: hit=8 cand=1 linked=1 usable=0 gain=False no_gain=True new_term=1 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r5: hit=8 cand=0 linked=0 usable=0 gain=False no_gain=True new_term=0 action=continue/new_information loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r6: hit=5 cand=3 linked=3 usable=0 gain=False no_gain=True new_term=8 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r7: hit=5 cand=1 linked=1 usable=0 gain=True no_gain=True new_term=2 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r8: hit=5 cand=1 linked=1 usable=0 gain=True no_gain=False new_term=0 action=continue/new_information loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r9: hit=5 cand=1 linked=1 usable=1 gain=True no_gain=False new_term=4 action=continue/new_information loss={'stage': 'judge_satisfied', 'observational_label': 'JUDGE不足', 'count': False, 'note': 'first False/zero along chain; not blame assignment'}
  - r10: hit=5 cand=0 linked=0 usable=0 gain=True no_gain=False new_term=0 action=stop/max_research_rounds loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}

### disk_usage

- pass=False fail_stage=research stop=stagnation
- labels: ['VERIFICATION不足', 'PROGRESS不足', 'STAGNATION']
- first_loss: {'round': 1, 'label': 'SEARCH不足', 'stage': 'web_hit_kept'}
- web_vs_llm: ['case6_gain_then_no_gain_streak', 'case1_no_web_hit', 'case3_candidate_no_link', 'case4_candidate_verify_ng', 'round_no_gain']
- answer_run: `{"aggregates_sum": {"total_web_hits": 44.0, "kept_hits": 44.0, "direct_in_kept": 0.0, "core_in_kept": 6.0, "lead_in_kept": 0.0, "unknown_count": 0.0}, "answer_in_kept_hit": true, "answer_in_dropped_hit": "missing", "valuable_only_in_dropped": "missing", "dropped_hits_observed": false, "lead_then_next_gain": {"lead_rounds": 0, "next_gain_true": 0, "next_gain_false": 0, "next_gain_missing": 0}}`

  - r1: hit=0 cand=4 linked=0 usable=0 gain=False no_gain=False new_term=7 action=continue/no_progress loss={'stage': 'web_hit_kept', 'observational_label': 'SEARCH不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r2: hit=5 cand=4 linked=2 usable=0 gain=False no_gain=False new_term=78 action=continue/new_information loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r3: hit=8 cand=3 linked=3 usable=0 gain=False no_gain=True new_term=122 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r4: hit=8 cand=1 linked=1 usable=0 gain=False no_gain=True new_term=0 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r5: hit=8 cand=3 linked=2 usable=0 gain=True no_gain=True new_term=8 action=continue/new_information loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r6: hit=5 cand=4 linked=2 usable=0 gain=False no_gain=False new_term=5 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r7: hit=5 cand=3 linked=2 usable=0 gain=False no_gain=True new_term=2 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r8: hit=5 cand=1 linked=1 usable=0 gain=False no_gain=True new_term=2 action=stop/stagnation loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}

### gpu_vram_usage

- pass=False fail_stage=research stop=max_research_rounds
- labels: ['VERIFICATION不足', 'PROGRESS不足', 'STAGNATION']
- first_loss: {'round': 1, 'label': 'VERIFICATION不足', 'stage': 'candidate_verified'}
- web_vs_llm: ['case6_gain_then_no_gain_streak', 'case4_candidate_verify_ng', 'case3_candidate_no_link', 'case2_hit_no_candidate', 'round_no_gain']
- answer_run: `{"aggregates_sum": {"total_web_hits": 71.0, "kept_hits": 71.0, "direct_in_kept": 0.0, "core_in_kept": 71.0, "lead_in_kept": 0.0, "unknown_count": 0.0}, "answer_in_kept_hit": true, "answer_in_dropped_hit": "missing", "valuable_only_in_dropped": "missing", "dropped_hits_observed": false, "lead_then_next_gain": {"lead_rounds": 0, "next_gain_true": 0, "next_gain_false": 0, "next_gain_missing": 0}}`

  - r1: hit=5 cand=2 linked=2 usable=0 gain=False no_gain=False new_term=107 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r2: hit=8 cand=2 linked=0 usable=0 gain=True no_gain=False new_term=5 action=continue/new_information loss={'stage': 'candidate_linked', 'observational_label': 'LINK不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r3: hit=8 cand=2 linked=0 usable=0 gain=False no_gain=False new_term=4 action=continue/no_progress loss={'stage': 'candidate_linked', 'observational_label': 'LINK不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r4: hit=8 cand=0 linked=0 usable=0 gain=False no_gain=True new_term=0 action=continue/no_progress loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r5: hit=8 cand=0 linked=0 usable=0 gain=False no_gain=True new_term=0 action=continue/new_information loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r6: hit=8 cand=0 linked=0 usable=0 gain=False no_gain=True new_term=0 action=continue/no_progress loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r7: hit=8 cand=0 linked=0 usable=0 gain=False no_gain=True new_term=0 action=continue/no_progress loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r8: hit=8 cand=0 linked=0 usable=0 gain=False no_gain=True new_term=0 action=continue/new_information loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r9: hit=5 cand=1 linked=1 usable=0 gain=False no_gain=True new_term=1 action=continue/no_progress loss={'stage': 'candidate_verified', 'observational_label': 'VERIFICATION不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}
  - r10: hit=5 cand=0 linked=0 usable=0 gain=False no_gain=True new_term=0 action=stop/max_research_rounds loss={'stage': 'candidate_available', 'observational_label': 'SEARCH→CANDIDATE変換不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}

### memory_usage

- pass=True fail_stage=None stop=findings_complete
- labels: ['LINK不足', 'success_trajectory']
- first_loss: {'round': 1, 'label': 'LINK不足', 'stage': 'candidate_linked'}
- web_vs_llm: ['case3_candidate_no_link']
- answer_run: `{"aggregates_sum": {"total_web_hits": 1.0, "kept_hits": 1.0, "direct_in_kept": 0.0, "core_in_kept": 0.0, "lead_in_kept": 0.0, "unknown_count": 0.0}, "answer_in_kept_hit": false, "answer_in_dropped_hit": "missing", "valuable_only_in_dropped": "missing", "dropped_hits_observed": false, "lead_then_next_gain": {"lead_rounds": 0, "next_gain_true": 0, "next_gain_false": 0, "next_gain_missing": 0}}`

  - r1: hit=1 cand=4 linked=0 usable=1 gain=True no_gain=False new_term=47 action=implement/findings_complete loss={'stage': 'candidate_linked', 'observational_label': 'LINK不足', 'count': 0, 'note': 'first False/zero along chain; not blame assignment'}

## Report questions (tendency only)

### Q1_fail_despite_web_hits

```json
{
  "fail_with_hits": 3,
  "fail_without_hits": 1,
  "note": "tendency only; n small"
}
```

### Q2_hit_vs_success_rate

```json
{
  "signal_yes|fail": 27,
  "signal_yes|next_no_gain": 18,
  "signal_yes|next_gain": 6,
  "signal_no|fail": 1,
  "signal_no|next_no_gain": 1,
  "signal_yes|success": 1
}
```

### Q3_new_source_term_then_gain

```json
{
  "new_source": {
    "signal_yes|fail": 3,
    "signal_yes|next_no_gain": 2,
    "signal_no|fail": 25,
    "signal_no|next_no_gain": 17,
    "signal_no|next_gain": 5,
    "signal_yes|next_gain": 1,
    "signal_yes|success": 1
  },
  "new_term": {
    "signal_yes|fail": 16,
    "signal_yes|next_no_gain": 11,
    "signal_no|fail": 12,
    "signal_no|next_no_gain": 8,
    "signal_yes|next_gain": 4,
    "signal_no|next_gain": 2,
    "signal_yes|success": 1
  },
  "lead_then_next_gain": [
    [
      "cpu_temperature",
      {
        "lead_rounds": 0,
        "next_gain_true": 0,
        "next_gain_false": 0,
        "next_gain_missing": 0
      }
    ],
    [
      "disk_usage",
      {
        "lead_rounds": 0,
        "next_gain_true": 0,
        "next_gain_false": 0,
        "next_gain_missing": 0
      }
    ],
    [
      "gpu_usage",
      {
        "lead_rounds": 0,
        "next_gain_true": 0,
        "next_gain_false": 0,
        "next_gain_missing": 0
      }
    ],
    [
      "gpu_vram_usage",
      {
        "lead_rounds": 0,
        "next_gain_true": 0,
        "next_gain_false": 0,
        "next_gain_missing": 0
      }
    ],
    [
      "memory_usage",
      {
        "lead_rounds": 0,
        "next_gain_true": 0,
        "next_gain_false": 0,
        "next_gain_missing": 0
      }
    ]
  ]
}
```

### Q4_candidate_without_usable

```json
{
  "round_count": 18
}
```

### Q5_success_without_link

```json
{
  "success_cases_with_link_coverage_0": 1,
  "contrast": "memory_usage may succeed without linkage"
}
```

### Q6_no_gain_after_useful_exploration

```json
{
  "cases_with_novelty_before_no_gain": 3
}
```

### Q7_first_loss_points

```json
[
  {
    "case": "cpu_temperature",
    "round": 1,
    "label": "VERIFICATION不足",
    "stage": "candidate_verified"
  },
  {
    "case": "disk_usage",
    "round": 1,
    "label": "SEARCH不足",
    "stage": "web_hit_kept"
  },
  {
    "case": "gpu_vram_usage",
    "round": 1,
    "label": "VERIFICATION不足",
    "stage": "candidate_verified"
  },
  {
    "case": "memory_usage",
    "round": 1,
    "label": "LINK不足",
    "stage": "candidate_linked"
  }
]
```

### Q8_trajectory_success_vs_fail

```json
{
  "success_avg_rounds": 1.0,
  "fail_avg_rounds": 7.0
}
```

## Answer-presence questions

### A1_failures_without_web_answer

```json
1
```

### A2_failures_with_answer_only_in_dropped

```json
0
```

### A3_lead_presence

```json
0.0
```

### A4_lead_then_additional_info

```json
[
  [
    "cpu_temperature",
    {
      "lead_rounds": 0,
      "next_gain_true": 0,
      "next_gain_false": 0,
      "next_gain_missing": 0
    }
  ],
  [
    "disk_usage",
    {
      "lead_rounds": 0,
      "next_gain_true": 0,
      "next_gain_false": 0,
      "next_gain_missing": 0
    }
  ],
  [
    "gpu_usage",
    {
      "lead_rounds": 0,
      "next_gain_true": 0,
      "next_gain_false": 0,
      "next_gain_missing": 0
    }
  ],
  [
    "gpu_vram_usage",
    {
      "lead_rounds": 0,
      "next_gain_true": 0,
      "next_gain_false": 0,
      "next_gain_missing": 0
    }
  ],
  [
    "memory_usage",
    {
      "lead_rounds": 0,
      "next_gain_true": 0,
      "next_gain_false": 0,
      "next_gain_missing": 0
    }
  ]
]
```

### A5_valuable_in_dropped

```json
{
  "direct_in_dropped": 0,
  "core_in_dropped": 0,
  "lead_in_dropped": 0,
  "dropped_observed": false,
  "note": "If dropped_hits missing on historical data, counts stay 0/missing — do not invent."
}
```

### A6_kept_valuable_but_no_usable

```json
2
```

### A7_loss_label_distribution

```json
{
  "JUDGE不足": 1,
  "PROGRESS不足": 3,
  "STAGNATION": 3,
  "VERIFICATION不足": 2,
  "PROPOSAL_FAILURE": 1,
  "LINK不足": 1,
  "success_trajectory": 1
}
```

## Human audit samples (fill human_answer_presence)

Heuristic labels are **not** ground truth. Compare before trusting `web_answer_presence_judge` (LLM).

1. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
   - url: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
   - snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter r
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

2. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Sample scripts for system administration - PowerShell
   - url: https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
   - snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static 
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

3. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
   - url: https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
   - snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows で
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

4. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: システム管理のサンプル スクリプト - PowerShell
   - url: https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
   - snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピ
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

5. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
   - url: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
   - snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter r
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

6. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Sample scripts for system administration - PowerShell
   - url: https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
   - snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static 
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

7. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
   - url: https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
   - snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows で
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

8. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: システム管理のサンプル スクリプト - PowerShell
   - url: https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
   - snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピ
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

9. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
   - url: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process
   - snippet: The output reveals that. The second pipeline shows a different way to get the owner of a process using Get-CimInstance and Invoke-CimMethod. The Win32_Process class with a filter r
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

10. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Sample scripts for system administration - PowerShell
   - url: https://learn.microsoft.com/en-us/powershell/scripting/samples/sample-scripts-for-administration
   - snippet: Working with objects How-To Guide Viewing object structure Selecting parts of objects Removing objects from the pipeline Sorting objects Creating .NET and COM objects Using static 
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

11. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: Get-Process (Microsoft.PowerShell.Management) - PowerShell
   - url: https://learn.microsoft.com/ja-jp/powershell/module/microsoft.powershell.management/get-process
   - snippet: Get-Process モジュール: Microsoft.PowerShell.Management Module ローカル コンピューターで実行されているプロセスを取得します。. 2 番目のパイプラインは、 Get-CimInstance と Invoke-CimMethodを使用してプロセスの所有者を取得する別の方法を示しています。. Windows で
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

12. [kept] case=cpu_temperature heuristic=core discard=kept
   - title: システム管理のサンプル スクリプト - PowerShell
   - url: https://learn.microsoft.com/ja-jp/powershell/scripting/samples/sample-scripts-for-administration
   - snippet: オブジェクトの操作 攻略ガイド オブジェクトの構造の表示 一部のオブジェクトの選択 パイプラインからのオブジェクトの削除 オブジェクトの並べ替え .NET オブジェクトと COM オブジェクトの作成 静的なクラスとメソッドの使用 Get-CimInstance を使った WMI オブジェクトの取得 項目を直接操作する コンピューターの管理 攻略ガイド コンピ
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

13. [kept] case=disk_usage heuristic=none discard=kept
   - title: Windows PE (WinPE)
   - url: https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
   - snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Window
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

14. [kept] case=disk_usage heuristic=none discard=kept
   - title: Windows PE (WinPE)
   - url: https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/winpe-intro
   - snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Window
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

15. [kept] case=disk_usage heuristic=none discard=kept
   - title: サーバー メモリ構成オプション - SQL Server
   - url: https://learn.microsoft.com/ja-jp/sql/database-engine/configure-windows/server-memory-server-configuration-options
   - snippet: サーバー メモリの構成オプション この記事の内容 適用対象:SQL Server SQL Server データベース エンジンのメモリ使用率は、 min server memory (MB) と max server memory (MB)の構成設定のペアによって制限されます。. Locking pages in memory might keep the 
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

16. [kept] case=disk_usage heuristic=none discard=kept
   - title: Windows PE (WinPE)
   - url: https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-intro
   - snippet: Windows PE (WinPE) Summarize this article for me In this article Windows PE (WinPE) is a small operating system used to install, deploy, and repair Windows desktop editions, Window
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

17. [kept] case=disk_usage heuristic=none discard=kept
   - title: MBR2GPT
   - url: https://learn.microsoft.com/en-us/windows/deployment/mbr-to-gpt
   - snippet: MBR2GPT.EXE Summarize this article for me In this article Important MBR. MBR2GPT.EXE converts a disk from the Master Boot Record (MBR) to the GUID Partition Table (GPT) partition s
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

18. [kept] case=disk_usage heuristic=core discard=kept
   - title: diskpart
   - url: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/diskpart
   - snippet: Parameters You can run the following commands from the Diskpart command interpreter: Command Description active Marks the disk's partition with focus, as active. add Mirrors the si
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

19. [kept] case=disk_usage heuristic=core discard=kept
   - title: Select a disk type for Azure IaaS VMs - managed disks - Azure Virtual Machines
   - url: https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types
   - snippet: Azure managed disk types Summarize this article for me In this article Applies to: ✔️ Linux VMs ✔️ Windows VMs ✔️ Flexible scale sets ✔️ Uniform scale sets Azure managed disks curr
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

20. [kept] case=disk_usage heuristic=none discard=kept
   - title: Point-in-time restore for Windows
   - url: https://learn.microsoft.com/en-us/windows/configuration/point-in-time-restore
   - snippet: Note *Reserved storage is a Windows feature that sets aside a portion of disk space for successful update installation. Configuration details are as follows: Configuration Defaults
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

21. [kept] case=disk_usage heuristic=none discard=kept
   - title: MBR2GPT
   - url: https://learn.microsoft.com/en-us/windows/deployment/mbr-to-gpt
   - snippet: MBR2GPT.EXE Summarize this article for me In this article Important MBR. MBR2GPT.EXE converts a disk from the Master Boot Record (MBR) to the GUID Partition Table (GPT) partition s
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

22. [kept] case=disk_usage heuristic=core discard=kept
   - title: diskpart
   - url: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/diskpart
   - snippet: Parameters You can run the following commands from the Diskpart command interpreter: Command Description active Marks the disk's partition with focus, as active. add Mirrors the si
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

23. [kept] case=disk_usage heuristic=core discard=kept
   - title: Select a disk type for Azure IaaS VMs - managed disks - Azure Virtual Machines
   - url: https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types
   - snippet: Azure managed disk types Summarize this article for me In this article Applies to: ✔️ Linux VMs ✔️ Windows VMs ✔️ Flexible scale sets ✔️ Uniform scale sets Azure managed disks curr
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

24. [kept] case=disk_usage heuristic=none discard=kept
   - title: Point-in-time restore for Windows
   - url: https://learn.microsoft.com/en-us/windows/configuration/point-in-time-restore
   - snippet: Note *Reserved storage is a Windows feature that sets aside a portion of disk space for successful update installation. Configuration details are as follows: Configuration Defaults
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

25. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: GPU Utilization - Microsoft Q&A
   - url: https://learn.microsoft.com/en-us/answers/questions/1696159/gpu-utilization
   - snippet: For querying GPU utilization, a more common method is to use the nvidia-smi command-line tool to view GPU utilization, temperature, memory usage, etc. For more information about NV
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

26. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: How I can allocate full GPU to a python/anaconda ? - Microsoft Q&A
   - url: https://learn.microsoft.com/en-us/answers/questions/4131160/how-i-can-allocate-full-gpu-to-a-python-anaconda
   - snippet: ..., P0, 67, 95 %, 74 %, 46068 MiB, 31550 MiB, 14241 MiB 2023/07/08 00:11:35.950, P0, 67, 91 %, 61 %, 46068 MiB, 31550 MiB, 14241 MiB C:\Users\Administrator&gt;nvidia-smi Sat Jul  
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

27. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: Linux 用の N シリーズ GPU ドライバーのセットアップをAzureする - Azure Virtual Machines
   - url: https://learn.microsoft.com/ja-jp/azure/virtual-machines/linux/n-series-driver-setup
   - snippet: NVIDIA GPU ドライバー拡張機能は、N シリーズ VM に適切な NVIDIA コンピューティング統合デバイス アーキテクチャ (CUDA) または GRID ドライバーをインストールします。. サポートされているオペレーティング システム (OS) と展開の手順については、 NVIDIA GPU ドライバー拡張機能のドキュメントを参照してください。
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

28. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: Windows用の N シリーズ NVIDIA GPU ドライバーのセットアップをAzureする - Azure Virtual Machines
   - url: https://learn.microsoft.com/ja-jp/azure/virtual-machines/windows/n-series-driver-setup
   - snippet: GRID ドライバーのインストールを確認す... nvidia-smi を実行します。. ドライバーがインストールされている場合、NVIDIA SMI は 、VM で GPU ワークロードを実行するまで GPU-Util を N/A として一覧表示します。. AzureでWindows ServerまたはWindowsを実行している N シリーズ VM 用に
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

29. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: GPU Utilization - Microsoft Q&A
   - url: https://learn.microsoft.com/en-us/answers/questions/1696159/gpu-utilization
   - snippet: For querying GPU utilization, a more common method is to use the nvidia-smi command-line tool to view GPU utilization, temperature, memory usage, etc. For more information about NV
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

30. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: How I can allocate full GPU to a python/anaconda ? - Microsoft Q&A
   - url: https://learn.microsoft.com/en-us/answers/questions/4131160/how-i-can-allocate-full-gpu-to-a-python-anaconda
   - snippet: ..., P0, 67, 95 %, 74 %, 46068 MiB, 31550 MiB, 14241 MiB 2023/07/08 00:11:35.950, P0, 67, 91 %, 61 %, 46068 MiB, 31550 MiB, 14241 MiB C:\Users\Administrator&gt;nvidia-smi Sat Jul  
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

31. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: Linux 用の N シリーズ GPU ドライバーのセットアップをAzureする - Azure Virtual Machines
   - url: https://learn.microsoft.com/ja-jp/azure/virtual-machines/linux/n-series-driver-setup
   - snippet: NVIDIA GPU ドライバー拡張機能は、N シリーズ VM に適切な NVIDIA コンピューティング統合デバイス アーキテクチャ (CUDA) または GRID ドライバーをインストールします。. サポートされているオペレーティング システム (OS) と展開の手順については、 NVIDIA GPU ドライバー拡張機能のドキュメントを参照してください。
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

32. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: Windows用の N シリーズ NVIDIA GPU ドライバーのセットアップをAzureする - Azure Virtual Machines
   - url: https://learn.microsoft.com/ja-jp/azure/virtual-machines/windows/n-series-driver-setup
   - snippet: GRID ドライバーのインストールを確認す... nvidia-smi を実行します。. ドライバーがインストールされている場合、NVIDIA SMI は 、VM で GPU ワークロードを実行するまで GPU-Util を N/A として一覧表示します。. AzureでWindows ServerまたはWindowsを実行している N シリーズ VM 用に
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

33. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: GPU Utilization - Microsoft Q&A
   - url: https://learn.microsoft.com/en-us/answers/questions/1696159/gpu-utilization
   - snippet: For querying GPU utilization, a more common method is to use the nvidia-smi command-line tool to view GPU utilization, temperature, memory usage, etc. For more information about NV
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

34. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: How I can allocate full GPU to a python/anaconda ? - Microsoft Q&A
   - url: https://learn.microsoft.com/en-us/answers/questions/4131160/how-i-can-allocate-full-gpu-to-a-python-anaconda
   - snippet: ..., P0, 67, 95 %, 74 %, 46068 MiB, 31550 MiB, 14241 MiB 2023/07/08 00:11:35.950, P0, 67, 91 %, 61 %, 46068 MiB, 31550 MiB, 14241 MiB C:\Users\Administrator&gt;nvidia-smi Sat Jul  
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

35. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: Linux 用の N シリーズ GPU ドライバーのセットアップをAzureする - Azure Virtual Machines
   - url: https://learn.microsoft.com/ja-jp/azure/virtual-machines/linux/n-series-driver-setup
   - snippet: NVIDIA GPU ドライバー拡張機能は、N シリーズ VM に適切な NVIDIA コンピューティング統合デバイス アーキテクチャ (CUDA) または GRID ドライバーをインストールします。. サポートされているオペレーティング システム (OS) と展開の手順については、 NVIDIA GPU ドライバー拡張機能のドキュメントを参照してください。
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

36. [kept] case=gpu_vram_usage heuristic=core discard=kept
   - title: Windows用の N シリーズ NVIDIA GPU ドライバーのセットアップをAzureする - Azure Virtual Machines
   - url: https://learn.microsoft.com/ja-jp/azure/virtual-machines/windows/n-series-driver-setup
   - snippet: GRID ドライバーのインストールを確認す... nvidia-smi を実行します。. ドライバーがインストールされている場合、NVIDIA SMI は 、VM で GPU ワークロードを実行するまで GPU-Util を N/A として一覧表示します。. AzureでWindows ServerまたはWindowsを実行している N シリーズ VM 用に
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

37. [kept] case=memory_usage heuristic=none discard=kept
   - title: Windows 回復環境 (Windows RE)
   - url: https://learn.microsoft.com/ja-jp/windows-hardware/manufacture/desktop/windows-recovery-environment--windows-re--technical-reference
   - snippet: Windows 回復環境 (Windows RE) この記事の内容 Windows回復環境 (WinRE) は、起動できないオペレーティング システムの一般的な原因を修復できる回復環境です。. The base WinRE... Memory requirements In order to boot Windows RE directly from mem
   - human_answer_presence: missing (fill: direct|core|lead|related|none|unknown)

## Routing readiness

- sufficient_for_routing_rules: **False**
- reason: n small; dropped_hits often missing on historical runs; heuristic answer_presence not calibrated vs human; no causal proof that continuing web would flip fail→pass.
- next_observations: ['Live KSS-1.4 runs with web_hit_partition (kept+dropped)', 'Human audit of heuristic vs human_answer_presence samples', 'Optional offline web_answer_presence_judge (LLM) agreement rate', 'More success trajectories beyond memory_usage']
- options_not_executed: {'A': 'Webを追加探索', 'B': '検索戦略を変更', 'C': 'LLMに戻す', 'D': '上位LLMへ相談', 'E': 'HELP', 'F': '終了'}

## KSS-1.5 hypotheses to test next

- H-A: valuable dropped hits (direct/core/lead) correlate with avoidable failures
- H-B: lead rounds predict next_round novelty more than raw hit counts
- H-C: verification/judge gaps dominate when kept already has core
- H-D: search-strategy change beats blind additional searches
