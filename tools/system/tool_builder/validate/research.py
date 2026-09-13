ALLOWED_RESEARCH_STATUS = (
    "completed",
    "partial",
    "fail",
)

ALLOWED_CONFIDENCE = (
    "high",
    "medium",
    "low",
)

ALLOWED_SOURCE = (
    "local",
    "web",
    "mixed",
)

REQUIRED_RESULT_KEYS = (
    "question",
    "finding",
    "evidence",
    "confidence",
)


def check_envelope(payload):
    errors = []
    warnings = []

    if not payload:
        errors.append("調査結果がありません")
        return errors, warnings

    status = payload.get("status")
    if status not in ALLOWED_RESEARCH_STATUS:
        errors.append(
            f"status は {list(ALLOWED_RESEARCH_STATUS)} のいずれかにしてください: {status}"
        )

    source = payload.get("source")
    if source and source not in ALLOWED_SOURCE:
        errors.append(
            f"source は {list(ALLOWED_SOURCE)} のいずれかにしてください: {source}"
        )

    if not isinstance(payload.get("results"), list):
        errors.append("results がリストではありません")

    return errors, warnings


def check_result_item(item, index):
    errors = []
    warnings = []
    prefix = f"results[{index}]"

    if not isinstance(item, dict):
        errors.append(f"{prefix} が dict ではありません")
        return errors, warnings

    for key in REQUIRED_RESULT_KEYS:
        if key not in item:
            errors.append(f"{prefix}.{key} がありません")

    if item.get("confidence") and item.get("confidence") not in ALLOWED_CONFIDENCE:
        errors.append(
            f"{prefix}.confidence は {list(ALLOWED_CONFIDENCE)} のいずれかにしてください: "
            f"{item.get('confidence')}"
        )

    if item.get("source") and item.get("source") not in ALLOWED_SOURCE:
        errors.append(
            f"{prefix}.source は {list(ALLOWED_SOURCE)} のいずれかにしてください: "
            f"{item.get('source')}"
        )

    finding = item.get("finding")
    if finding is not None and not str(finding).strip():
        errors.append(f"{prefix}.finding が空です")

    if item.get("evidence") in (None, "", [], {}):
        errors.append(f"{prefix}.evidence が空です")

    if item.get("source") == "web" and not (item.get("evidence") or {}).get("command"):
        warnings.append(f"{prefix} は未検証の Web検索ヒットです")

    return errors, warnings


def check_coverage(payload, expected_items=None):
    errors = []
    warnings = []
    expected_items = expected_items or []
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return errors, warnings

    actual_questions = [
        item.get("question")
        for item in results
        if isinstance(item, dict)
    ]
    for item in expected_items:
        if not isinstance(item, dict):
            continue
        question = item.get("question")
        if question and question not in actual_questions:
            errors.append(f"調査項目が結果にありません: {question}")

    return errors, warnings


def research_result_validator(research_execution=None, research_items=None):
    """
    調査結果が信用できる形式か機械的に確認する。
    再調査はしない。
    """

    research_execution = research_execution or {}
    research_items = research_items or []

    errors, warnings = check_envelope(research_execution)
    results = research_execution.get("results")
    if isinstance(results, list):
        for index, item in enumerate(results):
            item_errors, item_warnings = check_result_item(item, index)
            errors.extend(item_errors)
            warnings.extend(item_warnings)

    coverage_errors, coverage_warnings = check_coverage(
        research_execution,
        expected_items=research_items,
    )
    errors.extend(coverage_errors)
    warnings.extend(coverage_warnings)

    if errors:
        status = "fail"
        result = "NG"
    elif warnings:
        status = "warning"
        result = "OK"
    else:
        status = "pass"
        result = "OK"

    return {
        "result": result,
        "status": status,
        "source": research_execution.get("source"),
        "execution_status": research_execution.get("status"),
        "errors": errors,
        "warnings": warnings,
        "result_count": len(results) if isinstance(results, list) else 0,
    }
