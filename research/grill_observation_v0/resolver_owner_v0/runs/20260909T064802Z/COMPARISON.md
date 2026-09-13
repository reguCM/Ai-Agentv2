# resolver_owner_v0 比較（研究ラベルのみ）

run_id: `20260909T064802Z`
model: `qwen3:14b`
Production 未変更。Router 未実装。ラベルは研究観察のみ。

| Case | Goal 要約 | Grill | System First | Retry | Tool / next_action | 分類 |
|---|---|---|---|---|---|---|
| Case 1 | registry/tools.json を読んで、内容を確認してほしい。 | no | executable_action | — | read_file {'path': 'registry/tools.json'} | SYSTEM_RESOLVABLE |
| Case 2 | gridを検索して、その内容を要約してほしい。 | yes | no_required_capability | executable_action | search_files {'query': 'ID', 'path': '.'} | AI_RESOLVABLE |
| Case 3 | 来週の人間レビュー資料は、詳細な技術解説を優先するか、結論だけ短くまとめた報告を… | yes | tool_selected_arguments_incomplete | tool_selected_arguments_incomplete | — | HUMAN_REQUIRED |

## Case 4

NOT_AVAILABLE（実行していない）。

Canonical Index で tools[] が空の Capability は存在する (workspace_file_write / command_execution / python_execution / test_execution / tool_validation / tool_registration)。しかし現行 required_capabilities は Registry keyword 逆引きのため、空 tools[] の Capability へ自然言語リクエストを束縛できない。pytestを実行する / Pythonを実行して / コマンドを実行して 等の実測は no_required_capability であり、必要能力が System 上で明確になっていない。推測で SYSTEM_GAP ケースを作らない。

