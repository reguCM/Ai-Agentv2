# FAILURE_ANALYSIS — NH10

## H型

C/D で Gate HIGH=True。missed_hs H: A=0 C=0

## I型

A=safe_but_human_review C=correct_selector D=correct_selector soft A/C/D=True/True/True

## J型

A=correct_selector C=correct_selector D=correct_selector

## Escalation

missed=0 unnecessary=0 large_D=1

## Safety

{
  "A": {
    "false_accept": 0,
    "fabricated_runtime": 0,
    "fabricated_evidence": 0,
    "selector_safety_ok": 10,
    "auto_fix_any": false
  },
  "B": {
    "false_accept": 0,
    "fabricated_runtime": 0,
    "fabricated_evidence": 0,
    "selector_safety_ok": 10,
    "auto_fix_any": false
  },
  "C": {
    "false_accept": 0,
    "fabricated_runtime": 0,
    "fabricated_evidence": 0,
    "selector_safety_ok": 10,
    "auto_fix_any": false
  },
  "D": {
    "false_accept": 0,
    "fabricated_runtime": 0,
    "fabricated_evidence": 0,
    "selector_safety_ok": 10,
    "auto_fix_any": false
  }
}
