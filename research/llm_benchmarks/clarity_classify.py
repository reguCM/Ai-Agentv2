"""
Clarity 判定の機械ラベル。採点ラベルは LLM に渡さない。

status の正誤、質問がユーザー決定事項か、実装手段の丸投げ、
Research 材料がプロンプトに混ざっていないかを分ける。
"""

from tools.system.tool_builder.clarity import next_clarity_step


ALLOWED_MATERIAL_KEYS = frozenset({"target_request", "conversation"})

RESEARCH_FIELD_TOKENS = (
    "usable_findings",
    "insufficient_findings",
    "research_result",
    "evidence.command",
    "rejected_commands",
)

RESEARCH_ANSWER_TOKENS = (
    "win32_operatingsystem",
    "freephysicalmemory",
    "totalvisiblememorysize",
    "get-ciminstance",
    "get-wmiobject",
)

OUTPUT_COMMAND_TOKENS = (
    "get-ciminstance",
    "get-wmiobject",
    "win32_operatingsystem",
    "freephysicalmemory",
    "totalvisiblememorysize",
    "wmic ",
    "subprocess",
    "powershell -",
)

# エージェントが決める実現方法。Clarity の質問に出たら失敗。
DELEGATED_METHOD_TOKENS = (
    "powershell",
    "wmi",
    "cim",
    "python api",
    "task manager",
    "外部コマンド",
)


def _joined_messages(messages):
    parts = []
    for item in messages or []:
        if isinstance(item, dict):
            parts.append(str(item.get("content") or ""))
        else:
            parts.append(str(item))
    return "\n".join(parts)


def _judgment_haystack(judgment, text=""):
    return " ".join(
        [
            str(text or ""),
            str((judgment or {}).get("reason") or ""),
            str((judgment or {}).get("question") or ""),
            str((judgment or {}).get("options") or ""),
        ]
    ).lower()


def inspect_research_isolation(messages, materials):
    """
    Clarity が Research の結果を見ていないこと。
    LLM の判定正誤とは独立。ここが false ならパイプラインの漏れ。
    """
    leaks = []
    extra_keys = sorted(set(materials or {}) - ALLOWED_MATERIAL_KEYS)
    if extra_keys:
        leaks.append({"kind": "material_key", "value": extra_keys})
    joined = _joined_messages(messages)
    lower = joined.lower()
    for token in RESEARCH_FIELD_TOKENS:
        if token.lower() in lower:
            leaks.append({"kind": "research_field", "value": token})
    for token in RESEARCH_ANSWER_TOKENS:
        if token in lower:
            leaks.append({"kind": "research_answer", "value": token})
    return {"ok": not leaks, "leaks": leaks}


def inspect_project_context(messages):
    joined = _joined_messages(messages).lower()
    present = "implementation_method_selection" in joined and "agent" in joined
    return {"ok": present, "present": present}


def invented_command(judgment, text=""):
    haystack = _judgment_haystack(judgment, text)
    return any(token in haystack for token in OUTPUT_COMMAND_TOKENS)


def delegated_method(judgment):
    """質問・options が実現方法の選択になっている。プロンプト本文は見ない。"""
    haystack = " ".join(
        [
            str((judgment or {}).get("reason") or ""),
            str((judgment or {}).get("question") or ""),
            str((judgment or {}).get("options") or ""),
        ]
    ).lower()
    return any(token in haystack for token in DELEGATED_METHOD_TOKENS)


def mentions_expect(judgment, expect_any):
    if not expect_any:
        return True
    haystack = " ".join(
        [
            str((judgment or {}).get("question") or ""),
            str((judgment or {}).get("reason") or ""),
            str((judgment or {}).get("options") or ""),
        ]
    ).lower()
    return any(str(token).lower() in haystack for token in expect_any)


def classify_clarity_trial(
    judgment,
    *,
    expect_status,
    isolation,
    text="",
    expect_any=None,
    context=None,
):
    status = (judgment or {}).get("status")
    step = next_clarity_step(judgment)
    expect_step = "research" if expect_status == "clear" else "ask_user"
    status_ok = status == expect_status
    step_ok = step == expect_step
    isolation_ok = bool((isolation or {}).get("ok"))
    context_ok = True if context is None else bool((context or {}).get("ok"))
    command = invented_command(judgment, text)
    delegated = delegated_method(judgment)
    resolved_without_asking = expect_status != "clear" and status == "clear"
    has_question = bool(str((judgment or {}).get("question") or "").strip()) or bool(
        (judgment or {}).get("options")
    )
    if expect_status == "clear":
        asked_only_when_needed = not has_question
        user_decision_question = not has_question
    else:
        asked_only_when_needed = has_question
        user_decision_question = mentions_expect(judgment, expect_any) and not delegated
    expect_hit = mentions_expect(judgment, expect_any) if has_question or expect_any else True
    handed_to_research = step_ok and isolation_ok and context_ok
    did_not_delegate_method = not delegated
    passed = (
        status_ok
        and asked_only_when_needed
        and user_decision_question
        and did_not_delegate_method
        and handed_to_research
        and not command
    )
    return {
        "status": status,
        "next_step": step,
        "expect_status": expect_status,
        "expect_next_step": expect_step,
        "status_ok": status_ok,
        "next_step_ok": step_ok,
        "asked_only_when_needed": asked_only_when_needed,
        "user_decision_question": user_decision_question,
        "did_not_delegate_method": did_not_delegate_method,
        "handed_to_research": handed_to_research,
        "research_isolated": isolation_ok,
        "context_present": context_ok,
        "invented_command": command,
        "delegated_method": delegated,
        "resolved_without_asking": resolved_without_asking,
        "expect_hit": expect_hit,
        "ok": passed,
        "pass": passed,
    }
