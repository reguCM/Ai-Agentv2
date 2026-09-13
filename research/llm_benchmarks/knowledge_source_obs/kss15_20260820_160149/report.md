# KSS-1.5 Discarded Web Hit Live Audit

- experiment_id: `kss15_20260820_160149`
- routing_implemented: False
- label_source: `heuristic_pending_human_audit`
- human_labels_filled: 0

## Required counts

- total_searches: missing
- total_hits: 0
- kept_hits: 0
- dropped_hits: missing
- failed_runs: 0
- successful_runs: 0
- kept_with_direct: 0
- kept_with_core: 0
- kept_with_lead: 0
- dropped_with_direct: 0
- dropped_with_core: 0
- dropped_with_lead: 0
- dropped_answer_presence_unknown: 0
- failed_runs_with_answer_in_dropped: 0
- failed_runs_with_answer_in_kept: 0
- failed_runs_with_no_answer_found: 0

- four_group_counts: `{}`
- dropped_answer_rate: missing
- failed_runs_with_recoverable_dropped_info: 0

## drop_reason × answer_presence

```json
{}
```

## Lead continuation (observational)

```json
{
  "cases_with_lead": 0,
  "lead_then_success": 0,
  "lead_then_fail": 0,
  "no_lead_success": 0,
  "no_lead_fail": 0,
  "tracks": [],
  "note": "counts only; do not claim causation"
}
```

## Questions (tendency only; n small)

### Q1_failures_without_web_answer

failed_runs_with_no_answer_found=0 (only when dropped observed; else not claimed)

### Q2_failures_with_answer_in_dropped

count=0 (heuristic until human labels; not causal)

### Q3_kept_then_lost_downstream

failed_runs_with_answer_in_kept=0

### Q4_lead_useful_for_later_research

{'cases_with_lead': 0, 'lead_then_success': 0, 'lead_then_fail': 0, 'no_lead_success': 0, 'no_lead_fail': 0, 'tracks': [], 'note': 'counts only; do not claim causation'}

### Q5_dropped_valuable_rate

missing

### Q6_drop_reason_differences

{}

### Q7_success_vs_fail_web_handling

{}

### Q8_human_vs_llm_agreement

{'status': 'deferred_until_human_labels', 'agreement_rate': 'missing'}

## Human audit dataset

- entries: 0
- buckets: `{}`
- files: `human_audit_dataset.json`, `human_audit_worksheet.md`

## LLM Judge

`{"status": "deferred_until_human_labels", "agreement_rate": "missing"}`

## Routing readiness

- sufficient: **False**
- reason: Need filled human labels + more trials; heuristic-only rates are provisional; no routing.

## Unobserved / missing

- human_answer_presence (until worksheet filled)
- llm_human_agreement (deferred)
- full page text beyond snippet
- causal attribution
