import json

from tools.ai.prompts.base import (
    NEVER_DROP_MATERIAL_KEYS,
    REPAIR_CONTRACT,
    REPAIR_JSON_SHAPE,
)
from tools.ai.prompts.create import (
    CLARITY_CONTRACT,
    CLARITY_JSON_SHAPE,
    IMPLEMENT_CONTRACT,
    IMPLEMENT_JSON_SHAPE,
    PROPOSAL_CONTRACT,
    PROPOSAL_JSON_SHAPE,
    RESEARCH_JUDGE_CONTRACT,
    RESEARCH_JUDGE_JSON_SHAPE,
    WEB_CANDIDATE_CONTRACT,
    WEB_CANDIDATE_JSON_SHAPE,
)
from tools.ai.prompts.context import CONTEXT_CONTRACT
from tools.ai.prompts.state import (
    STATE_CONTRACT,
    STATE_QUERY_CONTRACT,
    STATE_QUERY_JSON_SHAPE,
)
from tools.ai.context.project_context import get_project_context, snapshot_context
from tools.ai.state.task_state import snapshot_state
from tools.system.config import get_llm_profile


WARNING_TEXTS = {
    "unparsed_output": {
        "fix": {
            "en": (
                "Do not change the subprocess execution or stdout capture. "
                "If evidence.parsed_table is present, return its value for that key. "
                "Do not re-parse the table in code. "
                "If extraction fails, do not raise; return a failure value such as {'status':'error'}."
            )
        }
    },
    "meaningless_output": {
        "fix": {
            "en": (
                "Do not return headers, separator lines, or empty text as the value. "
                "If usable_findings.sample contains the value line, return that value line."
            )
        }
    },
    "wrong_output_key": {
        "fix": {"en": "Match the return keys to proposal.output. Do not change the value itself."}
    },
    "return_value_not_dict": {
        "fix": {"en": "Return a dict and use the keys defined in proposal.output."}
    },
    "subprocess_result_handling": {
        "fix": {
            "en": (
                "Use subprocess.run with capture_output=True and text=True, "
                "and check returncode before using stdout."
            )
        }
    },
    "stub_value": {
        "fix": {
            "en": "Implement it only when usable_findings includes both evidence.command and sample."
        }
    },
    "runtime_exception": {
        "fix": {
            "en": (
                "Inspect test_result.error and traceback, then fix the exception. "
                "Do not crash on header or separator parsing. "
                "If usable_findings.sample contains the value line, match that line."
            )
        }
    },
    "wrong_command": {
        "fix": {
            "en": "Replace the current command with the verified command only when research findings verify it."
        }
    },
}


PROMPT_STYLES = {
    "japanese_verbose": {
        "contract_language": "ja",
        "contract_heading": "SYSTEM / CONTRACT",
        "shape_intro": "返す JSON:",
        "contract_intro": "契約:",
        "materials_heading": "TASK MATERIALS",
        "state_heading": "TASK STATE",
        "context_heading": "PROJECT CONTEXT",
        "retry_extra": "JSONオブジェクトだけを出してください。",
        "validation_extra_prefix": "検証 NG。直して JSON だけを出してください。\n",
    },
    "english_compact": {
        "contract_language": "en",
        "contract_heading": "SYSTEM / CONTRACT",
        "shape_intro": "Return this JSON shape:",
        "contract_intro": "Contract:",
        "materials_heading": "TASK MATERIALS",
        "state_heading": "TASK STATE",
        "context_heading": "PROJECT CONTEXT",
        "retry_extra": "Output ONLY the JSON object.",
        "validation_extra_prefix": "Validation NG. Fix and output only JSON.\n",
    },
}


def prompt_style(profile=None):
    profile = profile or get_llm_profile()
    name = profile.get("prompt_style") or "japanese_verbose"
    if name not in PROMPT_STYLES:
        raise KeyError(f"未知の prompt_style: {name}")
    return PROMPT_STYLES[name]


def dumps_json(value, profile=None):
    profile = profile or get_llm_profile()
    spec = profile.get("materials") or {}
    kwargs = {"ensure_ascii": False}
    if spec.get("compact_json"):
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    return json.dumps(value, **kwargs)


def _translate_warning_item(item, lang):
    if not isinstance(item, dict) or lang == "ja":
        return item
    translated = dict(item)
    code = str(item.get("code") or "")
    texts = WARNING_TEXTS.get(code) or {}
    if "fix" in translated and texts.get("fix", {}).get(lang):
        translated["fix"] = texts["fix"][lang]
    return translated


def _translate_materials(materials, lang):
    if lang == "ja":
        return materials
    translated = dict(materials or {})
    for key in ("repairable_warnings", "blocked_warnings"):
        if isinstance(translated.get(key), list):
            translated[key] = [
                _translate_warning_item(item, lang) for item in translated[key]
            ]
    return translated


def render_contract_items(contract, shape, profile=None, extra_items=None):
    """固定契約を PROFILE の言語・密度で出す。項目は消さない。"""
    profile = profile or get_llm_profile()
    style = prompt_style(profile)
    lang = style["contract_language"]
    lines = [
        style["contract_heading"],
        style["shape_intro"],
        dumps_json(shape, profile),
        style["contract_intro"],
    ]
    for item in list(contract) + list(extra_items or []):
        text = item.get(lang) or item["ja"]
        lines.append(f"- {text}")
    return "\n".join(lines)


def render_contract(profile=None):
    return render_contract_items(REPAIR_CONTRACT, REPAIR_JSON_SHAPE, profile)


