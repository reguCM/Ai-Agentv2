# LLM 問題解決実験用 Tool セット

このディレクトリは **FA 実装ではない**。本番 Repair / Research / Environment 経路・Registry・MATERIALS・`first_pipeline_step` には接続しない。

目的は、ローカル LLM が Failure 解決のために既存（および不足分の実験用）能力へ自分で到達できる状態を用意すること。

## 実験用 Tool セット（本番 Registry 非登録）

既存関数を呼ぶもの: `read_file`, `search_files`, `list_files`, `search_web`, `read_url_text`, `get_gpu_status`, `get_gpu_processes`, `read_git_diff`（`git_snapshot`）

実験用ラッパ / 新規: `get_current_failure`, `get_execution_environment`, `experiment_test_source`, `read_pdf`, `request_human_help`

確認: `python -m research.llm_benchmarks.problem_solving_experiment.smoke`

LLM 実験: `python -m research.llm_benchmarks.problem_solving_experiment.harness`

Problem Analysis 単体（項目列挙）: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_bench`

Problem Analysis 自由分析（項目列挙なし）: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_free_bench`

Problem Analysis 完全最小 Prompt: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_minimal_bench`

Problem Analysis モデル比較（最小 Prompt）: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_model_compare_bench`

Problem Analysis 文脈増加: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_context_bench`

Problem Analysis 切り分け（Failure/traceback/source/会話）: `python -m research.llm_benchmarks.problem_solving_experiment.problem_analysis_context_split_bench`

Problem Solving 成功事例探索（別ファイル調査連鎖）: `python -m research.llm_benchmarks.problem_solving_experiment.problem_solving_success_case_bench`

Problem Solving 調査連鎖条件: `python -m research.llm_benchmarks.problem_solving_experiment.chain_conditions_bench`

Problem Solving 実コード・実エラー: `python -m research.llm_benchmarks.problem_solving_experiment.real_code_bench`

Problem Solving Test後再判断: `python -m research.llm_benchmarks.problem_solving_experiment.rejudgment_bench`

設計資料（実装ではない）: `CURRENT_STATE.md` / `EXPERIMENT_GAP.md` / `DESIGN_OPTIONS.md` / `CHANGE_PLAN.md` / `PROTOCOL_V1.md` / `PROTOCOL_GAP.md` / `PROTOCOL_CODE_MAPPING.md` / `IMPLEMENTATION_OPTIONS.md` / `OBSERVABILITY_DESIGN.md`

観測ログ実装: `OBSERVABILITY_IMPLEMENTATION.md`
