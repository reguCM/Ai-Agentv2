# KSS-1.3 Exploration Value Observation Report

- experiment_dir: `D:\AI-Agent\research\llm_benchmarks\knowledge_source_obs\kss13_20260820_154524`
- cases: 5 (success=1, fail=4)
- routing_implemented: `False`
- confidence_threshold_implemented: `False`
- not_for_decision: `True`

## 1. Round-level exploration snapshots

### cpu_temperature — pass=False rounds=10 stop=max_research_rounds path={'labels': ['E_promising_web_unused_by_judge_proxy'], 'notes': ['proxy: medium/high evidence_level or hits but never implement (judge/LLM utilization gap not proven)']}

- r1: kept=5 search_raw=missing new_src=1 new_term=102 cand=2 link=1.0 zero_ov=0 no_gain=False action=continue/no_progress
- r2: kept=5 search_raw=missing new_src=0 new_term=0 cand=1 link=1.0 zero_ov=0 no_gain=False action=continue/new_information
- r3: kept=8 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=True action=continue/no_progress
- r4: kept=8 search_raw=missing new_src=0 new_term=1 cand=1 link=1.0 zero_ov=0 no_gain=True action=continue/no_progress
- r5: kept=8 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=True action=continue/new_information
- r6: kept=5 search_raw=missing new_src=0 new_term=8 cand=3 link=1.0 zero_ov=0 no_gain=True action=continue/no_progress
- r7: kept=5 search_raw=missing new_src=0 new_term=2 cand=1 link=1.0 zero_ov=0 no_gain=True action=continue/no_progress
- r8: kept=5 search_raw=missing new_src=0 new_term=0 cand=1 link=1.0 zero_ov=0 no_gain=False action=continue/new_information
- r9: kept=5 search_raw=missing new_src=0 new_term=4 cand=1 link=1.0 zero_ov=0 no_gain=False action=continue/new_information
- r10: kept=5 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=False action=stop/max_research_rounds

### disk_usage — pass=False rounds=8 stop=stagnation path={'labels': ['D_candidates_without_core_usable', 'E_promising_web_unused_by_judge_proxy'], 'notes': ['candidates generated but no usable/implement', 'proxy: medium/high evidence_level or hits but never implement (judge/LLM utilization gap not proven)']}

- r1: kept=0 search_raw=missing new_src=0 new_term=7 cand=4 link=0.0 zero_ov=4 no_gain=False action=continue/no_progress
- r2: kept=5 search_raw=missing new_src=1 new_term=78 cand=4 link=0.5 zero_ov=2 no_gain=False action=continue/new_information
- r3: kept=8 search_raw=missing new_src=0 new_term=122 cand=3 link=1.0 zero_ov=0 no_gain=True action=continue/no_progress
- r4: kept=8 search_raw=missing new_src=0 new_term=0 cand=1 link=1.0 zero_ov=0 no_gain=True action=continue/no_progress
- r5: kept=8 search_raw=missing new_src=0 new_term=8 cand=3 link=0.667 zero_ov=1 no_gain=True action=continue/new_information
- r6: kept=5 search_raw=missing new_src=0 new_term=5 cand=4 link=0.5 zero_ov=2 no_gain=False action=continue/no_progress
- r7: kept=5 search_raw=missing new_src=0 new_term=2 cand=3 link=0.667 zero_ov=1 no_gain=True action=continue/no_progress
- r8: kept=5 search_raw=missing new_src=0 new_term=2 cand=1 link=1.0 zero_ov=0 no_gain=True action=stop/stagnation

### gpu_usage — pass=False rounds=0 stop=None path={'labels': ['no_rounds'], 'notes': ['zero research rounds']}


### gpu_vram_usage — pass=False rounds=10 stop=max_research_rounds path={'labels': ['C_hits_but_weak_candidate_link', 'D_candidates_without_core_usable', 'E_promising_web_unused_by_judge_proxy'], 'notes': ['kept hits present but candidate↔hit linkage weak', 'candidates generated but no usable/implement', 'proxy: medium/high evidence_level or hits but never implement (judge/LLM utilization gap not proven)']}

