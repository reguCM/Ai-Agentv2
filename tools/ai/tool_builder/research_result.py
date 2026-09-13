USABLE_CONFIDENCE = ("high",)
REFERENCE_CONFIDENCE = ("medium",)
UNRESOLVED_CONFIDENCE = ("low",)


def command_key(item):
    item = item or {}
    evidence = item.get("evidence") if "evidence" in item else item
    evidence = evidence or {}
    command = str(evidence.get("command") or item.get("command") or "")
    args = evidence.get("args") if evidence.get("args") is not None else item.get("args")
    return (command, tuple(str(arg) for arg in (args or [])))


def compact_finding(item):
    item = item or {}
    return {
        "kind": item.get("kind"),
        "question": item.get("question"),
        "finding": item.get("finding"),
        "evidence": item.get("evidence"),
        "confidence": item.get("confidence"),
        "source": item.get("source") or "local",
    }


def split_findings(findings):
    usable_findings = []
    reference_findings = []
    unresolved = []

    for item in findings:
        confidence = item.get("confidence")
        if confidence in USABLE_CONFIDENCE:
            usable_findings.append(item)
        elif confidence in REFERENCE_CONFIDENCE:
            reference_findings.append(item)
        else:
            unresolved.append(item)

    return usable_findings, reference_findings, unresolved


def empty_payload(result="NG", status="fail", error=None):
    payload = {
        "result": result,
        "status": status,
        "findings": [],
        "usable_findings": [],
        "reference_findings": [],
        "unresolved": [],
        "insufficient_findings": [],
    }
    if error:
        payload["error"] = error
    return payload


def research_result(research_execution=None, validation_result=None):
    """
    検証済みの調査結果を、実装・修正用の材料にまとめる。
    コード生成やファイル変更は行わない。

    confidence:
    - high → usable_findings（実装事実として利用可能）
    - medium → reference_findings（参考情報。実装根拠にしない）
    - low → unresolved（未解決）
    """

    research_execution = research_execution or {}
    validation_result = validation_result or {}

    if validation_result.get("result") != "OK":
        return empty_payload(
            error="調査結果の検証が OK ではありません",
        )

    findings = [
        compact_finding(item)
        for item in research_execution.get("results") or []
        if isinstance(item, dict)
    ]
    usable_findings, reference_findings, unresolved = split_findings(findings)

    return {
        "result": "OK",
        "status": research_execution.get("status") or "completed",
        "source": research_execution.get("source") or "local",
        "subject": research_execution.get("subject") or {},
        "findings": findings,
        "usable_findings": usable_findings,
        "reference_findings": reference_findings,
        "unresolved": unresolved,
        "rules": [
            "usable_findings（confidence=high）だけを実装の事実として使うこと。",
            "reference_findings（confidence=medium）は参考情報であり、実装根拠にしないこと。",
            "コマンドやライブラリの存在確認だけでは、取得方法を実装しないこと。",
            "具体的な取得方法と戻り値が usable_findings にあるときだけ実装すること。",
            "usable_findings の evidence.command / sample があるとき、それを取得方法の根拠にすること。",
            "unresolved（confidence=low）は未実装のままにすること。",
            "findings にないライブラリ・コマンド・値を想像しないこと。",
            "成功に見える未確認の値を埋めないこと。",
            "ファイル作成はしないこと。",
        ],
        "insufficient_findings": [],
    }


def mark_insufficient(research, findings, reason=None):
    research = dict(research or {})
    insufficient = list(research.get("insufficient_findings") or [])
    remove_keys = {command_key(item) for item in findings or []}
    kept_usable = []
    for item in research.get("usable_findings") or []:
        if command_key(item) in remove_keys:
            marked = dict(item)
            if reason:
                marked["insufficient_reason"] = reason
            insufficient.append(marked)
        else:
            kept_usable.append(item)
    research["usable_findings"] = kept_usable
    research["insufficient_findings"] = insufficient
    return research


def merge_packed_research(base, extra):
    base = dict(base or empty_payload(result="OK", status="completed"))
    extra = extra or {}
    rejected = {command_key(item) for item in base.get("insufficient_findings") or []}
    usable = list(base.get("usable_findings") or [])
    seen = {command_key(item) for item in usable}
    for item in extra.get("usable_findings") or []:
        key = command_key(item)
        if key in rejected or key in seen:
            continue
        usable.append(item)
        seen.add(key)
    base["usable_findings"] = usable
    base["reference_findings"] = list(extra.get("reference_findings") or [])
    base["unresolved"] = list(extra.get("unresolved") or [])
    base["findings"] = list(base.get("findings") or []) + list(
        extra.get("findings") or []
    )
    return base


def filter_rejected_candidates(candidates, rejected_commands, *, banned_actions=None):
    """
    rejected_commands と state.banned_actions の両方で候補を除外する。
    Phase 5: banned_actions を正ソースにできる。
    """
    from tools.system.tool_builder.research.verify import normalize_candidate

    rejected = set()
    for item in list(rejected_commands or []) + list(banned_actions or []):
        if not isinstance(item, dict):
            continue
        normalized = normalize_candidate(item) if "command" in item else None
        rejected.add(command_key(normalized or item))
    kept = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        normalized = normalize_candidate(candidate)
        if not normalized:
            continue
        if command_key(normalized) in rejected:
            continue
        kept.append(normalized)
    return kept


def _truncate_prior_text(text, max_len=200):
    text = str(text or "")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def compact_prior_failures(research):
    failures = []
    seen = set()
    for bucket in ("unresolved", "insufficient_findings"):
        for item in (research or {}).get(bucket) or []:
            command, args = command_key(item)
            if not command or (command, args) in seen:
                continue
            seen.add((command, args))
            evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
            failures.append(
                {
                    "question": _truncate_prior_text(item.get("question"), 120),
                    "command": command,
                    "args": list(args),
                    "error": _truncate_prior_text(evidence.get("error")),
                    "finding": _truncate_prior_text(item.get("finding")),
                }
            )
    return failures


def rejected_command_list(research):
    result = []
    seen = set()
    for bucket in ("insufficient_findings", "unresolved"):
        for item in (research or {}).get(bucket) or []:
            command, args = command_key(item)
            if not command or (command, args) in seen:
                continue
            seen.add((command, args))
            result.append({"command": command, "args": list(args)})
    return result
