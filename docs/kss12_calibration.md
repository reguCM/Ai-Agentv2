# KSS-1.2 — Verifier/Rule Calibration & Web↔Decision Link Audit

## Purpose

1. Build **calibration tables** from existing Verifier / Rule signals → `progress_action` / case pass.
2. Audit **Web evidence ↔ decision** linkage gaps (no hard FK from candidate → hit).
3. Do **not** implement routing or confidence thresholds.

## Inputs

Primary offline source: KSS-1.1 measurement dir  
`research/llm_benchmarks/kss11_measurement/kss11_20260820_151041/`

## Outputs

- `research/llm_benchmarks/kss12_calibration.py`
- Example run: `research/llm_benchmarks/kss12_calibration/kss12_20260820_offline/`
  - `kss12_calibration.json`
  - `kss12_report.md`

## Live observation (behavior unchanged)

| Piece | Role |
|---|---|
| `tools/ai/state/web_decision_link.py` | token-overlap candidate↔hit + `hit_score` annotate |
| `environment_benchmark._web_hits_for_obs` | store `web_hits[].score` when obs ON |
| `decision_evidence.collect_web_evidence` | recompute score via existing `hit_score` if absent |

Env: `AI_AGENT_KSS12_OBS=1` (inherits `AI_AGENT_KSS11_OBS` when unset).

## Key findings (offline on KSS-1.1)

- Verifier `high` → `implement` rate **0.8** (n=5); `low` → almost always `continue`.
- Saved runs had **0** `hit.score` fields; retro audit recomputed all scores.
- Token-overlap link_coverage ≈ **0.59**; hard `candidate.hit_url` still absent.
- **No thresholds / routing** introduced.

## Non-goals

Routing, confidence cutoffs, HELP, Web force, Phase 5.1 formalize, inventing missing numerics.
