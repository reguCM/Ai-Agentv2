"""Build External Help Request packages for NH14 — no cause fixation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _facts_from_materials(materials: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    runtime = str(materials.get("runtime_log") or "")
    if "[OBSERVED]" in runtime:
        for line in runtime.splitlines():
            if "[OBSERVED]" in line:
                facts.append(line.strip()[:500])
    if materials.get("state_context"):
        facts.append(f"state_context: {str(materials['state_context'])[:300]}")
    if materials.get("evidence"):
        facts.append(f"evidence field present (not interpreted): {str(materials['evidence'])[:200]}")
    return facts[:20]


def _suspected_causes(features: dict[str, Any], gate: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    if features.get("suspect_ranking_vs_filter"):
        candidates.append({"hypothesis": "ranking/filter confusion", "status": "candidate_not_confirmed"})
    if features.get("suspect_stdout_vs_llm_handoff"):
        candidates.append({"hypothesis": "stdout vs handoff mismatch", "status": "candidate_not_confirmed"})
    if gate.get("reasons"):
        for r in gate.get("reasons") or []:
            if r.startswith("real_log_"):
                candidates.append({"hypothesis": r, "status": "rule_triggered_not_root_cause"})
    if not candidates:
        candidates.append({"hypothesis": "UNKNOWN", "status": "insufficient_evidence"})
    return candidates


def build_external_help_package(
    record: dict[str, Any],
    out_dir: Path,
) -> Path:
    case_id = record["case_id"]
    pkg = out_dir / case_id
    pkg.mkdir(parents=True, exist_ok=True)
    materials = (record.get("materials") or record.get("input_materials") or {})
    features = (record.get("fingerprint") or {}).get("features") or {}
    gate = record.get("gate") or {}
    validation = record.get("validation") or {}
    sel = record.get("selector_output") or {}

    request = {
        "case_id": case_id,
        "kind": "external_diagnostic_request",
        "shadow_mode": True,
        "auto_fix_allowed": False,
        "classification": record.get("final_classification"),
        "gate_level": gate.get("nh14_level"),
        "constraints": [
            "Do not modify production code",
            "Do not fix cause by guess alone",
            "Do not fabricate evidence",
            "UNKNOWN is acceptable",
        ],
    }
    (pkg / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pkg / "OBSERVATION.json").write_text(
        json.dumps(record.get("observation_flat") or {}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (pkg / "FINGERPRINT.json").write_text(
        json.dumps(record.get("fingerprint") or {}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (pkg / "VALIDATION.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (pkg / "GATE.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pkg / "SELECTOR.json").write_text(json.dumps(sel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    evid_dir = pkg / "EVIDENCE"
    evid_dir.mkdir(exist_ok=True)
    if materials.get("runtime_log"):
        (evid_dir / "runtime_log.txt").write_text(str(materials["runtime_log"]), encoding="utf-8")
    if materials.get("raw_api_digest"):
        (evid_dir / "raw_api_digest.json").write_text(
            str(materials["raw_api_digest"]), encoding="utf-8"
        )

    code_dir = pkg / "CODE_CONTEXT"
    code_dir.mkdir(exist_ok=True)
    if materials.get("code_excerpt"):
        (code_dir / "code_excerpt.txt").write_text(str(materials["code_excerpt"]), encoding="utf-8")

    state_hist = materials.get("state_history") or materials.get("state_context") or ""
    (pkg / "STATE_HISTORY.json").write_text(
        json.dumps({"state_context": materials.get("state_context"), "state_history": materials.get("state_history")}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    facts = _facts_from_materials(materials)
    suspects = _suspected_causes(features, gate)
    summary = f"""# External Diagnostic Request

## Task

原因調査をしてください。自動修正は禁止です。

## Observed Problem

{materials.get('problem_summary', '（材料に problem_summary なし）')}

## Confirmed Facts

{chr(10).join('- ' + f for f in facts) if facts else '- （観測事実は OBSERVATION.json を参照）'}

## Suspected Causes (not confirmed)

{chr(10).join(f"1. {s['hypothesis']} ({s['status']})" for s in suspects)}

## Evidence

See `EVIDENCE/` and `CODE_CONTEXT/`.

## Rejected Explanations

- auto_fix: NOT_ALLOWED
- Large LLM auto-diagnosis: SKIPPED (NH14)

## Uncertainty

Gate level: {gate.get('nh14_level')}  
Reasons: {', '.join(gate.get('nh14_reasons') or [])}

## Questions

1. 何を確認してほしいか: {gate.get('high_slot_names') or 'slot/経路の実測確認'}
2. 現在の有力候補: {', '.join(s['hypothesis'] for s in suspects[:3])}
3. 何が不足しているか: 根拠付きの因果確定
4. 人間/Cursorに委ねる判断: {record.get('final_classification')}

## Constraints

- 本番コードを変更しない
- 原因を推測だけで確定しない
- Evidenceを捏造しない
- UNKNOWNを許容する
"""
    (pkg / "SUMMARY.md").write_text(summary, encoding="utf-8")
    return pkg
