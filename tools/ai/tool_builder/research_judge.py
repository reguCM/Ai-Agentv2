def compact_finding(item):
    item = item or {}
    evidence = item.get("evidence") or {}
    return {
        "question": item.get("question"),
        "finding": item.get("finding"),
        "command": evidence.get("command"),
        "args": evidence.get("args") or [],
        "sample": evidence.get("sample") or [],
        "confidence": item.get("confidence"),
        "source": item.get("source"),
        "insufficient_reason": item.get("insufficient_reason"),
    }


def _truncate(text, max_len):
    if not text or len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def compact_insufficient_finding(item, *, max_reason=120, max_question=120, max_sample=3):
    """insufficient_findings 用の圧縮版。Judge が reject 理由を把握できる最小情報を残す。"""
    base = compact_finding(item)
    base["insufficient_reason"] = _truncate(
        base.get("insufficient_reason"), max_reason
    )
    base["question"] = _truncate(base.get("question"), max_question)
    sample = base.get("sample") or []
    if isinstance(sample, list) and len(sample) > max_sample:
        base["sample"] = sample[:max_sample]
    return base


def _error_texts_equivalent(left, right):
    left = str(left or "").strip()
    right = str(right or "").strip()
    if not left or not right:
        return False
    return left == right or left in right or right in left


def compact_unresolved_finding(
    item, *, max_finding=200, max_error=120, max_question=120, max_sample=3
):
    """Judge MATERIALS 用 unresolved。research/STATE の原文は変更しない。"""
    item = item or {}
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    evidence = evidence or {}

    compact_evidence = {}
    if evidence.get("command") not in (None, ""):
        compact_evidence["command"] = evidence.get("command")
    args = evidence.get("args")
    if args is not None:
        compact_evidence["args"] = list(args or [])
    if "returncode" in evidence:
        compact_evidence["returncode"] = evidence.get("returncode")
    if evidence.get("output_key") not in (None, ""):
        compact_evidence["output_key"] = evidence.get("output_key")

    sample = evidence.get("sample") or []
    if isinstance(sample, list):
        compact_evidence["sample"] = sample[:max_sample]
    else:
        compact_evidence["sample"] = sample

    error = str(evidence.get("error") or "").strip()
    stderr = str(evidence.get("stderr") or "").strip()
    if error:
        compact_evidence["error"] = _truncate(error, max_error)
    elif stderr:
        compact_evidence["error"] = _truncate(stderr, max_error)
    if stderr and not _error_texts_equivalent(stderr, error):
        compact_evidence["stderr"] = _truncate(stderr, max_error)

    for key in ("platform", "available_modules", "missing_modules", "available_commands"):
        if key in evidence:
            compact_evidence[key] = evidence[key]

    return {
        "kind": item.get("kind"),
        "question": _truncate(item.get("question"), max_question),
        "finding": _truncate(item.get("finding"), max_finding),
        "evidence": compact_evidence,
        "confidence": item.get("confidence"),
        "source": item.get("source"),
    }


def _decision_value(state, key):
    if state is None:
        return None
    decisions = getattr(state, "decisions", None)
    if decisions is None and isinstance(state, dict):
        decisions = state.get("decisions")
    for item in decisions or []:
        if isinstance(item, dict) and item.get("key") == key:
            value = item.get("value")
            if value not in (None, ""):
                return str(value).strip()
    return None


def _sample_numbers(sample):
    values = []
    for item in sample or []:
        text = str(item or "").strip()
        if not text:
            continue
        if text.endswith("%"):
            text = text[:-1].strip()
        try:
            values.append(float(text))
        except ValueError:
            continue
    return values


