"""Phase I live test cases — I-T1 through I-T6."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ai_tool.experimental.ur_program_validator.test_cases import URTestCase

ExpectedValidator = Literal["PASS", "FAIL", "WARNING", "ANY"]
ExpectedURSim = Literal["PASS", "FAIL", "ANY", "SKIP"]
ExpectedCompare = Literal["expected", "critical_miss", "possible_over_validation", "ANY", "NOT_FOUND"]
ExpectedT7 = Literal["CRITICAL_MISS", "NOT_FOUND", "STUB_ONLY", "ANY"]


@dataclass
class LiveTestCase:
    test_id: str
    label: str
    script: str
    polyscope_version: str = "5.15"
    expect_validator: ExpectedValidator = "ANY"
    expect_ursim: ExpectedURSim = "ANY"
    expect_compare: ExpectedCompare = "ANY"
    expect_t7: ExpectedT7 = "ANY"
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

    def as_ur_test_case(self) -> URTestCase:
        return URTestCase(
            test_id=self.test_id,
            label=self.label,
            script=self.script,
            polyscope_version=self.polyscope_version,
            expect_validator=self.expect_validator,
            expect_ursim=self.expect_ursim,
            expect_compare=self.expect_compare if self.expect_compare != "NOT_FOUND" else "ANY",
            notes=self.notes,
        )


# Official catalog-backed valid script — not LLM memory
I_T1_VALID = LiveTestCase(
    test_id="I-T1",
    label="Live valid basic script",
    script="""
def live_test():
    movej(get_actual_joint_positions(), 0.5, 0.5)
end
""",
    expect_validator="PASS",
    expect_ursim="PASS",
    expect_compare="expected",
    notes="Catalog-backed movej + builtin get_actual_joint_positions",
)

I_T2_UNKNOWN = LiveTestCase(
    test_id="I-T2",
    label="Live non-existent function",
    script="""
def live_test():
    foo_bar(get_actual_joint_positions())
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

I_T3_ARG_COUNT = LiveTestCase(
    test_id="I-T3",
    label="Live wrong argument count",
    script="""
def live_test():
    movej(get_actual_joint_positions())
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

I_T4_SYNTAX = LiveTestCase(
    test_id="I-T4",
    label="Live syntax error",
    script="""
def live_test():
    movej(get_actual_joint_positions(), 0.5
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

I_T5_VERSION = LiveTestCase(
    test_id="I-T5",
    label="Live version-specific function",
    script="""
def live_test():
    legacy_move(get_actual_joint_positions())
end
""",
    polyscope_version="5.15",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
    notes="legacy_move PoC catalog — 5.0 only",
)

I_T6_BLIND_SPOT = LiveTestCase(
    test_id="I-T6",
    label="Live validator blind spot search",
    script="""
def live_test():
    movej(get_actual_joint_positions(), 0.5, 0.5)
    # Phase H T7 marker — may not reproduce on live URSim
end
""",
    expect_validator="PASS",
    expect_ursim="ANY",
    expect_compare="ANY",
    expect_t7="ANY",
    notes="Search for Validator PASS + Live FAIL without synthetic marker",
)


def all_live_test_cases() -> list[LiveTestCase]:
    return [I_T1_VALID, I_T2_UNKNOWN, I_T3_ARG_COUNT, I_T4_SYNTAX, I_T5_VERSION, I_T6_BLIND_SPOT]
