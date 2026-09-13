# KSS-1.5 Discarded Web Hit Live Audit

- experiment_id: `kss15_20260820_160911`
- measurement_ok: `True`
- measurement_invalid: `False`
- python_executable: `D:\AI-Agent\.venv\Scripts\python.exe`
- python_version: `3.14.7 (tags/v3.14.7:823f032, Aug  5 2026, 10:51:32) [MSC v.1944 64 bit (AMD64)]`
- ollama_available: `True`
- ollama_file: `D:\AI-Agent\.venv\Lib\site-packages\ollama\__init__.py`
- invalid_run_count: `1`
- label_source: `heuristic_pending_human_audit`

## Required counts

- cases_total: 5
- cases_completed: 5
- cases_failed: 4
- cases_valid_for_measurement: 4
- searches_observed: 46
- hits_observed: 192
- total_searches: 46
- total_hits: 192
- kept_hits: 183
- dropped_hits: 9
- failed_runs: 3
- successful_runs: 1
- kept_with_direct: 0
- kept_with_core: 141
- kept_with_lead: 0
- dropped_with_direct: 0
- dropped_with_core: 7
- dropped_with_lead: 0
- dropped_answer_presence_unknown: 0
- failed_runs_with_answer_in_dropped: 1
- failed_runs_with_answer_in_kept: 3
- failed_runs_with_no_answer_found: 0

- four_group_counts: `{"kept_no_answer": 42, "dropped_answer": 7, "kept_answer": 141, "dropped_no_answer": 2}`
- dropped_answer_rate: 0.778

## drop_reason × answer_presence

```json
{
  "irrelevant_token:dev drive|core": 5,
  "not_relevant_low_score|related": 2,
  "not_relevant_low_score|core": 2
}
```

## Lead continuation

```json
{
  "cases_with_lead": 0,
  "lead_then_success": 0,
  "lead_then_fail": 0,
  "no_lead_success": 1,
  "no_lead_fail": 3,
  "tracks": [],
  "note": "counts only; do not claim causation"
}
```

## Notes on dropped_hits

- `dropped_hits = 0` ≠ no answers in dropped (none were dropped).
- `dropped_hits = missing` ≠ zero; partition not observed.
- `live_search_executed = false` is a separate invalid/incomplete state.

## Human audit

- entries: 69
- buckets: `{"kept_other": 30, "B_success_dropped": 1, "D_failed_kept_answerish": 30, "A_failed_dropped": 8}`

- routing_ready: False — Need filled human labels + more trials; no routing.
