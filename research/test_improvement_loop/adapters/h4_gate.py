"""H4 Adoption Gate adapter for テスト改善ループ.

Replays saved Local recommendations. Does not call an LLM.
Does not modify production runtime.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BENCH = REPO / "research" / "llm_benchmarks" / "h4_decision_maker_bench"

import sys

if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))

from adoption_gate import evaluate_adoption_gate, route_final  # noqa: E402
from research.test_improvement_loop.validation_gate import attach_hidden_eval  # noqa: E402


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        did = str(row.get("decision_id") or "")
        if did:
            out[did] = row
    return out


def decision_index(path: Path | None = None) -> dict[str, dict[str, Any]]:
    items = _load_json(path or (BENCH / "packets" / "decisions.json"))
    return {str(d["id"]): d for d in items}


def load_final_row(
    *,
    decision_id: str,
    batch_dir: Path,
    gate_dir: Path | None = None,
) -> dict[str, Any]:
    if gate_dir is not None:
        gp = gate_dir / "gate_results.json"
        if gp.exists():
            recs = _load_json(gp).get("records") or []
            for rec in recs:
                if str(rec.get("decision_id")) == decision_id:
                    block = rec.get("revised") if rec.get("retry_performed") else rec.get("initial")
                    block = block or rec.get("initial") or {}
                    rec_text = str(
                        rec.get("revised_first_recommendation")
                        or rec.get("initial_first_recommendation")
                        or ""
                    )
                    return {
                        "decision_id": decision_id,
                        "first_recommendation": rec_text,
                        "reason": block.get("reason"),
                        "rejected_alternatives": block.get("rejected_alternatives"),
                        "known_issues": block.get("known_issues"),
                        "concrete_failure_scenarios": block.get("concrete_failure_scenarios"),
                        "need_human": rec.get("need_human")
                        if rec.get("retry_performed")
                        else rec.get("need_human"),
                        "uncertainty_score": rec.get("uncertainty")
                        if isinstance(rec.get("uncertainty"), int)
                        else block.get("uncertainty_score"),
                        "uncertainty_reason": block.get("uncertainty_reason"),
                        "needs_deep_review": rec.get("needs_deep_review"),
                    }
    batch = _load_jsonl_by_id(batch_dir / "phase_a_parsed.jsonl")
    row = batch.get(decision_id)
    if row is None:
        raise KeyError(f"no saved recommendation for {decision_id}")
    return row


def score_one(
    *,
    decision_id: str,
    row: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    rec_text = str(row.get("first_recommendation") or "")
    gate = evaluate_adoption_gate(
        row=row,
        decision_id=decision_id,
        heuristic_dangerous=[],
        prior_contradictions=[],
    )
    routing = route_final(
        semantic_gate_result=str(gate.get("semantic_gate_result") or "FAIL"),
        semantic_dangerous=gate.get("semantic_dangerous") or [],
        need_human=bool(row.get("need_human")),
        needs_deep_review=bool(row.get("needs_deep_review")),
        uncertainty_score=row.get("uncertainty_score") if isinstance(row.get("uncertainty_score"), int) else None,
        uncertainty_reason=str(row.get("uncertainty_reason") or ""),
        reason=str(row.get("reason") or ""),
        known_issues=row.get("known_issues"),
        question=str(item.get("question") or ""),
        context=str(item.get("context") or ""),
        recommendation=rec_text,
    )
    out = {
        "decision_id": decision_id,
        "first_recommendation": rec_text,
        "semantic_gate": gate.get("semantic_gate_result"),
        "semantic_dangerous": gate.get("semantic_dangerous") or [],
        "route": routing["route"],
        "notes": routing["notes"],
        "attributes": routing["attributes"],
        "need_human": row.get("need_human"),
        "needs_deep_review": row.get("needs_deep_review"),
        "uncertainty": row.get("uncertainty_score"),
        "parse_failure": bool(row.get("_parse_missing")),
        "missing_output": not rec_text.strip(),
    }
    return attach_hidden_eval([out])[0]


def score_ids(
    ids: list[str],
    *,
    batch_dir: Path,
    gate_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    idx = decision_index()
    records: list[dict[str, Any]] = []
    for did in ids:
        row = None
        last_err: Exception | None = None
        for gd in gate_dirs or []:
            try:
                row = load_final_row(decision_id=did, batch_dir=batch_dir, gate_dir=gd)
                break
            except KeyError as exc:
                last_err = exc
        if row is None:
            row = load_final_row(decision_id=did, batch_dir=batch_dir, gate_dir=None)
        rec = score_one(decision_id=did, row=row, item=idx[did])
        records.append(rec)

    records = attach_hidden_eval(records)

    def n(route: str) -> int:
        return sum(1 for r in records if r["route"] == route)

    false_auto_ids = [
        r["decision_id"] for r in records if (r.get("contract_eval") or {}).get("false_auto")
    ]
    return {
        "summary": {
            "n": len(records),
            "ids": list(ids),
            "AUTO": n("AUTO"),
            "REVIEW": n("REVIEW"),
            "HUMAN": n("HUMAN"),
            "auto_ids": [r["decision_id"] for r in records if r["route"] == "AUTO"],
            "review_ids": [r["decision_id"] for r in records if r["route"] == "REVIEW"],
            "human_ids": [r["decision_id"] for r in records if r["route"] == "HUMAN"],
            "semantic_dangerous_count": sum(1 for r in records if r["semantic_dangerous"]),
            "parse_failure": sum(1 for r in records if r["parse_failure"]),
            "missing_output": sum(1 for r in records if r["missing_output"]),
            "false_auto": len(false_auto_ids),
            "false_auto_ids": false_auto_ids,
        },
        "records": records,
        "llm_called": False,
    }
