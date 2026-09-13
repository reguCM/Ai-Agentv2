# Test Contract Skeleton Generator

**状態:** ADOPT CANDIDATE（固定構造。期待値の自動推測なし）

## 配置

`docs/ai_tool/tool_creation/validator/test_skeleton.py`

## 生成クラス（固定）

| クラス | Test Contract 対応 |
|--------|-------------------|
| `TestExistence` | import / tool_id |
| `TestInputSchema` | input schema 形状、invalid（skip/TODO） |
| `TestOutputSchema` | normal execution、error_format |
| `TestSideEffect` | side_effect 文書化、write 禁止枠 |
| `TestSafety` | contract.cannot / must_not |
| `TestContract` | can/cannot/must/must_not 完全性 |

## HUMAN_REQUIRED / TODO

実装固有の期待値は自動生成しない:

```python
def test_normal_execution_shape(self):
    result = tool_fn()  # HUMAN_REQUIRED: add arguments if needed
    assert isinstance(result, dict)
    TODO: assert keys match SPEC_OUTPUT_SCHEMA
```

- `provider_specific.module/function` がある場合のみ import 行を生成
- 引数あり Tool は invalid テストを `pytest.skip('HUMAN_REQUIRED')`

## 出力

`runs/ai_tool/<timestamp>_tool_creation_phase2/generated_tests/test_<tool_id>.py`

## LLM 不使用

テスト**内容**は固定テンプレートのみ。自由生成しない。

## Phase 2 生成結果

| Tool | 出力ファイル |
|------|--------------|
| local:get_gpu_status | `test_local_get_gpu_status.py` |
| local:cpu_status | `test_local_cpu_status.py` |

生成スケルトンはそのままでは多くが skip/TODO — **意図どおり**。

## 本番 tests/ への配置

Phase 2 では `tests/` にコピーしない。人間承認後に手動配置。
