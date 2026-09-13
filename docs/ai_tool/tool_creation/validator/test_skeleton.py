from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_HUMAN = "HUMAN_REQUIRED"
_TODO = "TODO"


def _safe_module_name(tool_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", tool_id.replace(":", "_"))


def generate_test_skeleton(spec: dict[str, Any]) -> str:
    """Fixed Test Contract structure. No LLM. Implementation expectations left as TODO."""
    tool_id = spec.get("tool_id", "unknown:tool")
    name = spec.get("name", "unknown_tool")
    module = (spec.get("provider_specific") or {}).get("module")
    function = (spec.get("provider_specific") or {}).get("function")
    side_effect = spec.get("side_effect", "unknown")
    has_input = bool((spec.get("input_schema") or {}).get("properties"))
    mod = _safe_module_name(tool_id)

    import_block = ""
    call_block = f"    # {_HUMAN}: import and call {name}\n    pytest.skip('{_HUMAN}: wire implementation import')"
    if module and function:
        import_block = f"from {module} import {function} as tool_fn"
        call_block = "    result = tool_fn()  # HUMAN_REQUIRED: add arguments if needed"

    lines = [
        f'"""Test Contract skeleton for {tool_id}.',
        "Auto-generated — do not treat as passing tests.",
        f"Side effect class: {side_effect}",
        '"""',
        "",
        "import json",
        "",
        "import pytest",
        "",
        import_block,
        "",
        f"TOOL_ID = {json.dumps(tool_id)}",
        f"TOOL_NAME = {json.dumps(name)}",
        f"SIDE_EFFECT = {json.dumps(side_effect)}",
        "SPEC_INPUT_SCHEMA = "
        + json.dumps(spec.get("input_schema") or {}, ensure_ascii=False, indent=4).replace(
            "\n", "\n"
        ),
        "SPEC_OUTPUT_SCHEMA = "
        + json.dumps(spec.get("output_schema"), ensure_ascii=False, indent=4).replace(
            "\n", "\n"
        ),
        "CONTRACT = "
        + json.dumps(spec.get("contract") or {}, ensure_ascii=False, indent=4).replace(
            "\n", "\n"
        ),
        "",
        "",
        "class TestExistence:",
        "    def test_tool_id_documented(self):",
        "        assert TOOL_ID",
        "        assert TOOL_NAME",
        "",
        "",
        "class TestInputSchema:",
        "    def test_input_schema_is_object(self):",
        '        assert SPEC_INPUT_SCHEMA.get("type") == "object"',
        "",
        "    @pytest.mark.skipif(" + ("False" if has_input else "True") + ", reason='no input parameters')",
        "    def test_invalid_input_type(self):",
        f"        {_TODO}: reject wrong types per input_schema",
        "        pytest.skip('HUMAN_REQUIRED: invalid input cases')",
        "",
        "",
        "class TestOutputSchema:",
        "    def test_normal_execution_shape(self):",
        call_block,
        "        assert isinstance(result, dict)",
        f"        {_TODO}: assert keys match SPEC_OUTPUT_SCHEMA",
        "",
        "    def test_error_format(self):",
        f"        {_TODO}: simulate failure path and assert error_format",
        "        pytest.skip('HUMAN_REQUIRED: error handling expectations')",
        "",
        "",
        "class TestSideEffect:",
        "    def test_side_effect_documented(self):",
        "        assert SIDE_EFFECT in {",
        '            "none", "read_only", "write", "modify", "execute", "unknown"',
        "        }",
        "",
        "    def test_no_unexpected_write(self):",
        '        if SIDE_EFFECT in ("none", "read_only"):',
        f"            {_TODO}: static or runtime check — no filesystem/network writes",
        "        pytest.skip('HUMAN_REQUIRED: side effect verification')",
        "",
        "",
        "class TestSafety:",
        "    def test_contract_cannot_rules(self):",
        '        cannot = CONTRACT.get("cannot") or []',
        "        assert cannot, 'contract.cannot must be defined'",
        "",
        "    def test_contract_must_not_rules(self):",
        '        must_not = CONTRACT.get("must_not") or []',
        "        assert must_not, 'contract.must_not must be defined'",
        "",
        "",
        "class TestContract:",
        "    def test_contract_complete(self):",
        "        for key in ('can', 'cannot', 'must', 'must_not'):",
        "            assert CONTRACT.get(key), f'contract.{key} missing'",
        "",
    ]
    return "\n".join(lines) + "\n"


def write_test_skeleton(
    spec: dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    tool_id = str(spec.get("tool_id") or "UNKNOWN")
    safe_name = tool_id.replace(":", "_")
    path = output_dir / f"test_{safe_name}.py"
    path.write_text(generate_test_skeleton(spec), encoding="utf-8")
    return path