def prepare_materials(materials, profile=None):
    """
    選ばれた MATERIALS を context 予算に収める。
    契約キーと必須 MATERIALS は drop_keys でも消さない。
    """
    profile = profile or get_llm_profile()
    spec = profile.get("materials") or {}
    lang = prompt_style(profile)["contract_language"]
    prepared = dict(materials or {})
    for key in spec.get("drop_keys") or []:
        if key in NEVER_DROP_MATERIAL_KEYS:
            continue
        prepared.pop(key, None)
    max_chars = spec.get("current_source_max_chars")
    source = prepared.get("current_source")
    if max_chars and isinstance(source, str):
        prepared["current_source"] = source[: int(max_chars)]
    return _translate_materials(prepared, lang)


def render_state(state, profile=None):
    profile = profile or get_llm_profile()
    style = prompt_style(profile)
    payload = snapshot_state(state)
    if payload is None:
        return ""
    return style["state_heading"] + "\n" + dumps_json(payload, profile)


def render_context(context, profile=None):
    profile = profile or get_llm_profile()
    style = prompt_style(profile)
    payload = snapshot_context(context)
    return style["context_heading"] + "\n" + dumps_json(payload, profile)


def render_materials(materials, profile=None):
    profile = profile or get_llm_profile()
    style = prompt_style(profile)
    prepared = prepare_materials(materials, profile)
    return style["materials_heading"] + "\n" + dumps_json(prepared, profile)


def build_repair_messages(materials, extra=None, profile=None, state=None):
    return build_json_messages(
        REPAIR_CONTRACT,
        REPAIR_JSON_SHAPE,
        materials,
        extra=extra,
        profile=profile,
        state=state,
    )


def build_clarity_messages(materials, extra=None, profile=None, state=None, context=None):
    if context is None:
        context = get_project_context()
    return build_json_messages(
        CLARITY_CONTRACT,
        CLARITY_JSON_SHAPE,
        materials,
        extra=extra,
        profile=profile,
        state=state,
        context=context,
    )


def build_proposal_messages(materials, extra=None, profile=None, state=None):
    return build_json_messages(
        PROPOSAL_CONTRACT,
        PROPOSAL_JSON_SHAPE,
        materials,
        extra=extra,
        profile=profile,
        state=state,
    )


def build_web_candidate_messages(materials, extra=None, profile=None, state=None):
    return build_json_messages(
        WEB_CANDIDATE_CONTRACT,
        WEB_CANDIDATE_JSON_SHAPE,
        materials,
        extra=extra,
        profile=profile,
        state=state,
    )


def build_implement_messages(materials, extra=None, profile=None, state=None):
    return build_json_messages(
        IMPLEMENT_CONTRACT,
        IMPLEMENT_JSON_SHAPE,
        materials,
        extra=extra,
        profile=profile,
        state=state,
    )


def build_research_judge_messages(materials, extra=None, profile=None, state=None):
    return build_json_messages(
        RESEARCH_JUDGE_CONTRACT,
        RESEARCH_JUDGE_JSON_SHAPE,
        materials,
        extra=extra,
        profile=profile,
        state=state,
    )


def build_state_query_messages(materials, extra=None, profile=None, state=None):
    return build_json_messages(
        STATE_QUERY_CONTRACT,
        STATE_QUERY_JSON_SHAPE,
        materials,
        extra=extra,
        profile=profile,
        state=state,
    )


def build_json_messages(
    contract, shape, materials, extra=None, profile=None, state=None, context=None
):
    profile = profile or get_llm_profile()
    extra_items = []
    if context is not None:
        extra_items.extend(CONTEXT_CONTRACT)
    if state is not None:
        extra_items.extend(STATE_CONTRACT)
    user_parts = []
    if context is not None:
        user_parts.append(render_context(context, profile))
    if state is not None:
        user_parts.append(render_state(state, profile))
    user_parts.append(render_materials(materials, profile))
    if extra:
        user_parts.append(extra)
    return [
        {
            "role": "system",
            "content": render_contract_items(
                contract, shape, profile, extra_items=extra_items or None
            ),
        },
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def build_repair_prompt(materials, extra=None, profile=None):
    messages = build_repair_messages(materials, extra=extra, profile=profile)
    return "\n\n".join(item["content"] for item in messages)


def retry_extra(profile=None):
    return prompt_style(profile)["retry_extra"]


def exploration_retry_extra(materials, profile=None):
    inventory = materials.get("inventory") or {}
    commands = list(inventory.get("available_commands") or [])
    failed_commands = set()
    for item in (materials.get("prior_failures") or []) + (
        materials.get("rejected_commands") or []
    ):
        command = str(item.get("command") or "").strip().lower()
        if command:
            failed_commands.add(command)
    untried = [
        command
        for command in commands
        if str(command).strip().lower() not in failed_commands
    ]
    lines = [
        prompt_style(profile)["retry_extra"],
        "Your previous candidate repeated a rejected or failed command.",
        "Start a new exploration from inventory.available_commands.",
        "Do not reuse the same command/script as rejected_commands or prior_failures.",
    ]
    if untried:
        lines.append(
            "Use one of these not-yet-tried commands: "
            + ", ".join(str(item) for item in untried)
            + "."
        )
    hints = materials.get("exploration_hints") or []
    if hints:
        lines.append("exploration_hints:")
        lines.extend(f"- {item}" for item in hints[:6])
    return "\n".join(lines)


def validation_extra(errors, profile=None):
    prefix = prompt_style(profile)["validation_extra_prefix"]
    return prefix + json.dumps(errors, ensure_ascii=False)
