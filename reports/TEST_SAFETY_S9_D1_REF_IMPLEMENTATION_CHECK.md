# Test Safety — S9 D1 External `$ref` Implementation Check

**Date:** 2026-09-12  
**Status:** COMPLETE (S9 entry gate)  
**Authority:** `reports/TEST_SAFETY_S8_1_HUMAN_DECISION_CLOSURE.md` (D1)

## Question

Can tool-argument JSON Schema use **external** `$ref` to  
`registry/schema/test_safety_evaluation.schema.json#/$defs/test_plan`  
with the **same loader pattern** as `validate_packet_schema` (single file, `Draft202012Validator(schema)`)?

## Results

| Method | Result |
|--------|--------|
| Naive single-file validator on tool schema with external `$ref` | **NOT_SUPPORTED** — unresolved `$ref` |
| `referencing.Registry` + `Resource` (jsonschema 4.x) | **SUPPORTED** when `referencing` package is importable in the runtime environment |
| Load evaluation schema once; validate instance against `schema["$defs"]["test_plan"]` | **SUPPORTED** — **no duplicated constraint subset**; single file canonical |

## Decision (S9)

**Do not** add a separate tool schema JSON that relies on unresolved external `$ref`.

**Do** implement `validate_run_test_plan_arguments()` in `tools/test_safety/tool_argument_validation.py` that:

1. Loads `registry/schema/test_safety_evaluation.schema.json` from disk.
2. Validates `arguments["test_plan"]` with `Draft202012Validator(evaluation_schema["$defs"]["test_plan"])`.

Optional future: add `registry/schema/run_test_plan_tool.schema.json` documenting the wrapper object, with validation still delegated to the helper above (or Registry-based `$ref` where `referencing` is guaranteed).

## Environment note

Project pytest/dev may use Python 3.10 where `referencing` is not always installed alongside `jsonschema`; the **loader-from-canonical-file** approach avoids that dependency for tool-arg validation.

## S8.1 compliance

- `s8_1_external_ref_resolution`: **VERIFIED** for chosen approach (canonical file load).
- `if_external_ref_unsupported_no_silent_duplicate`: **SATISFIED** — no silent duplicated subset file added.
