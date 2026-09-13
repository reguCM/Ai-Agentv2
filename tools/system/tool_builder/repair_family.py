"""
Repair の5分類。Validator の code は増やしすぎず、測定用の家族にまとめる。
仕様は docs/repair_types.md。
"""

R1 = "R1"
R2 = "R2"
R3 = "R3"
R4 = "R4"
R5 = "R5"

FAMILIES = (R1, R2, R3, R4, R5)

FAMILY_TITLE = {
    R1: "Syntax / Format Repair",
    R2: "Runtime Repair",
    R3: "Semantic Repair",
    R4: "Finding Repair",
    R5: "Research Repair",
}

CODE_TO_FAMILY = {
    "return_value_not_dict": R1,
    "wrong_output_key": R1,
    "unparsed_output": R1,
    "meaningless_output": R1,
    "missing_stub_marker": R1,
    "unconfirmed_looks_complete": R1,
    "runtime_exception": R2,
    "subprocess_result_handling": R2,
    "semantic_mismatch": R3,
    "wrong_command": R4,
    "stub_value": R5,
    "empty_output_spec": R5,
}

ERROR_TO_FAMILY = {
    "no_json": R1,
    "no_code": R1,
    "timeout": R1,
}

# 同時に複数 code があるとき、より手前の修復を優先する。
FAMILY_PRIORITY = (R2, R1, R3, R4, R5)


def family_for_code(code):
    return CODE_TO_FAMILY.get(code)


def classify_repair_family(*, codes=None, error=None, step=None):
    """
    Validator code / LLM 出力エラー / 分岐から R1〜R5 を1つ返す。
    ケースを単一家族で測るためのラベルであり、パイプライン分岐そのものではない。
    """
    if error in ERROR_TO_FAMILY and not codes:
        return ERROR_TO_FAMILY[error]

    families = []
    for code in codes or []:
        family = family_for_code(code)
        if family and family not in families:
            families.append(family)

    if error in ERROR_TO_FAMILY:
        extra = ERROR_TO_FAMILY[error]
        if extra not in families:
            families.append(extra)

    if not families and step == "research":
        return R5
    if not families:
        return None

    for family in FAMILY_PRIORITY:
        if family in families:
            return family
    return families[0]
