# KSS-1.4 — Information loss & discarded-hit answer presence

## Observation-only

No routing, `should_continue_web`, confidence thresholds, Web force, or HELP.

## Modules

| File | Role |
|---|---|
| `tools/ai/state/information_loss.py` | chain + first_loss + run labels |
| `tools/ai/state/web_answer_presence.py` | kept/dropped partition + answer_presence heuristic |
| `research/llm_benchmarks/kss14_analyze.py` | trajectories + questions |
| `research/benchmarks/kss/_kss14_measurement_bench.py` | offline rebuild bench |

## answer_presence labels

`direct` | `core` | `lead` | `related` | `none` | `unknown`

- Judge family: `web_answer_presence` (not `llm_self_confidence`)
- Default method: `web_answer_presence_heuristic`
- Optional LLM: `AI_AGENT_KSS14_ANSWER_JUDGE=1` (still not for routing)
- `unknown` ≠ `none`

## Historical data gap

Saved KSS-1.1/1.3 runs store kept `web_hits` only → `dropped_hits = missing`.
Live runs with KSS-1.4 obs store `web_hit_partition` from `web_exec` (dropped truncated to executor `[:5]`).

## Env

`AI_AGENT_KSS14_OBS=1` (inherits KSS13/11 when unset).
