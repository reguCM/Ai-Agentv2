ACTION_REPAIR = "repair"
ACTION_BLOCKED = "blocked"
ACTION_ACCEPTABLE = "acceptable"

NEXT_BY_ACTION = {
    ACTION_REPAIR: "repair_tool",
    ACTION_BLOCKED: "research",
    ACTION_ACCEPTABLE: "none",
}


def unique_texts(values):
    seen = set()
    result = []
    for value in values or []:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def proposal_unconfirmed_notes(proposal):
    return [
        str(note)
        for note in (proposal or {}).get("implementation_notes") or []
        if "未確認" in str(note)
    ]


def proposal_unconfirmed_dependencies(proposal):
    return [
        str(dep)
        for dep in (proposal or {}).get("dependencies") or []
        if "未確認" in str(dep)
    ]


def proposal_platforms(proposal):
    runtime = (proposal or {}).get("runtime") or {}
    platforms = runtime.get("platform") or []
    if isinstance(platforms, str):
        platforms = [platforms]
    return [str(item) for item in platforms if str(item).strip()]


def stub_required_information(proposal, stub_keys, unimplemented=None):
    required = []
    proposal = proposal or {}
    subject = (
        proposal.get("subcategory")
        or proposal.get("category")
        or proposal.get("name")
    )
    if subject:
        required.append(
            f"{subject} のメトリクスを取得できるライブラリまたはコマンド"
        )

    stub_keys = stub_keys or []
    for key in stub_keys:
        required.append(f"output '{key}' の取得方法")

    for item in unimplemented or []:
        if item in stub_keys:
            continue
        required.append(f"unimplemented '{item}' の取得方法")

    required.extend(proposal_unconfirmed_notes(proposal))

    deps = proposal_unconfirmed_dependencies(proposal)
    if any(dep == "未確認" for dep in deps):
        required.append("dependencies として使えるライブラリまたはコマンド")
    else:
        for dep in deps:
            required.append(f"dependency の利用可否: {dep}")

    platforms = proposal_platforms(proposal)
    if platforms:
        required.append(
            "その取得手段の platform 対応状況: " + ", ".join(platforms)
        )

    return unique_texts(required)


def warning_item(
    code,
    message,
    action,
    reason=None,
    required_information=None,
    evidence=None,
    next_step=None,
    fix=None,
    needs_research_findings=False,
):
    return {
        "code": code,
        "message": message,
        "action": action,
        "status": action,
        "reason": reason or "",
        "required_information": unique_texts(required_information),
        "evidence": evidence or {},
        "next": next_step if next_step is not None else NEXT_BY_ACTION.get(action, "none"),
        "fix": fix or "",
        "needs_research_findings": bool(needs_research_findings),
    }


def collect_warning_items(checks):
    items = []
    for check_name, result in (checks or {}).items():
        for item in result.get("warning_items") or []:
            items.append({**item, "check": check_name})
    return items


def build_research_request(blocked_items):
    research_items = [
        item
        for item in blocked_items or []
        if item.get("next") == "research"
    ]
    if not research_items:
        return None

    reasons = unique_texts(item.get("reason") for item in research_items)
    required = []
    for item in research_items:
        required.extend(item.get("required_information") or [])

    return {
        "status": ACTION_BLOCKED,
        "reason": "; ".join(reasons),
        "required_information": unique_texts(required),
        "codes": [item.get("code") for item in research_items],
    }


def summarize_disposition(warning_items):
    repairable = []
    blocked = []
    acceptable = []

    for item in warning_items or []:
        action = item.get("action")
        if action == ACTION_REPAIR:
            repairable.append(item)
        elif action == ACTION_BLOCKED:
            blocked.append(item)
        else:
            acceptable.append(item)

    if repairable:
        next_action = ACTION_REPAIR
    elif blocked:
        next_action = ACTION_BLOCKED
    else:
        next_action = ACTION_ACCEPTABLE if acceptable else "none"

    research_request = build_research_request(blocked)
    if next_action == ACTION_REPAIR:
        next_step = "repair_tool"
    elif research_request:
        next_step = "research"
    elif blocked:
        nexts = unique_texts(item.get("next") for item in blocked)
        next_step = nexts[0] if nexts else "none"
    else:
        next_step = NEXT_BY_ACTION.get(next_action, "none")

    return {
        "next_action": next_action,
        "next": next_step,
        "repairable": repairable,
        "blocked": blocked,
        "acceptable": acceptable,
        "research_request": research_request,
    }


def finalize_validation_status(errors, disposition, *, treat_repairable_as_fail=False):
    """
    エージェント状態:
    - pass: 完了
    - warning: 許容できる指摘のみ
    - fail: やり方は分かっているが、コードが間違っている
    - blocked: 実装に必要な情報がまだない
    """

    disposition = disposition or {}

    if errors:
        return "NG", "fail"
    if disposition.get("repairable") and treat_repairable_as_fail:
        return "NG", "fail"
    if disposition.get("research_request"):
        return "OK", "blocked"
    if (
        disposition.get("repairable")
        or disposition.get("acceptable")
        or disposition.get("blocked")
    ):
        return "OK", "warning"
    return "OK", "pass"


def get_disposition(result_validation):
    return (result_validation or {}).get("disposition") or {}


def needs_repair(result_validation):
    if not result_validation:
        return False
    if result_validation.get("status") == "fail":
        return True
    if result_validation.get("result") == "NG":
        return True
    return get_disposition(result_validation).get("next_action") == ACTION_REPAIR


def is_blocked_on_info(result_validation):
    if not result_validation:
        return False
    if result_validation.get("status") == "blocked":
        return True
    return bool(get_disposition(result_validation).get("research_request"))


def is_implementation_complete(result_validation):
    return (result_validation or {}).get("status") == "pass"


def research_has_verified_method(research_result):
    for item in (research_result or {}).get("usable_findings") or []:
        evidence = item.get("evidence") or {}
        if evidence.get("command") and evidence.get("sample"):
            return True
    return False


def first_pipeline_step(result_validation, *, has_verified_method=False):
    """
    validate_tool_result の直後に進む分岐。
    repair と research が両方あるときは repair を先にする。
    """

    if is_implementation_complete(result_validation) and not needs_repair(
        result_validation
    ):
        return "pass"

    disposition = get_disposition(result_validation)
    repairable = disposition.get("repairable") or []
    needs_findings = any(
        item.get("needs_research_findings") for item in repairable
    )
    ready = (
        has_verified_method
        or bool((result_validation or {}).get("research_ready"))
        or (needs_findings and research_has_verified_method(
            (result_validation or {}).get("research_result")
        ))
    )

    if needs_repair(result_validation) and is_blocked_on_info(result_validation):
        return "repair"
    if needs_repair(result_validation) and needs_findings:
        return "research_repair" if ready else "research"
    if needs_repair(result_validation):
        return "repair"
    if is_blocked_on_info(result_validation):
        return "research_repair" if ready else "research"
    return "pass"
