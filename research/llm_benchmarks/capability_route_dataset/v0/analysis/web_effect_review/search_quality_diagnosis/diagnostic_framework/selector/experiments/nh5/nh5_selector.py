"""NH5 experimental method selector — simulation only.

Does NOT modify production selector.py, rules.json, or Agent/Tool/Manager.
Combines NH1–NH4 experimental knowledge with existing DiagnosticSelector for diagnosis cases.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Import production selector without modifying it
SELECTOR_DIR = Path(__file__).resolve().parents[2]
FRAMEWORK_DIR = SELECTOR_DIR.parent
KB_DIR = FRAMEWORK_DIR / "knowledge_base"
NH5_DIR = Path(__file__).resolve().parent

if str(SELECTOR_DIR) not in sys.path:
    sys.path.insert(0, str(SELECTOR_DIR))

from selector import DiagnosticSelector  # noqa: E402


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def features_match(required: dict[str, Any], actual: dict[str, Any]) -> bool:
    for k, v in required.items():
        if actual.get(k) != v:
            return False
    return True


class NH5Selector:
    def __init__(self) -> None:
        self.registry = load_json(NH5_DIR / "method_registry.json")["methods"]
        self.rules = load_json(NH5_DIR / "rules.json")
        self.catalog = {m["id"]: m for m in load_json(KB_DIR / "method_catalog.json")["methods"]}
        self.base_selector = DiagnosticSelector.from_default_paths()

    def _status(self, method_id: str) -> str:
        reg = self.registry.get(method_id) or {}
        cid = reg.get("catalog_id")
        if cid and cid in self.catalog:
            return str(self.catalog[cid].get("status") or reg.get("status") or "unknown")
        return str(reg.get("status") or "unknown")

    def _runs(self, method_id: str) -> list[str]:
        reg = self.registry.get(method_id) or {}
        return list(reg.get("runs") or [])

    def select(self, case: dict[str, Any]) -> dict[str, Any]:
        features = dict(case.get("features") or {})
        case_id = case["case_id"]

        selected: set[str] = set()
        rejected: set[str] = set(self.rules.get("hard_reject") or [])
        reasons: list[str] = []
        safety_constraints: list[str] = []
        unknowns: list[str] = []
        reused: set[str] = set()

        for item in self.rules.get("always_select", []):
            mid = item["method_id"]
            selected.add(mid)
            reasons.append(f"[{item['rule_id']}] {item['reason']}")
            reused.update(self._runs(mid))

        for rule in self.rules.get("feature_rules", []):
            if not features_match(rule["when"], features):
                continue
            for mid in rule.get("select") or []:
                selected.add(mid)
            for mid in rule.get("reject") or []:
                rejected.add(mid)
                selected.discard(mid)
            reasons.append(f"[{rule['rule_id']}] {rule['reason']}")
            for mid in rule.get("select") or []:
                reused.update(self._runs(mid))

        # Delegate to production DiagnosticSelector for diagnostic methods
        diag_selected: set[str] = set()
        if features.get("state_change_requested") is not True or features.get("code_available"):
            diag_problem = {
                "problem_id": f"nh5_{case_id.lower()}",
                "tool": case.get("tool", "simulation"),
                "features": features,
            }
            diag = self.base_selector.select(diag_problem)
            for item in diag["selected"]:
                mid = item["method_id"]
                # Only merge diagnostic-domain methods, not auto_fix etc.
                if mid in rejected:
                    continue
                if mid.startswith("nh") or mid.startswith("nh4"):
                    continue
                diag_selected.add(mid)
                if item.get("reason"):
                    reasons.append(f"[DIAG] {mid}: {item['reason']}")
            for mid in self.rules.get("hard_reject", []):
                if mid in diag_selected:
                    diag_selected.discard(mid)
                    rejected.add(mid)

        # Apply hard reject to selected
        for mid in list(selected):
            if mid in self.rules.get("hard_reject", []):
                selected.discard(mid)
                rejected.add(mid)

        selected.update(diag_selected)

        # Safety constraints
        if features.get("state_change_requested") or features.get("reopen_requested"):
            safety_constraints.append("mechanical_validator_priority")
            safety_constraints.append("auto_fix_allowed=false")
        safety_constraints.append("unknown_non_forcing_policy")

        # Escalation
        escalation = "NONE"
        if features.get("llm_disagreement"):
            escalation = "HUMAN_REVIEW"
            unknowns.append("llm_judgment_conflict")
        elif features.get("small_llm_output_suspicious"):
            escalation = "LARGE_LLM"
        elif features.get("has_runtime_logs") is False and features.get("code_available"):
            escalation = "ESCALATE_INVESTIGATE"
            unknowns.append("missing_runtime_evidence")
        elif features.get("needs_path_integration") and not features.get("llm_disagreement"):
            escalation = "LARGE_LLM"
        elif features.get("evidence_suspicious"):
            escalation = "UNKNOWN_OR_REJECT"
            unknowns.append("evidence_trust")

        if features.get("near_exact_reactivation") and not features.get("reopen_requested"):
            unknowns.append("near_exact_boundary_possible")

        human_review = bool(
            features.get("llm_disagreement")
            or features.get("evidence_suspicious")
            or features.get("reopen_requested")
            or escalation in {"HUMAN_REVIEW", "UNKNOWN_OR_REJECT"}
            or (features.get("reopen_requested") and features.get("evidence_timestamp_unknown"))
        )

        confidence = "high"
        if unknowns or escalation in {"ESCALATE_INVESTIGATE", "UNKNOWN_OR_REJECT", "HUMAN_REVIEW"}:
            confidence = "low"
        elif any(self._status(m).startswith("experimental") for m in selected):
            confidence = "medium"

        # Rejected with reasons (not in selected)
        rejected_methods = []
        all_methods = set(self.registry.keys()) | set(self.catalog.keys())
        for mid in sorted(all_methods):
            if mid in selected:
                continue
            if mid not in rejected and mid not in selected:
                # only list methods we considered relevant
                if mid in self.rules.get("hard_reject", []):
                    rejected.add(mid)
            if mid in rejected or mid in self.rules.get("hard_reject", []):
                rr = self.rules.get("reject_reasons", {}).get(mid) or self.rules.get("reject_reasons", {}).get(
                    mid, f"not_applicable_for_case_{case_id}"
                )
                if mid in self.rules.get("hard_reject", []):
                    rr = self.rules["reject_reasons"].get(mid, "hard_reject")
                rejected_methods.append(
                    {
                        "method_id": mid,
                        "status": self._status(mid),
                        "reason": rr if mid in self.rules.get("reject_reasons", {}) else "条件不一致または未適用",
                    }
                )

        selected_methods = [
            {
                "method_id": mid,
                "status": self._status(mid),
                "tier": (self.registry.get(mid) or {}).get("tier", "diagnostic"),
                "hypothesis": (self.registry.get(mid) or {}).get("hypothesis"),
                "runs": self._runs(mid),
            }
            for mid in sorted(selected)
        ]

        return {
            "case_id": case_id,
            "scenario": case.get("scenario"),
            "safety_class": case.get("safety_class"),
            "selected_methods": selected_methods,
            "rejected_methods": rejected_methods,
            "escalation": escalation,
            "confidence": confidence,
            "selection_reasons": reasons,
            "safety_constraints": safety_constraints,
            "unknowns": unknowns,
            "human_review_required": human_review,
            "auto_fix_allowed": False,
            "reused_experiments": sorted(reused),
            "features": features,
            "selector": {
                "type": "nh5_experimental_rule_based",
                "production_selector_modified": False,
                "ml": False,
            },
        }


def evaluate_case(output: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    selected_ids = {m["method_id"] for m in output["selected_methods"]}
    must = set(gold.get("must_select") or [])
    must_not = set(gold.get("must_not_select") or [])
    must_not_treat_proven = set(gold.get("must_not_treat_as_proven") or [])

    missing = sorted(must - selected_ids)
    forbidden = sorted(must_not & selected_ids)
    experimental_as_proven = [
        m["method_id"]
        for m in output["selected_methods"]
        if m["method_id"] in must_not_treat_proven
        and m.get("status") in {"adopt", "conditional_adopt"}
    ]

    checks = {
        "must_select_ok": not missing,
        "must_not_select_ok": not forbidden,
        "auto_fix_ok": output.get("auto_fix_allowed") is False,
        "human_review_ok": (not gold.get("human_review_required"))
        or output.get("human_review_required") is True,
        "escalation_ok": (not gold.get("escalation_must_be"))
        or output.get("escalation") == gold["escalation_must_be"]
        or (
            gold.get("escalation_one_of")
            and output.get("escalation") in gold["escalation_one_of"]
        ),
        "unknown_ok": (not gold.get("unknown_required"))
        or len(output.get("unknowns") or []) > 0
        or output.get("escalation") in {"UNKNOWN_OR_REJECT", "ESCALATE_INVESTIGATE", "HUMAN_REVIEW"},
        "no_experimental_as_adopt": not experimental_as_proven,
        "reason_trace_ok": len(output.get("selection_reasons") or []) > 0,
    }
    checks["safety_ok"] = checks["must_not_select_ok"] and checks["auto_fix_ok"]
    checks["method_selection_ok"] = checks["must_select_ok"] and checks["must_not_select_ok"]
    checks["over_rejection_ok"] = not gold.get("must_not_over_reject") or all(
        mid in selected_ids for mid in gold["must_not_over_reject"]
    )
    checks["all_ok"] = all(
        checks[k]
        for k in checks
        if k not in {"safety_ok", "method_selection_ok", "over_rejection_ok"}
    )

    return {
        "case_id": output["case_id"],
        "checks": checks,
        "missing_must_select": missing,
        "forbidden_selected": forbidden,
        "selected_ids": sorted(selected_ids),
        "escalation": output.get("escalation"),
        "confidence": output.get("confidence"),
    }
