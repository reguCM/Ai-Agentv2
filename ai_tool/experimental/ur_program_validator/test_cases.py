"""Test scripts T1–T8 for Phase H PoC."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ExpectedValidator = Literal["PASS", "FAIL", "WARNING", "ANY"]
ExpectedURSim = Literal["PASS", "FAIL", "ANY", "SKIP"]
ExpectedCompare = Literal["expected", "critical_miss", "possible_over_validation", "ANY"]


@dataclass
class URTestCase:
    test_id: str
    label: str
    script: str
    polyscope_version: str = "5.15"
    expect_validator: ExpectedValidator = "ANY"
    expect_ursim: ExpectedURSim = "ANY"
    expect_compare: ExpectedCompare = "ANY"
    expect_runtime_fail: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "label": self.label,
            "script": self.script,
            "polyscope_version": self.polyscope_version,
            "expect_validator": self.expect_validator,
            "expect_ursim": self.expect_ursim,
            "expect_compare": self.expect_compare,
            "notes": self.notes,
        }


T1_VALID_BASIC = URTestCase(
    test_id="T1",
    label="Valid basic script",
    script="""
def my_program():
    movej(get_actual_joint_positions(), 1.0, 1.0)
    set_digital_out(0, 1)
end
""",
    expect_validator="PASS",
    expect_ursim="PASS",
    expect_compare="expected",
)

T2_UNKNOWN_FUNCTION = URTestCase(
    test_id="T2",
    label="Non-existent function",
    script="""
def my_program():
    foo_bar(get_actual_joint_positions())
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

T3_ARG_COUNT = URTestCase(
    test_id="T3",
    label="Wrong argument count",
    script="""
def my_program():
    movej(get_actual_joint_positions())
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

T4_TYPE_ERROR = URTestCase(
    test_id="T4",
    label="Python-style boolean",
    script="""
def my_program():
    set_digital_out(0, False)
end
""",
    expect_validator="WARNING",
    expect_ursim="PASS",
    expect_compare="ANY",
    notes="WARNING for Python-style literal — URSim stub may still pass",
)

T5_SYNTAX_ERROR = URTestCase(
    test_id="T5",
    label="Syntax error — unbalanced parens",
    script="""
def my_program():
    movej(get_actual_joint_positions(), 1.0
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

T6_VERSION_DIFF = URTestCase(
    test_id="T6",
    label="Version-specific function",
    script="""
def my_program():
    legacy_move(get_actual_joint_positions())
end
""",
    polyscope_version="5.15",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
    notes="legacy_move in catalog for 5.0 only — unavailable on 5.15",
)

T6_VERSION_OK = URTestCase(
    test_id="T6b",
    label="Version-specific function on older PolyScope",
    script=T6_VERSION_DIFF.script,
    polyscope_version="5.0",
    expect_validator="PASS",
    expect_ursim="PASS",
    expect_compare="expected",
)

T7_BLIND_SPOT = URTestCase(
    test_id="T7",
    label="Validator blind spot — runtime-only failure",
    script="""
def my_program():
    movej(get_actual_joint_positions(), 1.0, 1.0)
    # RUNTIME_FAIL marker for stub
end
""",
    expect_validator="PASS",
    expect_ursim="FAIL",
    expect_compare="critical_miss",
    expect_runtime_fail=True,
    notes="Static PASS but runtime joint/target issue — critical_miss observation",
)

T8_NORMAL_SET = URTestCase(
    test_id="T8a",
    label="Normal motion script 1",
    script="""
def prog_a():
    movel(get_actual_tcp_pose(), 0.5, 0.5)
    sleep(0.1)
end
""",
    expect_validator="PASS",
    expect_ursim="PASS",
)

T8_NORMAL_2 = URTestCase(
    test_id="T8b",
    label="Normal motion script 2",
    script="""
def prog_b():
    movej(get_actual_joint_positions(), 0.8, 0.8, 0.0)
end
""",
    expect_validator="PASS",
    expect_ursim="PASS",
)

T_PYTHON_CONFUSION = URTestCase(
    test_id="T2b",
    label="Python pandas confusion",
    script="""
def my_program():
    pandas.read_csv("data.csv")
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    notes="LLM/Python hallucination pattern",
)


def all_test_cases() -> list[URTestCase]:
    return [
        T1_VALID_BASIC,
        T2_UNKNOWN_FUNCTION,
        T_PYTHON_CONFUSION,
        T3_ARG_COUNT,
        T4_TYPE_ERROR,
        T5_SYNTAX_ERROR,
        T6_VERSION_DIFF,
        T6_VERSION_OK,
        T7_BLIND_SPOT,
        T8_NORMAL_SET,
        T8_NORMAL_2,
    ]
