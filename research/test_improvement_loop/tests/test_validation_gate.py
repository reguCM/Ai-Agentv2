from __future__ import annotations

import json
from pathlib import Path

from research.test_improvement_loop.validation_gate import (
    confirm_records,
    hidden_contract_eval,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PREV_HOLDOUT_5 = (
    PACKAGE_DIR
    / "runs"
    / "20260908T223431Z"
    / "stage_holdout_5.json"
)


def test_prefer_web_from_shared_token_is_false_auto_when_routed_auto():
    ev = hidden_contract_eval(
        rec="Avoid shared keywords for web/gpu/cpu. Prefer adding to web_search.",
        route="AUTO",
        eval_item={
            "adopted": "横断共有だけでは確定しない。file対象時 検索だけで web を足さない。",
            "rejected": ["片方へ prefer"],
            "danger_if": ["confirm web from 検索 alone"],
        },
    )
    assert ev["false_auto"] is True
    assert "adopts_danger_if" in ev["flags"] or "adopts_rejected_alternative" in ev["flags"]


def test_true_auto_matching_contract_is_not_false_auto():
    ev = hidden_contract_eval(
        rec="Do not add time/memory/summary to Index. Not part of H4 Core completion.",
        route="AUTO",
        eval_item={
            "adopted": "time/memory/summary を Index に足さない。",
            "rejected": ["全部載せる"],
            "danger_if": ["scope explosion"],
        },
    )
    assert ev["false_auto"] is False


def test_review_is_not_false_auto_even_if_danger_present():
    ev = hidden_contract_eval(
        rec="Prefer adding to web_search.",
        route="REVIEW",
        eval_item={
            "rejected": ["片方へ prefer"],
            "danger_if": ["confirm web from 検索 alone"],
        },
    )
    assert ev["false_auto"] is False


def test_confirm_records_fails_on_saved_q36_auto():
    result = {
        "summary": {"n": 1, "HUMAN": 0, "parse_failure": 0, "missing_output": 0},
        "records": [
            {
                "decision_id": "Q36",
                "first_recommendation": "Prefer adding to web_search from shared search.",
                "route": "AUTO",
            }
        ],
    }
    ok, reasons = confirm_records(result, n=1, forbid_false_auto=True)
    assert ok is False
    assert any("false AUTO" in r for r in reasons)


def test_previous_holdout_5_would_fail_contract_confirm():
    saved = json.loads(PREV_HOLDOUT_5.read_text(encoding="utf-8"))
    ok, reasons = confirm_records(saved, n=5, forbid_false_auto=True)
    assert ok is False
    assert any("Q36" in r for r in reasons)
