# KSS-1.3 — Available vs Missing fields

Observation-only. No routing / confidence thresholds / Web force.

## Research round boundary (reuse existing)

| Stage | Timing | Artifact |
|---|---|---|
| search + hit filter | `run_research` / executor | hits, dropped_count (on web_exec) |
| candidate generation | after LLM candidate JSON | `candidates`, filter stats |
| verification | `research_verifier` | `verified` |
| judge | GJ / LLM | `judgment` |
| progress | `evaluate_research_progress` | action / stagnation |
| information_gain / no_gain | KSS-0 ← `assess_information_gain` | `known_coverage.no_gain` |

No new History Store. Attached to `round_details[].exploration_value_observation`.

## AVAILABLE (mechanical)

| Field | Source |
|---|---|
| `round_index` | loop counter |
| `kept_hit_count` | `len(web_hits)` / web_exec kept |
| `candidate_count` | filter after / verified |
| `candidate_to_hit_link_count` / `link_coverage` | KSS-1.2 |
| `zero_overlap_count` | KSS-1.2 unlinked |
| `new_url_count` / `new_source_count` / `new_term_count` | set-diff vs prior rounds |
| `new_reference_count` | reference_findings fingerprint set-diff |
| `new_information_count` | `progress.new_keys` length when present |
| `duplicate_or_repeated_*` | `progress.duplicate_only` + URL/term ∩ prior |
| `information_gain_existing` / `no_gain_existing` | KSS-0 / KSS-1.1 copy |
| `previous_round_similarity` | token/url Jaccard only |
| `evidence_level` | KSS-1.1 |
| `search_result_count` | **live only** via `web_exec` kept+dropped |

## ALWAYS MISSING (do not invent)

| Field | Why |
|---|---|
| `new_entity_count` | no NER |
| `exploration_value` composite score | intentionally not created |
| `semantic_novelty` | no embedding / LLM self-report for novelty |
| `search_result_count` on offline rebuild | web_exec not in saved JSON |

## Env

`AI_AGENT_KSS13_OBS=1` (inherits KSS12/KSS11 when unset).
