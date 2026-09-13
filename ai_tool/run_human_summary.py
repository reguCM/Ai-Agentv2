"""Deterministic Japanese presentation of recorded Agent Run facts."""
from __future__ import annotations

import json
from typing import Any, Mapping


RATINGS = {"GOOD": "良好", "PARTIAL": "一部問題あり", "REVIEW": "要確認", "INCOMPLETE": "未完了"}
CERTAINTY_LABELS = {
    "CONFIRMED": "確認済み",
    "OBSERVED": "実測済み",
    "INFERRED": "推論",
    "HYPOTHESIS": "仮説",
    "UNVERIFIED": "未確認",
}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item and item.strip()))


def build_human_summary(
    record: Mapping[str, Any],
    *,
    task_runtime: Mapping[str, Any],
    turn: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a summary exclusively from persisted Runtime/Recorder facts."""
    goals = list(task_runtime.get("goals") or [])
    tasks = list(task_runtime.get("tasks") or [])
    evidence = list(task_runtime.get("evidence") or [])
    replans = list(task_runtime.get("replans") or [])
    reviews = [
        item
        for item in task_runtime.get("local_reviews") or []
        if isinstance(item, Mapping)
    ]
    root = next((item for item in goals if not item.get("parent_goal_id")), {})
    prompt = str(record.get("prompt") or "").strip()
    purpose_text = str(root.get("title") or prompt or "目的を記録できませんでした")

    accepted_descriptions = {
        str(item.get("description") or "")
        for review in reviews
        for item in review.get("accepted_new_tasks") or []
        if isinstance(item, Mapping)
    }
    decomposition = [
        {
            "task_id": item.get("task_id"),
            "name": item.get("title") or item.get("task_id"),
            "status": item.get("status") or "unknown",
            "purpose": item.get("instruction") or item.get("title"),
            "completion_conditions": list(item.get("completion_conditions") or []),
            "dependencies": list(item.get("depends_on") or []),
            "added_by_local_review": str(item.get("title") or "") in accepted_descriptions,
        }
        for item in tasks
    ]

    requirement = record.get("requirement_decomposition") or {}
    expectation = record.get("tool_expectation") or {}
    approach: list[str] = []
    if requirement:
        approach.append(
            f"Requirement Decompositionを検証し、状態を{requirement.get('status') or '不明'}として扱った"
        )
    if expectation.get("generated"):
        approach.append(f"必要Tool候補として{expectation.get('expected_tool')}を提示した")
    if reviews:
        approach.append(f"Local Reviewを{len(reviews)}回実施し、追加作業の必要性を検証した")
    if replans:
        approach.append(f"Replanを{len(replans)}回記録した")
    recovery_count = int((record.get("runtime") or {}).get("recovery_count") or 0)
    if recovery_count:
        approach.append(f"Recoveryを{recovery_count}回実施した")
    if not approach:
        approach.append("記録されたTaskとTool結果に基づいて処理した")

    execution = []
    for index, item in enumerate(turn.get("tools") or [], 1):
        arguments = dict(item.get("arguments") or {})
        target = arguments.get("path") or arguments.get("url") or arguments.get("query")
        execution.append(
            {
                "sequence": index,
                "type": "tool",
                "tool": item.get("name"),
                "target": target,
                "arguments": arguments,
                "status": item.get("status") or "unknown",
            }
        )
    for review in reviews:
        execution.append(
            {
                "sequence": len(execution) + 1,
                "type": "local_review",
                "iteration": review.get("review_iteration"),
                "status": review.get("final_review_status") or review.get("review_status"),
                "accepted_new_task_count": len(review.get("accepted_new_tasks") or []),
            }
        )
    for item in replans:
        execution.append(
            {
                "sequence": len(execution) + 1,
                "type": "replan",
                "replan_id": item.get("replan_id"),
                "reason": item.get("reason"),
                "status": "recorded",
            }
        )
    if recovery_count:
        execution.append(
            {
                "sequence": len(execution) + 1,
                "type": "recovery",
                "count": recovery_count,
                "status": "recorded",
            }
        )

    conditions = list((record.get("completion_coverage") or {}).get("completion_conditions") or [])
    satisfied = [item for item in conditions if item.get("status") == "SATISFIED"]
    unresolved_conditions = [item for item in conditions if item.get("status") != "SATISFIED"]
    confirmed = [
        {
            "statement": str(item.get("condition")),
            "source": "completion_condition",
            "evidence_ids": list(item.get("supporting_evidence") or []),
        }
        for item in satisfied
    ]
    observed_evidence = [
        {
            "statement": str(item.get("summary")),
            "source": "accepted_evidence",
            "evidence_ids": [item.get("evidence_id")],
            "verified": bool(item.get("verified", True)),
            "certainty": str(item.get("certainty") or "OBSERVED"),
            "certainty_label": CERTAINTY_LABELS["OBSERVED"],
        }
        for item in evidence
        if item.get("summary")
        and item.get("verified", True)
        and str(item.get("certainty") or "OBSERVED") == "OBSERVED"
    ]
    claim_rows = list(record.get("effective_claims") or record.get("claims") or [])
    claims_by_certainty = {
        certainty: [
            {
                "statement": str(item.get("claim") or ""),
                "source": str(item.get("source") or "unknown"),
                "evidence_ids": list(item.get("evidence_ids") or []),
                "verified": bool(item.get("verified")),
                "certainty": certainty,
                "certainty_label": CERTAINTY_LABELS[certainty],
            }
            for item in claim_rows
            if item.get("certainty") == certainty and item.get("claim")
        ]
        for certainty in CERTAINTY_LABELS
    }
    confirmed.extend(claims_by_certainty["CONFIRMED"])
    review_facts = _unique(
        [
            str(fact)
            for review in reviews
            for fact in (review.get("structured_review") or {}).get("facts") or []
        ]
    )
    hypotheses = _unique(
        [
            str(problem)
            for review in reviews
            for problem in (review.get("structured_review") or {}).get("problems") or []
        ]
    )
    missing_evidence = _unique(
        [
            str(item)
            for review in reviews
            for item in (review.get("structured_review") or {}).get("missing_evidence") or []
        ]
    )
    conflicts = _unique(
        [
            str(item)
            for review in reviews
            for item in (review.get("structured_review") or {}).get("conflicts") or []
        ]
    )
    unfinished = [
        {"task_id": item.get("task_id"), "name": item.get("title"), "status": item.get("status")}
        for item in tasks
        if item.get("status") != "complete"
    ]

    runtime = record.get("runtime") or {}
    concept = dict(record.get("concept_resolution") or {})
    capabilities = list(record.get("capability_resolution") or [])
    evaluations = record.get("evaluations") or {}
    approach_code = "PARTIAL" if any(
        int(runtime.get(key) or 0) > 0
        for key in ("stagnation_count", "recovery_count", "replan_count")
    ) else "GOOD"
    decomposition_code = "GOOD" if tasks and conditions else "REVIEW"
    if int((record.get("tool") or {}).get("tool_failure_count") or 0) > 0:
        execution_code = "PARTIAL"
    elif not evidence:
        execution_code = "REVIEW"
    else:
        execution_code = "GOOD"
    output = record.get("output") or {}
    final_goal_status = (record.get("goal") or {}).get("final_goal_status")
    if output.get("final_answer_empty") or unfinished or unresolved_conditions:
        final_code = "INCOMPLETE"
    elif evaluations.get("completion_consistency") == "FAIL":
        final_code = "PARTIAL"
    elif final_goal_status == "complete":
        final_code = "GOOD"
    else:
        final_code = "REVIEW"

    next_actions: list[dict[str, str]] = []
    for review in reviews:
        action = str(
            (review.get("structured_review") or {}).get("recommended_next_action") or ""
        ).strip()
        if action:
            next_actions.append({"description": action, "source": "local_review"})
    for action in (record.get("runtime_status_report") or {}).get("next_actions") or []:
        next_actions.append({"description": str(action), "source": "runtime_status_report"})
    for item in unresolved_conditions:
        next_actions.append(
            {"description": f"未解決条件: {item.get('condition')}", "source": "completion_coverage"}
        )
    current_task_id = task_runtime.get("current_task_id")
    current_task = next((item for item in tasks if item.get("task_id") == current_task_id), None)
    if current_task and current_task.get("status") != "complete":
        next_actions.append(
            {"description": str(current_task.get("title") or current_task_id), "source": "current_task"}
        )
    if concept.get("detected") and concept.get("resolution_status") != "RESOLVED":
        for path in concept.get("look_first") or []:
            if path not in (concept.get("files_checked") or []):
                next_actions.append(
                    {"description": str(path), "source": "concept_resolution.look_first"}
                )
    deduplicated_actions = {
        json.dumps(row, ensure_ascii=False, sort_keys=True): row for row in next_actions
    }

    return {
        "schema_version": 1,
        "language": "ja",
        "purpose": {"summary": purpose_text, "sources": ["user_prompt", "final_goal"]},
        "approach": approach,
        "decomposition": decomposition,
        "concept_resolution": concept,
        "capability_resolution": capabilities,
        "execution": execution,
        "learned": {
            "confirmed": confirmed,
            "observed": observed_evidence + claims_by_certainty["OBSERVED"],
            "inferred": claims_by_certainty["INFERRED"],
            "review_observations_unconfirmed": review_facts,
            "hypotheses": _unique(
                hypotheses
                + [item["statement"] for item in claims_by_certainty["HYPOTHESIS"]]
            ),
            "unverified": claims_by_certainty["UNVERIFIED"],
        },
        "unresolved": {
            "conditions": unresolved_conditions,
            "missing_evidence": missing_evidence,
            "conflicts": conflicts,
            "unfinished_tasks": unfinished,
            "evidence_absent": not bool(evidence),
        },
        "evaluation": {
            "approach": {"rating": RATINGS[approach_code], "code": approach_code},
            "decomposition": {"rating": RATINGS[decomposition_code], "code": decomposition_code},
            "execution": {"rating": RATINGS[execution_code], "code": execution_code},
            "final_result": {"rating": RATINGS[final_code], "code": final_code},
        },
        "next_actions": list(deduplicated_actions.values()),
    }


def _bullets(values: list[str], *, empty: str = "記録なし") -> str:
    return "\n".join(f"- {item}" for item in values) if values else f"- {empty}"


def human_summary_markdown(summary: Mapping[str, Any]) -> str:
    decomposition = summary.get("decomposition") or []
    execution = summary.get("execution") or []
    learned = summary.get("learned") or {}
    unresolved = summary.get("unresolved") or {}
    evaluation = summary.get("evaluation") or {}
    concept = summary.get("concept_resolution") or {}
    capabilities = summary.get("capability_resolution") or []
    task_lines = [
        f"{item.get('task_id')}: {item.get('name')}（状態: {item.get('status')}、完了条件: "
        f"{', '.join(item.get('completion_conditions') or []) or 'なし'}）"
        for item in decomposition
    ]
    execution_lines = []
    for item in execution:
        if item.get("type") == "tool":
            target = f" / 対象: {item.get('target')}" if item.get("target") else ""
            arguments = json.dumps(item.get("arguments") or {}, ensure_ascii=False, sort_keys=True)
            execution_lines.append(
                f"{item.get('sequence')}. {item.get('tool')}（{item.get('status')}）{target} / 引数: {arguments}"
            )
        elif item.get("type") == "local_review":
            execution_lines.append(
                f"{item.get('sequence')}. Local Review {item.get('iteration')}（{item.get('status')}）"
            )
        elif item.get("type") == "replan":
            execution_lines.append(
                f"{item.get('sequence')}. Replan {item.get('replan_id')}（理由: {item.get('reason') or '記録なし'}）"
            )
        elif item.get("type") == "recovery":
            execution_lines.append(
                f"{item.get('sequence')}. Recoveryを{item.get('count')}回実施"
            )
    confirmed = [str(item.get("statement")) for item in learned.get("confirmed") or []]
    observed = [str(item.get("statement")) for item in learned.get("observed") or []]
    inferred = [str(item.get("statement")) for item in learned.get("inferred") or []]
    review_observations = [
        str(item) for item in learned.get("review_observations_unconfirmed") or []
    ]
    hypotheses = [str(item) for item in learned.get("hypotheses") or []]
    unverified = [str(item.get("statement")) for item in learned.get("unverified") or []]
    unknown = [str(item.get("condition")) for item in unresolved.get("conditions") or []]
    unknown += [str(item) for item in unresolved.get("missing_evidence") or []]
    unknown += [f"競合: {item}" for item in unresolved.get("conflicts") or []]
    unknown += [
        f"未完了Task: {item.get('task_id')} {item.get('name')}（{item.get('status')}）"
        for item in unresolved.get("unfinished_tasks") or []
    ]
    if unresolved.get("evidence_absent"):
        unknown.append("採用済みEvidenceは0件です")
    evaluation_lines = [
        f"{label}: {(evaluation.get(key) or {}).get('rating', '要確認')}"
        for key, label in (
            ("approach", "進め方"),
            ("decomposition", "作業の分け方"),
            ("execution", "実行内容"),
            ("final_result", "最終結果"),
        )
    ]
    next_lines = [str(item.get("description")) for item in summary.get("next_actions") or []]
    if concept.get("detected"):
        concept_lines = [
            f"未知の用語: {concept.get('concept')}",
            f"確認状態: {concept.get('resolution_status')}",
            "確認した場所: " + (", ".join(concept.get("files_checked") or []) or "なし"),
            f"分かった意味: {concept.get('resolved_definition') or '定義を確認できず'}",
        ]
    else:
        concept_lines = ["未知概念の確認は不要でした"]
    capability_lines = []
    for item in capabilities:
        if not item.get("required_capability"):
            continue
        capability_lines.extend(
            [
                f"必要だった能力: {item.get('required_capability')}",
                "確認した既存Tool: " + (", ".join(item.get("existing_candidates") or []) or "なし"),
                f"結果: {item.get('status')}",
            ]
        )
        if item.get("missing_capability"):
            capability_lines.append(f"不足している能力: {item.get('missing_capability')}")
        if item.get("suggested_minimal_tool"):
            capability_lines.append(f"次の候補: {item.get('suggested_minimal_tool')}（Human Approval待ち）")
    if not capability_lines:
        capability_lines = ["Capability解決は不要でした"]
    return f"""# 日本語Run要約

## 今回の目的

{summary.get('purpose', {}).get('summary') or '記録なし'}

## 今回の進め方

{_bullets(list(summary.get('approach') or []))}

## 未知概念の確認

{_bullets(concept_lines)}

## Capability確認

{_bullets(capability_lines)}

## 作業の分け方

{_bullets(task_lines)}

## 実際に行ったこと

{_bullets(execution_lines, empty='Tool実行・Reviewの記録なし')}

## 分かったこと

確定したこと:
{_bullets(confirmed, empty='確定済みの事実なし')}

実測済み:
{_bullets(observed, empty='なし')}

推論:
{_bullets(inferred, empty='なし')}

Local Reviewによる観測候補（未確定）:
{_bullets(review_observations, empty='なし')}

仮説:
{_bullets(hypotheses, empty='なし')}

未確認:
{_bullets(_unique(unverified + review_observations), empty='なし')}

## 分からなかったこと

{_bullets(_unique(unknown), empty='記録上の未解決事項なし')}

## 今回の評価

{_bullets(evaluation_lines)}

## 次にやること

{_bullets(_unique(next_lines), empty='記録された次Actionなし')}
"""


__all__ = ["build_human_summary", "human_summary_markdown"]
