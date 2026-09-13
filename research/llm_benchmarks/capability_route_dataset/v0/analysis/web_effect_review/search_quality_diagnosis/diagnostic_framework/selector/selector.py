"""Rule-based diagnostic method selector.

Uses knowledge_base/method_catalog.json + selector/rules.json.
Does not train a model, does not modify production Tools, does not overwrite
existing experiment runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
FRAMEWORK_DIR = THIS_DIR.parent
KB_DIR = FRAMEWORK_DIR / "knowledge_base"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def features_match(required: dict[str, Any], actual: dict[str, Any]) -> bool:
    for key, want in required.items():
        if key not in actual:
            return False
        if actual[key] != want:
            return False
    return True


@dataclass
class MethodDecision:
    method_id: str
    selected: bool
    role: str | None = None
    reason: str | None = None
    not_selected_reason: str | None = None
    confidence: str | None = None
    status: str | None = None
    rule_ids: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    reusable_artifacts: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "method_id": self.method_id,
            "selected": self.selected,
            "status": self.status,
            "confidence": self.confidence,
        }
        if self.selected:
            d["role"] = self.role
            d["reason"] = self.reason
            d["rule_ids"] = self.rule_ids
            d["findings"] = self.findings
            d["reusable_artifacts"] = self.reusable_artifacts
        else:
            d["not_selected_reason"] = self.not_selected_reason
            d["reusable_artifacts"] = self.reusable_artifacts
        return d


class DiagnosticSelector:
    def __init__(
        self,
        catalog: dict[str, Any],
        rules: dict[str, Any],
        reuse_index: dict[str, Any],
        experiment_data: dict[str, Any] | None = None,
    ) -> None:
        self.catalog = catalog
        self.rules = rules
        self.reuse_index = reuse_index
        self.experiment_data = experiment_data or {}
        self.methods = {m["id"]: m for m in catalog["methods"]}

    @classmethod
    def from_default_paths(cls) -> "DiagnosticSelector":
        catalog = load_json(KB_DIR / "method_catalog.json")
        rules = load_json(THIS_DIR / "rules.json")
        reuse = load_json(THIS_DIR / "reuse_index.json")
        exp = load_json(KB_DIR / "experiment_data.json")
        return cls(catalog, rules, reuse, exp)

    def select(self, problem: dict[str, Any]) -> dict[str, Any]:
        features = dict(problem.get("features") or {})
        problem_id = problem["problem_id"]
        decisions: dict[str, MethodDecision] = {}

        for method_id, meta in self.methods.items():
            decisions[method_id] = MethodDecision(
                method_id=method_id,
                selected=False,
                status=meta.get("status"),
                confidence=meta.get("confidence"),
                reusable_artifacts=self._artifacts(problem_id, method_id),
            )

        for block_id in self.rules.get("hard_blocks", []):
            d = decisions[block_id]
            d.selected = False
            d.not_selected_reason = self.rules["not_select_reasons"].get(
                block_id, "hard_block"
            )
            d.rule_ids.append("HARD-BLOCK")

        for item in self.rules.get("always_select", []):
            mid = item["method_id"]
            d = decisions[mid]
            d.selected = True
            d.role = item.get("role", "always")
            d.reason = item["reason"]
            d.rule_ids.append(item["rule_id"])
            if item.get("finding"):
                d.findings.append(item["finding"])

        for rule in self.rules.get("feature_rules", []):
            if not features_match(rule["when"], features):
                continue
            mid = rule["select"]
            d = decisions[mid]
            if mid in self.rules.get("hard_blocks", []):
                continue
            d.selected = True
            d.role = rule.get("role")
            if d.reason:
                d.reason = d.reason + " / " + rule["reason"]
            else:
                d.reason = rule["reason"]
            d.rule_ids.append(rule["rule_id"])
            if rule.get("finding"):
                d.findings.append(rule["finding"])

        for mid, d in decisions.items():
            if d.selected:
                continue
            if d.not_selected_reason:
                continue
            d.not_selected_reason = self.rules["not_select_reasons"].get(
                mid,
                "現在の問題特徴がこの手法の適用条件を満たさない。",
            )

        pipeline = [
            mid
            for mid in self.rules.get("pipeline_order", [])
            if decisions[mid].selected
        ]
        extra = [
            mid
            for mid, d in decisions.items()
            if d.selected and mid not in pipeline
        ]
        pipeline.extend(extra)

        selected = [decisions[mid].as_dict() for mid in pipeline]
        not_selected = [
            decisions[mid].as_dict()
            for mid in sorted(decisions)
            if not decisions[mid].selected
        ]
        considered = [decisions[mid].as_dict() for mid in sorted(decisions)]

        reuse = self.reuse_index.get("problems", {}).get(problem_id)
        return {
            "selector": {
                "type": "rule_based_plus_knowledge_base",
                "ml": False,
                "version": self.rules.get("version"),
            },
            "problem_id": problem_id,
            "tool": problem.get("tool"),
            "features": features,
            "auto_fix": "NOT_ALLOWED",
            "selected_pipeline": pipeline,
            "selected": selected,
            "not_selected": not_selected,
            "candidates_considered": considered,
            "reuse": {
                "problem_id": problem_id,
                "can_reuse_past_experiments": bool(reuse),
                "experiments": (reuse or {}).get("experiments", []),
                "note": "同じ problem_id では既存成果物を再利用する。Qwen/DeepSeek/大型LLMは再実行しない。",
            },
            "warnings": self._warnings(decisions),
        }

    def _artifacts(self, problem_id: str, method_id: str) -> list[str]:
        block = self.reuse_index.get("problems", {}).get(problem_id) or {}
        by_method = block.get("artifacts_by_method") or {}
        return list(by_method.get(method_id) or [])

    def _warnings(self, decisions: dict[str, MethodDecision]) -> list[str]:
        out = [
            "これは暫定Selectorであり、確定設計ではない。",
            "auto_fix は NOT_ALLOWED。本番 Tool は変更しない。",
        ]
        for mid in ("n1_single_edge", "n3_runtime_evidence_gate", "small_then_large_pipeline"):
            if decisions[mid].selected:
                out.append(
                    f"{mid} は選択されたが status={decisions[mid].status}。"
                    " 実験で確定した採用ではない。"
                )
        if decisions["n2_path_gate"].selected:
            out.append("N2 の YES を原因の強さに使ってはならない。")
        if decisions["specification_map"].selected:
            out.append("仕様書は地図のみ。実装行の最終根拠にしない。")
        return out


def evaluate_against_gold(result: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    selected = set(result["selected_pipeline"])
    must = set(gold["must_select"])
    must_not = set(gold["must_not_select"])
    missing = sorted(must - selected)
    forbidden_hit = sorted(must_not & selected)
    unexpected_ok = sorted(selected - must - set(gold.get("may_select") or []))
    checks = {
        "must_select_ok": not missing,
        "must_not_select_ok": not forbidden_hit,
        "auto_fix_ok": result.get("auto_fix") == gold.get("auto_fix_must_be"),
        "reuse_ok": (not gold.get("reuse_required"))
        or bool(result.get("reuse", {}).get("can_reuse_past_experiments")),
        "ml_not_used": result.get("selector", {}).get("ml") is False,
    }
    checks["all_ok"] = all(checks.values())
    return {
        "checks": checks,
        "missing_must_select": missing,
        "forbidden_selected": forbidden_hit,
        "selected_outside_must_or_may": unexpected_ok,
        "selected": sorted(selected),
        "note": "評価は既存知識ベースの期待との一致。新しい診断実験ではない。",
    }