def build_judging_hints(state, research_result):
    hints = []
    research_result = research_result or {}
    unit = _decision_value(state, "status.unit")
    meaning = _decision_value(state, "status.meaning")
    usable = list(research_result.get("usable_findings") or [])
    percent_samples = []
    for item in usable:
        numbers = _sample_numbers(compact_finding(item).get("sample"))
        percent_samples.extend(num for num in numbers if 0 <= num <= 100)
    if usable and percent_samples and unit == "%":
        sample_text = ", ".join(str(item) for item in percent_samples[:3])
        hints.append(
            f"usable_findings sample has numeric value(s) in 0-100: {sample_text}."
        )
        if meaning:
            hints.append(
                f"STATE status.meaning={meaning}, status.unit={unit} are confirmed."
            )
        hints.append(
            "This sample may set satisfies_request true as a measured usage rate (%)."
        )
        hints.append(
            "When sample is a single 0-100 number, it is the command output after calculation, not raw byte counts needing another conversion."
        )
        hints.append(
            "finding.question is a prior-round gap label; do not treat question wording as the sample kind."
        )
        hints.append(
            "When this sample may be accepted, set satisfies_request true and leave missing empty."
        )
    elif usable and percent_samples:
        sample_text = ", ".join(str(item) for item in percent_samples[:3])
        hints.append(
            f"usable_findings sample has numeric value(s) in 0-100: {sample_text}."
        )
    unresolved = list(research_result.get("unresolved") or [])
    if not usable and unresolved:
        empty_or_error = False
        for item in unresolved:
            evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
            sample = evidence.get("sample")
            if not sample or evidence.get("error"):
                empty_or_error = True
                break
        if empty_or_error:
            hints.append(
                "usable_findings is empty and unresolved has verify failure."
            )
            hints.append(
                "In missing, name unconfirmed measurement targets needed for the request "
                "(for example total physical memory, used memory)."
            )
            hints.append(
                "Do not ask to investigate commands, scripts, or the correct method."
            )
    return hints


def create_research_judgment(request, proposal, research_result, state=None):
    """
    調査結果が要求を満たすかの判断材料。
    正解コマンドは入れない。実装コードも要求しない。
    """

    research_result = research_result or {}
    proposal = proposal or {}
    payload = {
        "target_request": request,
        "output": proposal.get("output") or ["status"],
        "usable_findings": [
            compact_finding(item)
            for item in research_result.get("usable_findings") or []
        ],
        "insufficient_findings": [
            compact_insufficient_finding(item)
            for item in research_result.get("insufficient_findings") or []
        ],
        "unresolved": [
            compact_unresolved_finding(item)
            for item in research_result.get("unresolved") or []
        ],
    }
    hints = build_judging_hints(state, research_result)
    if hints:
        payload["judging_hints"] = hints
    return payload


def items_from_missing(missing, start_id=1):
    items = []
    for offset, question in enumerate(missing or []):
        text = str(question or "").strip()
        if not text:
            continue
        items.append(
            {
                "id": start_id + offset,
                "kind": "output",
                "question": text,
                "followup": True,
            }
        )
    return items


def prepare_followup_research(missing, research=None, *, reason=None, state=None):
    """
    Judge の missing から次ラウンド Research へ渡す材料を組み立てる。

    Phase 5: Memory Recall ON のとき prior_failures / rejected_commands /
    judge_reason は再掲しない（History + RecallPolicy が都度想起）。
    """
    from tools.ai.state.memory_recall import banned_digest, memory_recall_enabled
    from tools.ai.tool_builder.research_result import (
        compact_prior_failures,
        rejected_command_list,
    )

    items = items_from_missing(missing)
    payload = {
        "research_items": items,
        "followup_questions": [item["question"] for item in items],
    }
    if memory_recall_enabled():
        # 機械フィルタ用に banned だけ短く渡せる（LLM へのフル PF はしない）
        payload["rejected_commands"] = banned_digest(state, limit=12) if state else []
        payload["prior_failures"] = []
        payload["judge_reason"] = ""
        payload["memory_recall"] = True
    else:
        payload["rejected_commands"] = rejected_command_list(research)
        payload["prior_failures"] = compact_prior_failures(research)
        payload["judge_reason"] = str(reason or "").strip()
        payload["memory_recall"] = False
    return payload


def normalize_judgment(payload):
    if not isinstance(payload, dict):
        return {"satisfies_request": False, "reason": "", "missing": [], "proposed_decisions": []}
    flag = payload.get("satisfies_request")
    if isinstance(flag, str):
        flag = flag.strip().lower() in ("true", "1", "yes")
    missing = payload.get("missing") or []
    if isinstance(missing, str):
        missing = [missing]
    missing = [str(item).strip() for item in missing if str(item).strip()]
    reason = str(payload.get("reason") or "").strip()
    if not flag and not missing and reason:
        missing = [reason]
    proposed = payload.get("proposed_decisions") or []
    if isinstance(proposed, dict):
        proposed = [proposed]
    if not isinstance(proposed, list):
        proposed = []
    cleaned = []
    for item in proposed:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        value = item.get("value")
        if not key or value in (None, ""):
            continue
        cleaned.append({"key": key, "value": value})
    return {
        "satisfies_request": bool(flag),
        "reason": reason,
        "missing": missing,
        "proposed_decisions": cleaned,
    }
