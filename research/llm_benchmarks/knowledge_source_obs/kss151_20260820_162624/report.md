# KSS-1.5.1 Human Audit Ground Truth

- experiment_id: see summary.json
- source_experiment: `kss15_20260820_160911` (immutable)
- human_audit_status: **pending**
- routing_ready: **false**

## Frozen KSS-1.5 observation (not rewritten)

```json
{
  "cases_total": 5,
  "cases_completed": 5,
  "cases_failed": 4,
  "cases_valid_for_measurement": 4,
  "searches_observed": 46,
  "hits_observed": 192,
  "kept_hits": 183,
  "dropped_hits": 9,
  "successful_runs": 1,
  "failed_runs": 3,
  "dropped_with_core": 7,
  "dropped_with_direct": 0,
  "dropped_with_lead": 0,
  "failed_runs_with_answer_in_dropped": 1,
  "failed_runs_with_answer_in_kept": 3,
  "failed_runs_with_no_answer_found": 0,
  "heuristic_dropped_answer_rate_observed": 0.778,
  "note": "heuristic_dropped_answer_rate is NOT ground truth; do not treat 0.778 as confirmed precision"
}
```

> Do **not** treat `heuristic_dropped_answer_rate_observed` as confirmed precision.

## Audit scope

- Dropped hits to audit: **9** (all)
- Failed kept (heuristic core/direct, unique URL): **12**
- Failure loss-stage forms: **4**

## A. Dropped audit (pending)

- dropped_total: 9
- human_direct/core/related/none/misleading/unknown: **missing** until labeled

## B. Kept audit (pending)

- kept_audited (planned): 12
- human counts: **missing** until labeled

## C. Failure loss stage (pending)

- All stages: **missing** until case forms filled

## D. Heuristic calibration (pending)

- confusion matrix / precision / FPR / FNR: **missing**
- When computed: report as *observed sample / small-n / human-audit estimate* only

## Non-goals (explicit)

- No Web retry / force / search-count change
- No confidence thresholds / HELP / 上位LLM routing
- No Phase 5.1 formalize
- No proving 'lead → continue search' yet (needs trajectory accumulation → KSS-1.6)

## Next

1. Fill `human_audit_worksheet.md` / `ground_truth_template.json`
2. Apply labels → regenerate report counts
3. KSS-1.6: compare SEARCH/DROP/VERIFY/JUDGE/PROGRESS improvement options