- r1: kept=5 search_raw=missing new_src=1 new_term=107 cand=2 link=1.0 zero_ov=0 no_gain=False action=continue/no_progress
- r2: kept=8 search_raw=missing new_src=0 new_term=5 cand=2 link=0.0 zero_ov=2 no_gain=False action=continue/new_information
- r3: kept=8 search_raw=missing new_src=0 new_term=4 cand=2 link=0.0 zero_ov=2 no_gain=False action=continue/no_progress
- r4: kept=8 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=True action=continue/no_progress
- r5: kept=8 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=True action=continue/new_information
- r6: kept=8 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=True action=continue/no_progress
- r7: kept=8 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=True action=continue/no_progress
- r8: kept=8 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=True action=continue/new_information
- r9: kept=5 search_raw=missing new_src=0 new_term=1 cand=1 link=1.0 zero_ov=0 no_gain=True action=continue/no_progress
- r10: kept=5 search_raw=missing new_src=0 new_term=0 cand=0 link=None zero_ov=0 no_gain=True action=stop/max_research_rounds

### memory_usage — pass=True rounds=1 stop=findings_complete path={'labels': ['C_hits_but_weak_candidate_link'], 'notes': ['kept hits present but candidate↔hit linkage weak']}

- r1: kept=1 search_raw=missing new_src=1 new_term=47 cand=4 link=0.0 zero_ov=4 no_gain=False action=implement/findings_complete

## 2. Success vs failure comparison

> n is small; treat as tendency only, not established relation

### success

- `search_result_count`: n=0 avg=None min=None max=None median=None
- `kept_hit_count`: n=1 avg=1.0 min=1.0 max=1.0 median=1.0
- `new_source_count`: n=1 avg=1.0 min=1.0 max=1.0 median=1.0
- `new_term_count`: n=1 avg=47.0 min=47.0 max=47.0 median=47.0
- `new_url_count`: n=1 avg=1.0 min=1.0 max=1.0 median=1.0
- `candidate_count`: n=1 avg=4.0 min=4.0 max=4.0 median=4.0
- `link_coverage`: n=1 avg=0.0 min=0.0 max=0.0 median=0.0
- `zero_overlap_count`: n=1 avg=4.0 min=4.0 max=4.0 median=4.0
- `no_gain`: n=1 avg=0.0 min=0.0 max=0.0 median=0.0
- `information_gain`: n=1 avg=1.0 min=1.0 max=1.0 median=1.0
- `rounds_per_case`: n=1 avg=1.0 min=1.0 max=1.0 median=1.0

### failure

- `search_result_count`: n=0 avg=None min=None max=None median=None
- `kept_hit_count`: n=28 avg=6.214 min=0.0 max=8.0 median=5.0
- `new_source_count`: n=28 avg=0.107 min=0.0 max=1.0 median=0.0
- `new_term_count`: n=28 avg=16.357 min=0.0 max=122.0 median=1.5
- `new_url_count`: n=28 avg=0.607 min=0.0 max=5.0 median=0.0
- `candidate_count`: n=28 avg=1.429 min=0.0 max=4.0 median=1.0
- `link_coverage`: n=19 avg=0.754 min=0.0 max=1.0 median=1.0
- `zero_overlap_count`: n=28 avg=0.5 min=0.0 max=4.0 median=0.0
- `no_gain`: n=28 avg=0.607 min=0.0 max=1.0 median=1.0
- `information_gain`: n=28 avg=0.214 min=0.0 max=1.0 median=0.0
- `rounds_per_case`: n=4 avg=7.0 min=0.0 max=10.0 median=9.0

## 3. information_gain / no_gain relationship

Existing `no_gain` / `information_gain` are copied as `no_gain_existing` / `information_gain_existing` (meaning unchanged).

- cpu_temperature: no_gain sequence=[False, False, True, True, True, True, True, False, False, False]
- disk_usage: no_gain sequence=[False, False, True, True, True, False, True, True]
- gpu_usage: no_gain sequence=[]
- gpu_vram_usage: no_gain sequence=[False, False, False, True, True, True, True, True, True, True]
- memory_usage: no_gain sequence=[False]

## 4. Web hit ↔ candidate linkage

Uses KSS-1.2 token-overlap links (or retro). No hard FK `candidate.hit_url`.

