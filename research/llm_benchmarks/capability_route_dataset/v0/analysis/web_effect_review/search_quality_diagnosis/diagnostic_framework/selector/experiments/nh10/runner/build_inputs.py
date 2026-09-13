"""Build NH10 inputs from NH8/NH9 without modifying those runs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
NH9 = HERE.parents[1] / "20260827_151000" / "nh9_fixed_observation_escalation"
NH8 = HERE.parents[1] / "20260827_145000" / "nh8_uncertainty_gated_escalation"
NH10_EXP = HERE.parents[2] / "selector" / "experiments" / "nh10"
INPUTS = HERE / "inputs"


def gold_high_slots() -> dict:
    """Must-cover slots (HIGH or already correctly OBSERVED/NOT_OBSERVED). Focus H/I/J."""
    return {
        "NH5-A": [],
        "NH5-B": [],
        "NH5-C": [],
        "NH5-D": [],
        "NH5-E": [],
        "NH5-F": [],
        "NH5-G": [],
        "NH5-H": ["code_scope_present", "runtime_issue_observed"],
        "NH5-I": ["stdout_present", "runtime_issue_observed", "small_llm_unverified"],
        "NH5-J": ["llm_disagreement"],
    }


def main() -> None:
    INPUTS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(NH9 / "inputs" / "case_inputs.json", INPUTS / "case_inputs.json")
    shutil.copy2(NH9 / "inputs" / "gold_fingerprints.json", INPUTS / "gold_fingerprints.json")
    shutil.copy2(NH9 / "inputs" / "selector_gold.json", INPUTS / "selector_gold.json")
    shutil.copy2(NH9 / "inputs" / "gold_escalation.json", INPUTS / "gold_escalation.json")
    shutil.copy2(NH9 / "inputs" / "gold_slots.json", INPUTS / "gold_slots.json")
    (INPUTS / "gold_high_slots.json").write_text(
        json.dumps(gold_high_slots(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # copy rules into run for audit
    for name in (
        "mechanical_prefill_rules.json",
        "high_slot_schema.json",
        "reason_to_slot_map.json",
    ):
        shutil.copy2(NH10_EXP / name, HERE / name)
    # selector_inputs mirror
    cases = json.loads((INPUTS / "case_inputs.json").read_text(encoding="utf-8"))
    (HERE / "selector_inputs.json").write_text(
        json.dumps(
            {
                "run_id": "20260827_163000",
                "source_nh9": str(NH9),
                "legacy_cases": [c["case_id"] for c in cases],
                "new_cases": [],
                "nh9_condition_a": "condition_c",
                "auto_fix": "NOT_ALLOWED",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("NH10 inputs ready")


if __name__ == "__main__":
    main()
