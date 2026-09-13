# KSS-1.1 Decision Evidence Schema & Mapping

## Purpose

既存パイプラインが OK/NG/継続/停止を決めるときに使う根拠を観測する。
LLM 自己申告 confidence は正式な信頼度にしない（KSS-1 で coverage=0 を確認済み）。

## Decision source taxonomy

| Label | Meaning |
|---|---|
| `verifier` | subprocess 成否 → confidence high/low |
| `deterministic_rule` | progress / escalation / filter / split_findings |
| `llm_judgment` | research judge JSON |
| `mixed` | live_skip + LLM、proposal validation + LLM retry |
| `missing` | HELP 等、経路未実装 |

## Existing → observation mapping

| Existing | Observation field |
|---|---|
| `results[].confidence` high/low | `verify_confidence_label` / counts |
| usable/reference/unresolved | `finding_bucket_counts` |
| `evaluate_research_progress` | `progress_action` / `progress_reason` / stagnation flags |
| `judgment.satisfies_request` | `judge_satisfies_request` |
| live_skip / LLM | `judge_source` |
| `gj_trigger.*` | `gj_needed` / `gj_would_skip` / triggers |
| `escalation.*` | `escalation_reason` / routine |
| `filter_rejected` | `candidates_rejected_count` |
| web hits | `web_kept_count` / `web_hit_scores` (score missing if absent) |
| proposal validate | `proposal_spec_status` / `proposal_completeness_ok` |
| `no_gain` (Phase 5.1 / KSS-0) | `no_gain` |
| numeric verify confidence | **missing** |
| HELP decision | **missing** |
| composite web/decision confidence | **not created** |

KSS-1.2 note: when obs is on, missing `hit.score` may be filled by the existing `hit_score()` function for observation only. Candidate↔hit links are token-overlap observational; see `docs/kss12_calibration.md`.

## Evidence level (label-only)

Derived only from existing signals:

- `high`: verify high or usable_count > 0
- `medium`: reference or web_kept > 0
- `low`: verify low / unresolved only
- `missing`: none of the above

## Env

`AI_AGENT_KSS11_OBS=1` — observation on, no behavior change.

## Non-goals

No routing, HELP, Web force, Phase 5.1 formalize, headroom change, inventing missing scores.
