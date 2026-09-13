from __future__ import annotations

from validator.test_skeleton import generate_test_skeleton

# Phase 2 fixed class names (regression)
SKELETON_CLASSES = (
    "TestExistence",
    "TestInputSchema",
    "TestOutputSchema",
    "TestSideEffect",
    "TestSafety",
    "TestContract",
)

# User-facing contract areas mapped to skeleton content
REQUIRED_MARKERS = (
    "SPEC_INPUT_SCHEMA",  # input validation
    "SPEC_OUTPUT_SCHEMA",  # output contract
    "TestSafety",  # safety
    "TestSideEffect",  # side effect
    "error_format",  # error handling
    "HUMAN_REQUIRED",  # expectations left to human
    "TODO",  # not auto-generated expectations
)


def test_skeleton_contains_fixed_classes(gpu_status_spec: dict) -> None:
    text = generate_test_skeleton(gpu_status_spec)
    for cls in SKELETON_CLASSES:
        assert f"class {cls}" in text, f"missing {cls}"


def test_skeleton_maintains_human_boundary(gpu_status_spec: dict) -> None:
    text = generate_test_skeleton(gpu_status_spec)
    for marker in REQUIRED_MARKERS:
        assert marker in text, f"missing marker {marker}"
    assert "pytest.skip('HUMAN_REQUIRED" in text


def test_skeleton_imports_provider_module_when_present(gpu_status_spec: dict) -> None:
    text = generate_test_skeleton(gpu_status_spec)
    assert "from tools.system.gpu.gpu_status import get_gpu_status as tool_fn" in text


def test_skeleton_cpu_status_generated(cpu_status_spec: dict) -> None:
    text = generate_test_skeleton(cpu_status_spec)
    assert "local:cpu_status" in text
    assert "class TestContract" in text
