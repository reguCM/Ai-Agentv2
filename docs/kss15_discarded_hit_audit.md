# KSS-1.5 — Live discarded-hit measurement & human audit

## Absolute: observation-only

No retry, Web force, confidence thresholds, HELP/上位LLM routing, filter/candidate/verifier/judge changes.

## Live partition fields

Per hit (missing if unavailable):

`search_id`, `round_id`, `query`, `hit_id`, `url`, `title`, `source/domain`, `kept`, `drop_reason`, `position_rank`, `existing_hit_score`, `candidate_link`

Stored on `web_hit_partition` via executor `evidence.obs_hit_partition` (filter outcomes unchanged).

## Human audit

- `human_audit_dataset.json` — machine-readable labels to fill
- `human_audit_worksheet.md` — human-readable worksheet

Labels: `direct|core|lead|related|none|unknown` (+ 1-line rationale).

LLM Judge deferred until enough human labels (`AI_AGENT_KSS14_ANSWER_JUDGE` remains OFF).

## Historical data

If dropped absent: `dropped_* = missing` (never 0/none by invention).

## Run

```bash
python research/benchmarks/kss/_kss15_measurement_bench.py --cases memory_usage,cpu_temperature,disk_usage,gpu_usage,gpu_vram_usage
```

Outputs under `research/llm_benchmarks/knowledge_source_obs/kss15_*/`.
