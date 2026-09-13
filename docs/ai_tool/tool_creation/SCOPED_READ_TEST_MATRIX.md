# Scoped Read — Test Matrix

**Tool:** `local:workspace_read_text_scoped`  
**共通契約:** [TEST_CONTRACT.md](./TEST_CONTRACT.md)（重複定義なし。本表は映射のみ）

| TEST_CONTRACT | テスト関数 | 結果 |
|---------------|-----------|------|
| **Normal** | | |
| N-01 代表入力 | test_normal_text_file | PASS |
| N-02 最小入力 | test_normal_empty_file | PASS |
| N-03 output_schema | test_output_contract_success_keys | PASS |
| 追加: md/json/unicode | test_normal_md_json_txt, test_normal_unicode | PASS |
| 追加: 実 repo | test_real_repo_allowlisted_file | PASS |
| **Boundary** | | |
| B 最大サイズ | test_boundary_max_size_exact, test_boundary_max_size_exceeded | PASS |
| B 行数上限 | test_boundary_default_line_limit_truncates | PASS |
| B offset/limit | test_boundary_offset_limit | PASS |
| B ネスト | test_boundary_nested_under_root | PASS |
| **Invalid** | | |
| I-03 必須欠落 | test_invalid_empty_path, test_invalid_whitespace_path | PASS |
| I-01 型/範囲 | test_invalid_bad_offset, test_invalid_bad_limit | PASS |
| F-01 不存在 | test_invalid_not_found | PASS |
| ディレクトリ | test_invalid_directory | PASS |
| **Failure** | | |
| F-04 permission | test_failure_io_unreadable_file | SKIP (Windows) |
| **Safety** | | |
| S-01 禁止操作なし | test_safety_no_write_operations | PASS |
| traversal | test_safety_traversal_rejected[*] | PASS |
| allowlist 外 | test_safety_outside_* | PASS |
| prefix trap | test_safety_outside_allowlist_prefix_trap | PASS |
| absolute path | test_safety_absolute_path_* | PASS |
| symlink | test_safety_symlink_escape_rejected | SKIP (Windows) |
| binary | test_safety_binary_rejected | PASS |
| error contract | test_output_contract_error_keys | PASS |

**合計:** 30 passed, 2 skipped, 0 failed

## SKIP 理由

| テスト | 理由 |
|--------|------|
| symlink | Windows: symlink 作成に開発者モード/管理者権限が必要な場合がある |
| permission | Windows: chmod ベースの unreadable 再現が非信頼 |

## 追加テスト

既存 32 件で TEST_CONTRACT 全カテゴリをカバー。重複テストは追加していない。