- cpu_temperature: (round, link_coverage, zero_overlap)=[(1, 1.0, 0), (2, 1.0, 0), (3, None, 0), (4, 1.0, 0), (5, None, 0), (6, 1.0, 0), (7, 1.0, 0), (8, 1.0, 0), (9, 1.0, 0), (10, None, 0)]
- disk_usage: (round, link_coverage, zero_overlap)=[(1, 0.0, 4), (2, 0.5, 2), (3, 1.0, 0), (4, 1.0, 0), (5, 0.667, 1), (6, 0.5, 2), (7, 0.667, 1), (8, 1.0, 0)]
- gpu_usage: (round, link_coverage, zero_overlap)=[]
- gpu_vram_usage: (round, link_coverage, zero_overlap)=[(1, 1.0, 0), (2, 0.0, 2), (3, 0.0, 2), (4, None, 0), (5, None, 0), (6, None, 0), (7, None, 0), (8, None, 0), (9, 1.0, 0), (10, None, 0)]
- memory_usage: (round, link_coverage, zero_overlap)=[(1, 0.0, 4)]

## 5. Path to stagnation (A–E)

- **cpu_temperature**: ['E_promising_web_unused_by_judge_proxy'] — ['proxy: medium/high evidence_level or hits but never implement (judge/LLM utilization gap not proven)']
- **disk_usage**: ['D_candidates_without_core_usable', 'E_promising_web_unused_by_judge_proxy'] — ['candidates generated but no usable/implement', 'proxy: medium/high evidence_level or hits but never implement (judge/LLM utilization gap not proven)']
- **gpu_usage**: ['no_rounds'] — ['zero research rounds']
- **gpu_vram_usage**: ['C_hits_but_weak_candidate_link', 'D_candidates_without_core_usable', 'E_promising_web_unused_by_judge_proxy'] — ['kept hits present but candidate↔hit linkage weak', 'candidates generated but no usable/implement', 'proxy: medium/high evidence_level or hits but never implement (judge/LLM utilization gap not proven)']
- **memory_usage**: ['C_hits_but_weak_candidate_link'] — ['kept hits present but candidate↔hit linkage weak']

## 6. Hypotheses (provisional)

### H1_external_research_value_when_llm_hard

```json
{
  "status": "observational_only",
  "note": "Requires cases labeled LLM-hard; proxy=fail with many rounds. Not established.",
  "fail_cases_with_rounds_ge_5": 3,
  "established": false
}
```

### H2_exploration_leads_predict_later_success

```json
{
  "lead_round_in_success_runs": 0,
  "lead_round_in_fail_runs": 15,
  "established": false,
  "note": "counts are co-occurrence not causal; sample limited"
}
```

### H3_continue_while_novelty_arrives

```json
{
  "status": "supports_trend",
  "success_avg": 47.0,
  "fail_avg": 16.357,
  "established": false,
  "note": "sample_small"
}
```

### H4_no_gain_streak_lowers_value

```json
{
  "status": "supports_trend",
  "success_avg": 0.0,
  "fail_avg": 0.607,
  "established": false,
  "note": "sample_small"
}
```

### H5_novelty_and_linkage_beat_hit_count

```json
{
  "kept_hit_count": {
    "status": "opposes_trend",
    "success_avg": 1.0,
    "fail_avg": 6.214,
    "established": false,
    "note": "sample_small"
  },
  "new_source_count": {
    "status": "supports_trend",
    "success_avg": 1.0,
    "fail_avg": 0.107,
    "established": false,
    "note": "sample_small"
  },
  "new_term_count": {
    "status": "supports_trend",
    "success_avg": 47.0,
    "fail_avg": 16.357,
    "established": false,
    "note": "sample_small"
  },
  "link_coverage": {
    "status": "opposes_trend",
    "success_avg": 0.0,
    "fail_avg": 0.754,
    "established": false,
    "note": "sample_small"
  },
  "established": false,
  "note": "compare which metric separates success/fail more; n small"
}
```

## 7. Sample insufficiency / missing fields

- common missing: `['search_result_count (offline / no web_exec)', 'new_entity_count', 'exploration_value_score (intentionally not created)', 'semantic_novelty']`
- case_count=5 → no established statistical claims

## 8. Next-step proposals (still observation / no routing)

1. Collect more trials with `AI_AGENT_KSS13_OBS=1` so `search_result_count` (web_exec) is live, not missing.
2. Correlate `has_new_source/term` streaks with `next_round_gain` / eventual pass — still no threshold.
3. Only after stable tables: consider `expected_next_search_value` model — not now.
4. Do not add fixed search counts, Web force, or confidence routing.
