# KSS-1.2 Calibration & Web↔Decision Link Audit

- experiment_dir: `research\llm_benchmarks\kss11_measurement\kss11_20260820_151041`
- routing_implemented: `False`
- confidence_threshold_implemented: `False`
- not_for_decision: `True`

## Verifier / Rule calibration (existing signals → progress)

### Verifier confidence label → progress_action

- `low` n=39: continue=0.974, stop=0.026
- `high` n=5: continue=0.2, implement=0.8

### Evidence level → progress_action

- `medium` n=26: continue=0.885, stop=0.115
- `high` n=2: continue=0.5, implement=0.5
- `low` n=1: continue=1.0

### Evidence level → case pass/fail

- `medium` n=26: fail=1.0
- `high` n=2: fail=0.5, pass=0.5
- `low` n=1: fail=1.0

### Round had verify ok → progress_action

- `False` n=27: continue=0.889, stop=0.111
- `True` n=2: continue=0.5, implement=0.5

### Judge satisfies → progress_action

- `False` n=28: continue=0.893, stop=0.107
- `True` n=1: implement=1.0

### no_gain → progress_action

- `True` n=17: continue=0.882, stop=0.118
- `False` n=12: continue=0.833, stop=0.083, implement=0.083

## Web evidence ↔ decision linkage audit

- rounds_total: 29
- rounds_with_hits: 28
- candidates_total (verified_runs / keys linked): 44
- candidates_linked (token_overlap>0): 26
- link_coverage: 0.591
- hit_score_present_saved (KSS-1.1): 0
- hit_score_missing_saved (KSS-1.1): 175
- hit_score_computed_retro: 175
- audit_gaps: `{"none": 25, "no_web_hits_in_round": 1, "zero_candidate_hit_token_overlap": 4}`
- overlap_hist: `{"1": 20, "2": 5, "0": 18, "6+": 1}`

> Saved KSS-1.1 runs omit hit.score on web_hits; retroactive audit recomputes existing hit_score and token-overlap links to verified_runs (observational only).

## Code linkage (static)

- `web_search_produces_hits`: `True`
- `hit_score_exists`: `True`
- `hit_score_path`: `tools/system/tool_builder/research/web.py:hit_score`
- `hits_reach_candidate_prompt`: `True`
- `candidate_json_has_hit_url_field`: `False`
- `verifier_reads_hit_score`: `False`
- `progress_reads_hit_score`: `False`
- `round_details_web_hits_include_score_before_kss12`: `False`
- `linkage_before_kss12`: `missing`
- `linkage_after_kss12_obs`: `token_overlap_observational_only`
- `routing_on_web_score`: `False`
- `env_flag`: `AI_AGENT_KSS12_OBS (also inherits AI_AGENT_KSS11_OBS)`

## Recommendations (no thresholds yet)

1. Treat existing verifier `high/low` + progress rule as the primary calibration spine.
2. Do **not** introduce routing or confidence cutoffs until link_coverage and label→outcome tables stabilize across more trials.
3. For future live runs, enable `AI_AGENT_KSS12_OBS` so `web_hits[].score` and candidate↔hit links are stored (behavior unchanged).
4. Hard FK (`candidate.hit_url`) remains optional; only add if overlap audit stays weak.
