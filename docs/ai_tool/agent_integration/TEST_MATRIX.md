# Test Matrix — Agent Discovery Phase 1

**テスト:** `tests/ai_tool/agent_integration/test_discovery.py`  
**結果:** 14 passed（2026-08-28）

| # | カテゴリ | テスト | 確認内容 |
|---|----------|--------|----------|
| 1 | Production | test_production_tools_discovered | gpu/cpu/read_file が discovery 可能 |
| 2 | Production | test_production_agent_available | get_gpu_status: agent_available=true, production |
| 3 | Production | test_production_registry_consistency | cpu_status が Registry descriptor と一致 |
| 4 | Experimental | test_experimental_scoped_read_discovered | scoped read: agent_available=false |
| 5 | Experimental | test_experimental_read_url_discovered | read_url: experimental |
| 6 | Status | test_experimental_three_layer_status_preserved | unavailable/experimental/not_reviewed 保持 |
| 7 | Status | test_status_layers_not_collapsed | catalog_status ≠ discovery_category |
| 8 | Unknown | test_unknown_tool_not_fabricated | 未知 ID → None |
| 9 | Unknown | test_unknown_tool_id_no_crash | 全 entry に tool_id |
| 10 | Determinism | test_deterministic_discovery | 同一入力 → 同一出力 |
| 11 | Safety | test_discovery_does_not_import_experimental_executors | 実行関数未呼び出し |
| 12 | not_ready | test_pipeline_tools_not_agent_available | pipeline Tool: not_ready |
| 13 | Comparison | test_comparison_table_representatives | 5 Tool 表 |
| 14 | MCP | test_mcp_manual_catalog_experimental | mcp:get_current_time experimental |

## Phase 2 — Hook (`test_hook.py`)

| # | カテゴリ | テスト | 確認 |
|---|----------|--------|------|
| 15 | Production | test_hook_production_tools_agent_available | hook 経由 production |
| 16 | Experimental | test_hook_experimental_* | scoped/read_url false |
| 17 | Status | test_hook_status_preservation | 三層保持 |
| 18 | Safety | test_hook_execution_count_zero | execution_count=0 |
| 19 | Safety | test_safe_hook_survives_adapter_failure | fail-safe |
| 20 | Determinism | test_hook_deterministic | 同一出力 |

**合計:** 47 passed（Phase 1 + Phase 2 + Phase 3 + Phase 4）

## Phase 3 — Human Review (`test_human_review.py`)

| # | カテゴリ | テスト | 確認 |
|---|----------|--------|------|
| 21 | Review | test_unreviewed_tool_can_be_loaded | 未レビュー Tool 取得 |
| 22 | Review | test_record_approved | approved 記録 + 三層 preservation |
| 23 | Review | test_record_rejected | rejected → unavailable preview |
| 24 | Review | test_record_deferred | deferred → adoption 不変 |
| 25 | Review | test_rereview_* | 再レビュー / block |
| 26 | Agent | test_approved_still_not_agent_available | approved 後も false |
| 27 | Registry | test_registry_unchanged_by_review | registry SHA 不変 |
| 28 | LLM | test_ollama_schema_unchanged_by_review | Ollama schema 不変 |
| 29 | Safety | test_review_does_not_execute_tools | 実行 0 |
| 30 | Determinism | test_discovery_deterministic_after_review | 同一 discovery |
| 31 | Unknown | test_unknown_tool_not_found | 捏造なし |

## Phase 4 — Experimental Trial (`test_trial.py`)

| # | カテゴリ | テスト | 確認 |
|---|----------|--------|------|
| 32 | Exposure | test_trial_exposes_read_url_text_and_search_web | trial schema overlay |
| 33 | Discovery | test_production_discovery_still_not_agent_available | agent_available=false |
| 34 | Routing | test_url_scenario_selects_read_url_text | URL → read_url_text |
| 35 | Routing | test_search_scenario_selects_search_web | 探索 → search_web |
| 36 | Loop | test_result_used_in_follow_up_message | tool result → messages |
| 37 | Safety | test_registry_unchanged_after_trial | registry SHA 不変 |
| 38 | Safety | test_production_ollama_schema_unchanged | 本番 schema 不変 |
| 39 | Trial | test_trial_execution_count_nonzero | 実行 ≥2 |
| 40 | Docs | test_routing_comparison_documented | 使い分け定義 |
| 41 | Unknown | test_execute_unknown_tool_fails | 捏造なし |

- agent.py 本番 path 未変更（trial は isolated runner のみ）
- LLM schema 本番 7 Tool 不変（trial overlay は runner 内のみ）
