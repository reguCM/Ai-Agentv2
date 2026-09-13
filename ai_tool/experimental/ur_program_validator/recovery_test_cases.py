"""Phase I-R live test cases — I-R1 through I-R6."""
from __future__ import annotations

from ai_tool.experimental.ur_program_validator.live_test_cases import LiveTestCase

I_R1_VALID = LiveTestCase(
    test_id="I-R1",
    label="Valid URScript",
    script="""
def recovery_test():
    movej(get_actual_joint_positions(), 0.5, 0.5)
end
""",
    expect_validator="PASS",
    expect_ursim="PASS",
    expect_compare="expected",
)

I_R2_SYNTAX = LiveTestCase(
    test_id="I-R2",
    label="Syntax error",
    script="""
def recovery_test():
    movej(get_actual_joint_positions(), 0.5
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

I_R3_UNKNOWN = LiveTestCase(
    test_id="I-R3",
    label="Unknown function",
    script="""
def recovery_test():
    foo_bar(get_actual_joint_positions())
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

I_R4_ARG = LiveTestCase(
    test_id="I-R4",
    label="Argument count error",
    script="""
def recovery_test():
    movej(get_actual_joint_positions())
end
""",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

I_R5_VERSION = LiveTestCase(
    test_id="I-R5",
    label="Version-specific function on 5.15",
    script="""
def recovery_test():
    legacy_move(get_actual_joint_positions())
end
""",
    polyscope_version="5.15",
    expect_validator="FAIL",
    expect_ursim="FAIL",
    expect_compare="expected",
)

I_R6_BLIND_SPOT = LiveTestCase(
    test_id="I-R6",
    label="Natural validator blind spot search",
    script="""
def recovery_test():
    movej(get_actual_joint_positions(), 0.5, 0.5)
    movel(get_actual_tcp_pose(), 0.3, 0.3)
end
""",
    expect_validator="PASS",
    expect_ursim="ANY",
    expect_compare="ANY",
    notes="No synthetic RUNTIME_FAIL marker — search only",
)


def all_recovery_test_cases() -> list[LiveTestCase]:
    return [I_R1_VALID, I_R2_SYNTAX, I_R3_UNKNOWN, I_R4_ARG, I_R5_VERSION, I_R6_BLIND_SPOT]
