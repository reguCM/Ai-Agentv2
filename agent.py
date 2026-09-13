import json
import importlib
import inspect
import os
import platform
import subprocess
import sys
from tools.system.tool_builder.search import (
    search_tools,
    find_reference_tools,
    load_tool_source,
)
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.llm import chat
from tools.ai.llm.adapter import build_clarity_messages
from tools.ai.state.task_state import TaskState, snapshot_state
from tools.ai.agent_runtime import AgentRuntime, AgentRuntimeState
from tools.system.tool_result_contract import normalize_tool_result
from tools.system.tool_builder.clarity import (
    format_clarity_question,
    run_clarity_gate,
)

from tools.system.tool_builder.validate.spec import (
    ALLOWED_CATEGORIES,
    validate_tool_spec,
)
from tools.ai.tool_builder.proposal import PROJECT_CONVENTIONS
from tools.system.execution_identity import (
    PROJECT_AGENT,
    log_run_start,
    log_tool_call,
    log_tool_result,
)
from tools.system.agent_tool_gate import (
    authorize_tool_execution,
    blocked_result,
    default_ask_confirm,
)
from tools.system.capability_route_obs import (
    build_capability_outcome_compare,
    build_capability_route_observation,
    build_pre_web_answer_candidate,
    build_tool_trial,
    build_web_search_results_digest,
    new_observation_id,
    record_capability_outcome_compare,
    record_capability_route_observation,
    record_pre_web_answer_candidate,
)


def _development_policy_prompt() -> str:
    try:
        from ai_tool.policy.loader import policy_prompt_block

        return policy_prompt_block()
    except Exception as exc:  # noqa: BLE001
        return (
            "development_policy: LOAD_FAILED. "
            f"{type(exc).__name__}: {exc}. specification_complete is forbidden."
        )


_pipeline = get_pipeline()
_llm_profile = get_llm_profile()
MODEL = _llm_profile["model"]
MAX_TOOL_ROUNDS = int(_pipeline.get("max_tool_rounds") or 5)

# Actor Identity: 課題遂行主体は PROJECT_AGENT（Controller 起動でも同様）
log_run_start(
    execution_actor=PROJECT_AGENT,
    entrypoint="agent.py",
    llm=MODEL,
    extra={"event": "agent_start"},
)

# --- agent_tool_discovery hook (read-only; does not alter Ollama tools or execute_tool) ---
_agent_tool_discovery_result = None
_agent_tool_discovery_error = None
_skip_tool_discovery = str(os.environ.get("AI_AGENT_SKIP_TOOL_DISCOVERY") or "").strip().lower() in (
    "1",
    "true",
    "yes",
)
if not _skip_tool_discovery:
    try:
        from ai_tool.agent_integration.hook import safe_run_agent_discovery_hook

        _agent_tool_discovery_result = safe_run_agent_discovery_hook(audit=True)
        if not _agent_tool_discovery_result.ok:
            _agent_tool_discovery_error = _agent_tool_discovery_result.error
    except Exception as exc:  # noqa: BLE001 — discovery failure must not break Agent
        _agent_tool_discovery_error = str(exc)
        _agent_tool_discovery_result = None
else:
    _agent_tool_discovery_error = "skipped_by_AI_AGENT_SKIP_TOOL_DISCOVERY"

if _agent_tool_discovery_result is not None:
    print("\n[AGENT_TOOL_DISCOVERY]")
    print(
        json.dumps(
            {
                **_agent_tool_discovery_result.agent_summary(),
                "observation_only": True,
                "does_not_modify_ollama_tools": True,
                "does_not_execute_tools": True,
                "audit_id": _agent_tool_discovery_result.audit_id,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
elif _agent_tool_discovery_error and _agent_tool_discovery_error != "skipped_by_AI_AGENT_SKIP_TOOL_DISCOVERY":
    print("\n[AGENT_TOOL_DISCOVERY]")
    print(
        json.dumps(
            {
                "ok": False,
                "observation_only": True,
                "error": _agent_tool_discovery_error,
                "does_not_modify_ollama_tools": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

# --- LLM Tool Calling capability (diagnostic only; does not change model selection) ---
_agent_tool_calling_capability = None
if str(os.environ.get("AI_AGENT_SKIP_TOOL_CALLING_PROBE") or "").strip().lower() not in (
    "1",
    "true",
    "yes",
):
    try:
        from tools.system.llm_tool_capability import probe_tool_calling

        _agent_tool_calling_capability = probe_tool_calling(MODEL)
    except Exception as exc:  # noqa: BLE001
        _agent_tool_calling_capability = {
            "supported": None,
            "error": str(exc),
            "detail": "probe_exception",
        }

if _agent_tool_calling_capability is not None:
    print("\n[AGENT_TOOL_CALLING_CAPABILITY]")
    print(
        json.dumps(
            {
                "model": MODEL,
                "observation_only": False,
                "primary_path_requires_tool_calling": True,
                **_agent_tool_calling_capability,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    _allow_non_tool_calling = str(
        os.environ.get("AI_AGENT_ALLOW_NON_TOOL_CALLING_MODEL") or ""
    ).strip().lower() in ("1", "true", "yes")
    if _agent_tool_calling_capability.get("supported") is False and not _allow_non_tool_calling:
        print("\n[AGENT_TOOL_CALLING_CAPABILITY] ERROR")
        print(
            json.dumps(
                {
                    "model": MODEL,
                    "message": (
                        "現在の Agent 主経路は Native Tool Calling のみです。"
                        "設定モデルは Ollama tools パラメータ非対応のため起動を停止します。"
                    ),
                    "hint": (
                        "config/pipeline.yaml の active_model を Tool Calling 対応プロファイルへ変更するか、"
                        "研究・互換経路のみ AI_AGENT_ALLOW_NON_TOOL_CALLING_MODEL=1 を設定してください。"
                    ),
                    "probe": _agent_tool_calling_capability,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

# --- Model Registry (observation only; does not change model selection) ---
_skip_model_registry = str(os.environ.get("AI_AGENT_SKIP_MODEL_REGISTRY") or "").strip().lower() in (
    "1",
    "true",
    "yes",
)
if not _skip_model_registry:
    try:
        from tools.system.model_registry import registry_summary

        print("\n[MODEL_REGISTRY]")
        print(json.dumps(registry_summary(), ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001
        print("\n[MODEL_REGISTRY]")
        print(
            json.dumps(
                {
                    "ok": False,
                    "observation_only": True,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

# 収集バッチ等: AI_AGENT_USER_REQUEST で上書き。未設定なら既定の実験要求。
_USER_REQUEST_DEFAULT = (
    "複数の独立したWeb情報源を検索し、情報源ごとの差異を比較し、"
    "最終的な結論と根拠を整理してください。"
    "テーマは Windows で CPU 使用率を取得する代表的な方法です。"
    "検索結果をそのまま信じず、情報源を区別し、根拠と推測を分けてください。"
    "新規Toolの作成は不要です。既存の調査系Toolを使ってください。"
)
USER_REQUEST = (os.environ.get("AI_AGENT_USER_REQUEST") or "").strip() or _USER_REQUEST_DEFAULT

# ==========================================
# Registry読み込み
# ==========================================

def load_registry():
    with open("registry/tools.json", "r", encoding="utf-8") as f:
        return json.load(f)


registry = load_registry()


# ==========================================
# Registry → Ollama Tool定義
# ==========================================

def create_ollama_tools(registry):
    """
    visibility==\"agent\" の Tool だけを Ollama へ公開する。
    Registry input の required: true から parameters.required を生成する。
    """
    tools = []

    for tool in registry["tools"]:
        if tool.get("visibility") != "agent":
            continue

        properties = {}
        required = []

        for name, parameter in tool.get("input", {}).items():
            param = dict(parameter)
            is_required = bool(param.pop("required", False))
            properties[name] = param
            if is_required:
                required.append(name)

        for name in tool.get("required") or []:
            if name not in required:
                required.append(name)

        parameters = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": parameters,
                },
            }
        )

    return tools


tools = create_ollama_tools(registry)


def _ollama_tools_for_llm(tool_defs: list) -> list:
    return [{k: v for k, v in t.items() if not k.startswith("_")} for t in tool_defs]


# --- experimental Agent overlay (Phase 5 — NOT registry registration) ---
_experimental_agent_exposure = None
_experimental_agent_exposure_error = None
try:
    from ai_tool.agent_integration.production_bridge import (
        append_experimental_agent_tools,
        get_experimental_agent_exposure,
        ollama_tools_for_llm as _bridge_ollama_tools_for_llm,
    )

    tools = append_experimental_agent_tools(tools)
    _experimental_agent_exposure = get_experimental_agent_exposure()
    ollama_tools_for_llm = _bridge_ollama_tools_for_llm
except Exception as exc:  # noqa: BLE001 — overlay failure must not break Agent
    _experimental_agent_exposure_error = str(exc)
    ollama_tools_for_llm = _ollama_tools_for_llm

if _experimental_agent_exposure is not None and _experimental_agent_exposure.enabled:
    print("\n[EXPERIMENTAL_AGENT_TOOLS]")
    print(
        json.dumps(
            {
                **_experimental_agent_exposure.to_dict(),
                "does_not_modify_registry": True,
                "catalog_status_unchanged": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
elif _experimental_agent_exposure_error:
    print("\n[EXPERIMENTAL_AGENT_TOOLS]")
    print(
        json.dumps(
            {"ok": False, "error": _experimental_agent_exposure_error},
            ensure_ascii=False,
            indent=2,
        )
    )


# ==========================================
# Tool検索
# ==========================================

def find_tool(tool_name):
    for tool in registry["tools"]:
        if tool["name"] == tool_name:
            return tool

    return None


# ==========================================
# 検証済み情報
# ==========================================

def load_existing_tools():
    results = []

    for tool in registry["tools"]:
        if tool["name"] == "create_tool_proposal":
            continue

        try:
            module = importlib.import_module(tool["module"])
            source = inspect.getsource(module)

            results.append(
                {
                    "name": tool["name"],
                    "category": tool.get("category"),
                    "subcategory": tool.get("subcategory"),
                    "module": tool["module"],
                    "function": tool["function"],
                    "source": source,
                    "note": "構造の参考。要求の対象が違うなら対象を変えてまねること。",
                }
            )

        except Exception as e:
            results.append(
                {
                    "name": tool["name"],
                    "error": str(e),
                }
            )

    return results


def collect_verified_environment():
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    os_name = platform.system().lower()

    environment = {
        "language": "python",
        "python_version": python_version,
        "python_full_version": sys.version.split()[0],
        "platform": os_name,
        "architecture": platform.machine(),
        "gpu": "未確認",
    }

    try:
        from tools.system.gpu.nvidia_smi import query_gpu_status

        status = query_gpu_status()
        if status.get("ok") and status.get("gpu") not in (None, "unknown"):
            total = status.get("vram_total")
            if total not in (None, "unknown"):
                environment["gpu"] = f"{status['gpu']}, {total} MiB"
            else:
                environment["gpu"] = str(status["gpu"])
        elif status.get("status") == "unavailable":
            environment["gpu"] = "unavailable"
    except Exception:
        pass

    return environment


existing_tools = load_existing_tools()
verified_environment = collect_verified_environment()


def _clarity_complete(materials, state):
    messages = build_clarity_messages(materials, state=state)
    response = chat(model=MODEL, messages=messages)
    return response.message.content


def _clarity_ask(question, options):
    print("\n要求の確認:")
    print(format_clarity_question(question, options))
    if not sys.stdin.isatty():
        return None
    try:
        return input("> ").strip()
    except EOFError:
        return None


print("\nCLARITY CHECK:")
# 収集バッチ専用: AI_AGENT_SKIP_CLARITY=1 のときのみ Clarity 対話を飛ばす（通常運用では使わない）
if str(os.environ.get("AI_AGENT_SKIP_CLARITY") or "").strip().lower() in (
    "1",
    "true",
    "yes",
):
    clarity_result = {
        "status": "clear",
        "next_step": "research",
        "state": TaskState(task=USER_REQUEST),
        "judgment": {"status": "clear", "question": "", "options": []},
        "conversation": [],
        "skipped_for_collection": True,
    }
    print(
        json.dumps(
            {
                "status": clarity_result["status"],
                "next_step": clarity_result["next_step"],
                "skipped_for_collection": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
else:
    clarity_result = run_clarity_gate(
        USER_REQUEST,
        ask=_clarity_ask,
        complete=_clarity_complete,
    )
    print(
        json.dumps(
            {
                "status": clarity_result["status"],
                "next_step": clarity_result["next_step"],
                "decisions": snapshot_state(clarity_result["state"])["decisions"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if clarity_result["next_step"] != "research":
        print("\n要求が確定していないため、調査には進みません。")
        sys.exit(0)

task_state = clarity_result["state"]

# Cognitive Layer Phase 1（オプトイン）: State 生成・可視化のみ。Selector / Tool 実行には接続しない。
if str(os.environ.get("AI_AGENT_COGNITIVE_PHASE1") or "").strip().lower() in (
    "1",
    "true",
    "yes",
):
    try:
        from tools.ai.state.cognitive_session import save_session
        from tools.ai.state.cognitive_state import (
            init_from_user_request,
            sync_unresolved_from_task_state,
        )

        _cog = init_from_user_request(USER_REQUEST, source="agent_clarity")
        sync_unresolved_from_task_state(_cog, task_state)
        _cog_path = save_session(_cog)
        print(
            "\nCOGNITIVE PHASE1 (sidecar only; selector/tools not invoked):",
            _cog_path,
        )
    except Exception as _cog_err:
        print("\nCOGNITIVE PHASE1 skipped due to error:", _cog_err)

related_tools = search_tools(
    registry,
    USER_REQUEST,
)

reference_tools = []

if not related_tools:
    reference_tools = find_reference_tools(
        registry,
        category="system",
        limit=2,
    )
reference_sources = []

for tool in reference_tools:
    try:
        reference_sources.append(
            load_tool_source(tool)
        )
    except Exception as e:
        reference_sources.append(
            {
                "name": tool.get("name"),
                "error": str(e),
            }
        )

print("\n関連Tool:")
print(json.dumps(related_tools, ensure_ascii=False, indent=2))

print("\n参考Tool:")
print(json.dumps(reference_tools, ensure_ascii=False, indent=2))

print("\n参考Toolのソース:")
print(json.dumps(reference_sources, ensure_ascii=False, indent=2))

# capability_route 観測用（実行権限・Pipeline起動には使わない）
capability_observation_id = new_observation_id()
agent_tools_tried = []
web_session_tracker = None
try:
    from tools.system.network.web_status import WebSessionTracker

    web_session_tracker = WebSessionTracker()
except ImportError:
    pass

# 後々、構造的に近いものを検索するcategory → subcategory → keywords → description

# ==========================================
# Tool動的読み込み
# ==========================================

def normalize_arguments(arguments):
    if arguments is None:
        return {}

    if isinstance(arguments, str):
        if not arguments.strip():
            return {}
        return json.loads(arguments)

    return dict(arguments)


def execute_tool(
    tool_name,
    arguments,
    related_tools=None,
    reference_tools=None,
    reference_sources=None,
    *,
    bypass_tool_gate=False,
    ask_tool_confirm=None,
):
    """
    PROJECT_AGENT 公開 Tool 実行。

    実行前に agent_tool_gate（デフォルト人間確認）を通す。
    Research Pipeline の decide_execution_gate とは別系統・非統合。
    bypass_tool_gate は IDENTITY_SMOKE 等の明示バイパス専用。
    """
    try:
        from ai_tool.agent_integration.production_bridge import (
            execute_experimental_agent_tool,
            is_experimental_agent_tool,
        )

        if is_experimental_agent_tool(tool_name):
            return execute_experimental_agent_tool(
                tool_name,
                arguments,
                authorize=authorize_tool_execution,
                blocked_result=blocked_result,
                log_tool_call=log_tool_call,
                log_tool_result=log_tool_result,
                execution_actor=PROJECT_AGENT,
                ask_tool_confirm=ask_tool_confirm or default_ask_confirm,
                bypass_tool_gate=bypass_tool_gate,
            )
    except ImportError:
        pass

    tool = find_tool(tool_name)

    if tool is None:
        raise ValueError(
            f"RegistryにToolが登録されていません: {tool_name}"
        )

    arguments = normalize_arguments(arguments)

    # ログ用（create_tool_proposal の注入前引数）。別名への黙認変換はしない。
    logged_arguments = dict(arguments)

    auth = authorize_tool_execution(
        tool_name,
        logged_arguments,
        ask_confirm=ask_tool_confirm or default_ask_confirm,
        bypass=bypass_tool_gate,
    )
    if not auth.get("allowed"):
        denied = blocked_result(
            tool_name,
            reason=str(auth.get("decision") or "deny"),
            arguments=logged_arguments,
        )
        log_tool_call(
            execution_actor=PROJECT_AGENT,
            tool_name=tool_name,
            arguments=logged_arguments,
            extra={
                "agent_tool_gate": auth,
                "blocked": True,
            },
        )
        log_tool_result(
            execution_actor=PROJECT_AGENT,
            tool_name=tool_name,
            result=denied,
            extra={"agent_tool_gate": auth, "blocked": True},
        )
        return denied

    if tool_name == "create_tool_proposal":
        arguments = {
            "request": arguments.get("request", USER_REQUEST),
            "project_spec": PROJECT_CONVENTIONS,
            "registry": [
                {
                    "name": tool["name"],
                    "category": tool.get("category"),
                    "subcategory": tool.get("subcategory"),
                    "description": tool.get("description"),
                    "module": tool.get("module"),
                    "function": tool.get("function"),
                }
                for tool in registry["tools"]
            ],
            "reference_tools": reference_tools or [],
            "reference_sources": reference_sources or [],
            "related_tools": related_tools or [],
            "environment": verified_environment,
        }

    log_tool_call(
        execution_actor=PROJECT_AGENT,
        tool_name=tool_name,
        arguments=logged_arguments,
        extra={"agent_tool_gate": auth},
    )

    module = importlib.import_module(tool["module"])
    function = getattr(module, tool["function"])

    from tools.system.agent_git_execution_gate import apply_git_local_pre_execution_gate

    def _invoke_tool():
        return function(**arguments)

    try:
        gated = apply_git_local_pre_execution_gate(
            tool_name,
            logged_arguments,
            _invoke_tool,
        )
        if isinstance(gated, dict) and (
            gated.get("blocked_by_git_local_gate") or gated.get("need_human_git_local_operation")
        ):
            log_tool_result(
                execution_actor=PROJECT_AGENT,
                tool_name=tool_name,
                result=gated,
                extra={"agent_tool_gate": auth, "git_local_gate": True},
            )
            return gated
        result = gated
    except Exception as exc:
        log_tool_result(
            execution_actor=PROJECT_AGENT,
            tool_name=tool_name,
            error=f"{type(exc).__name__}: {exc}",
            extra={"agent_tool_gate": auth},
        )
        raise

    log_tool_result(
        execution_actor=PROJECT_AGENT,
        tool_name=tool_name,
        result=result,
        extra={"agent_tool_gate": auth},
    )
    return result


def try_agent_recovery_evaluation_loop(
    *,
    response=None,
    tool_name=None,
    tool_result=None,
    timeout=False,
    error=None,
):
    """
    P2-14: 自然 Failure 時に Recovery Evaluation → Agent Selection → 記録 → 停止。
    Recovery 自動実行なし。opt-in 無効時は None。
    """
    try:
        from tools.system.context_monitor.agent_recovery_loop import (
            agent_recovery_loop_enabled,
            handle_agent_recovery_failure,
        )
    except ImportError:
        return None

    if not agent_recovery_loop_enabled():
        return None

    tool_execution_ok = None
    if tool_result is not None:
        from tools.system.context_monitor.agent_recovery_loop import tool_result_is_execution_failure

        if tool_result_is_execution_failure(tool_result):
            tool_execution_ok = False
        elif isinstance(tool_result, dict) and tool_result.get("ok") is True:
            tool_execution_ok = True

    task_id = (os.environ.get("AI_AGENT_COLLECTION_CASE_ID") or "").strip() or None
    return handle_agent_recovery_failure(
        response=response,
        expected_tool=tool_name,
        tool_execution_ok=tool_execution_ok,
        timeout=timeout,
        error=error,
        task_type="agent_loop",
        task_id=task_id,
        chat_fn=chat,
        model=MODEL,
    )


# ==========================================
# 提案JSONの取り出しと検証
# ==========================================

def extract_json_object(text):
    if not text:
        return None

    stripped = text.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(stripped[start:end + 1])
        except json.JSONDecodeError:
            return None


def summarize_tool_result(tool_name, result):
    """
    stdout / 人間向け表示専用。LLM の Tool 結果には使わない。

    create_tool_proposal のみ Registry 件数などの提案要約を返す。
    それ以外は raw を壊さない軽い表示用オブジェクトを返す。
    """
    if tool_name == "create_tool_proposal" and isinstance(result, dict):
        registry_data = result.get("registry")
        if isinstance(registry_data, list):
            registry_tool_count = len(registry_data)
        elif isinstance(registry_data, dict):
            registry_tool_count = len(registry_data.get("tools", []))
        else:
            registry_tool_count = 0

        return {
            "target_request": result.get("target_request"),
            "verified_environment": result.get("verified_environment"),
            "related_tool_names": [
                tool.get("name")
                for tool in result.get("related_tools", [])
                if isinstance(tool, dict)
            ],
            "reference_tool_names": [
                tool.get("name")
                for tool in result.get("reference_tools", [])
                if isinstance(tool, dict)
            ],
            "reference_source_count": len(result.get("reference_sources", [])),
            "registry_tool_count": registry_tool_count,
            "note": "規約・参考Tool・ソースはLLMに渡済み。表示は要約のみ。",
        }

    if isinstance(result, dict):
        if tool_name == "search_web":
            hits = result.get("hits") or []
            return {
                "tool": tool_name,
                "query": result.get("query"),
                "hit_count": len(hits) if isinstance(hits, list) else 0,
                "backends_tried": result.get("backends_tried"),
                "error": result.get("error"),
                "grounding": result.get("grounding"),
                "web_status": result.get("web_status"),
                "titles": [
                    item.get("title")
                    for item in hits[:5]
                    if isinstance(item, dict)
                ],
                "urls": [
                    item.get("url")
                    for item in hits[:5]
                    if isinstance(item, dict)
                ],
                "note": "stdout要約。LLMには raw result を渡す。",
            }
        if tool_name == "read_url_text":
            quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
            main_text = result.get("main_text")
            preview = ""
            if isinstance(main_text, str):
                preview = main_text[:200]
            return {
                "tool": tool_name,
                "ok": result.get("ok"),
                "url": result.get("url"),
                "fact_ready": quality.get("fact_ready"),
                "main_text_preview": preview,
                "grounding": result.get("grounding"),
                "web_status": result.get("web_status"),
                "note": "stdout要約。LLMには raw result を渡す。",
            }
        return {
            "tool": tool_name,
            "keys": sorted(result.keys()),
            "note": "stdout要約。LLMには raw result を渡す。",
        }

    return {
        "tool": tool_name,
        "type": type(result).__name__,
        "note": "stdout要約。LLMには raw result を渡す。",
    }


def print_tool_result_for_stdout(tool_name, result):
    """表示専用。失敗しても呼び出し元の能力経路を止めない。"""
    print("\nTool実行結果:")
    try:
        if isinstance(result, str):
            print(result)
            return
        summary = summarize_tool_result(tool_name, result)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(
            f"[stdout summarize failed: {type(exc).__name__}: {exc}] "
            "raw result は LLM へ別途返却済み/返却予定。"
        )


def validate_proposals(payload, request=None):
    if not isinstance(payload, dict):
        return None

    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        return None

    results = []
    for spec in proposals:
        results.append(
            validate_tool_spec(
                spec,
                verified_environment,
                request=request,
                existing_tools=registry["tools"],
                allowed_categories=ALLOWED_CATEGORIES,
            )
        )

    return results


def validation_failed(results):
    return bool(results) and any(
        item.get("status") == "fail" for item in results
    )


# ==========================================
# 会話
# ==========================================

SYSTEM_PROMPT = f"""
あなたはローカル環境のAI Agentです。

使える事実は次だけです。
- ユーザー要求
- 確定した要求 (STATE)
- 検証済み環境
- Tool実行結果

ユーザー要求の対象を変えてはいけません。
検証済み環境のGPUは、ユーザーがGPUを求めていないなら提案対象ではありません。

確定した要求 (STATE):
{json.dumps(snapshot_state(task_state), ensure_ascii=False, indent=2)}

検証済み環境:
{json.dumps(verified_environment, ensure_ascii=False, indent=2)}

公開されている主なTool:
- search_web: Discovery — Web上の情報探索。queryで検索し title/snippet/URL/relevance_hint 等のヒットを返す。URL本文取得は read_url_text。limitは返す件数。hits だけでは事実確定しない。
- read_url_text: Fetch / Evidence — 既知の HTTP/HTTPS URL を read-only GET で取得し、main_text と quality（fact_ready 等）を返す。意味推論・要約は行わない。回答には main_text を根拠に使う。
- list_files / read_file / search_files: Workspace内の探索・読取・検索
- get_gpu_status / get_gpu_processes / get_cpu_status / cpu_status: ローカル観測（Windows + NVIDIA/CIM 実測）

Observation Tool結果:
- observed（実測値）のみ事実として扱う
- unknown は取得不能。0 や推測値で埋めない
- unsupported は Tool が提供しない情報（故障ではない）
- unavailable は環境/backend 不足（実測値として扱わない）

LLM Tool Calling:
- 使用モデルが Ollama の tools パラメータをサポートしている必要がある（起動時 [AGENT_TOOL_CALLING_CAPABILITY] を参照）

Web調査の手順（Search → Fetch → Evidence）:
1. URLが分からない・複数ソースを探す → search_web（Discovery）
2. 特定 URL の本文が必要 → read_url_text（Fetch / Evidence）
3. read_url_text の main_text と quality.fact_ready を確認する。fact_ready=false の数値や断定は避ける。
4. 返ってきた hits / main_text をユーザー要求と照合し、関連性・十分性を確認する。
5. 無関係・不足なら、同じ文言の繰り返しではなく、質問の言い換え・言語切替など汎用的に query を組み直して再検索する。
6. 1件だけの無関係な結果を根拠に断定しない。
7. 回答で使うタイトル・URL・数値・事実は、実際に受け取った hits / main_text に含まれるものだけを使う。
8. hits / main_text に無いURL・題名・数値を、取得したように補完しない。
9. search_web が空、または grounding.do_not_claim_web_verified_facts のとき、Webで確認した体裁の具体的数値を述べない。
10. tool result の web_status.overall が SUCCESS 以外のとき、Web確認済みの具体的事実として回答しない（システムが web_status を付与する）。
11. Fetch 結果に対して HTML/JSON の構造説明そのものを最終回答にしない（ユーザーが形式デバッグを求めない限り）。
12. 検索でも確認できない場合は「確認できなかった」と書く。

ルール:
1. 上記以外の具体的な値、環境、能力を想像してはいけません。
2. 不明なことは「未確認」と書いてください。
3. 必要な情報は公開Toolを呼び出して取得してください。
4. ファイル作成や Registry 変更はしないでください。
5. 存在しない引数名を捏造しないでください。各Toolの schema に従うこと。
6. 開発作業の完成判定は機械契約に従う。pytest 成功は仕様完成ではない。項目が CONNECTED でないものを完成と書いてはいけない。

Development Policy（機械契約。お願い文ではない）:
{_development_policy_prompt()}
""".strip()

verified_runtime = {
    "language": verified_environment["language"],
    "version": verified_environment["python_version"],
    "platform": [verified_environment["platform"]],
}
verified_runtime_json = json.dumps(verified_runtime, ensure_ascii=False, indent=2)

PROPOSAL_INSTRUCTIONS = f"""
ユーザー要求（対象を変えないこと）:
{USER_REQUEST}

この要求のTool設計仕様を、JSONだけ出力してください。

既存の get_gpu_status は GPU 用の実測 Tool（nvidia-smi）です。CPU要求の代替ではありません。
構造だけを参考にしてください（固定値をコピーしないこと）:
- GPU実測ヘルパー → tools.system.gpu.nvidia_smi
- get_gpu_status → tools.system.gpu.gpu_status（observation_source=real）
- CPU要求なら cpu_status → tools.system.cpu.cpu_status

守ること:
- risk は low / medium / high のみ。文章禁止。
- category は {json.dumps(ALLOWED_CATEGORIES, ensure_ascii=False)} から選ぶ。
- module は tools.<category>.<subcategory>.<filename>
- runtime は次をそのまま使う:
{verified_runtime_json}
- 未確認メトリクスは output に入れず implementation_notes へ。
- センサー値のハードコード（特定 GPU モデル名、固定温度・使用率など）は禁止。取得不能時は unknown/unavailable。
- ファイル作成はしない。

JSONの基本形式:
{{
    "proposals": [
        {{
            "name": "cpu_status",
            "category": "system",
            "subcategory": "cpu",
            "description": "CPUの基本状態を取得する。個別メトリクスの取得可否は未確認。",
            "keywords": ["CPU", "状態"],
            "risk": "low",
            "module": "tools.system.cpu.cpu_status",
            "function": "cpu_status",
            "input": {{}},
            "output": ["status"],
            "dependencies": ["未確認"],
            "runtime": {verified_runtime_json},
            "priority": "required",
            "based_on": ["cpu_status"],
            "implementation_notes": ["温度やコア数などの取得可否は未確認"],
            "observation_source": "real"
        }}
    ]
}}
""".strip()


# Actor Identity の最小確認専用（能力測定ではない）。
# CURSOR_CONTROLLER が AI_AGENT_IDENTITY_SMOKE=1 を付けたときのみ、
# LLM Tool選択を待たず 1 Tool を PROJECT_AGENT 経路で実行して終了する。
import os as _os_identity

if str(_os_identity.environ.get("AI_AGENT_IDENTITY_SMOKE") or "").strip().lower() in (
    "1",
    "true",
    "yes",
):
    # Identity 確認専用。人間確認 Gate はバイパス（能力試験ではない）。
    _smoke = execute_tool(
        "list_files",
        {"path": "registry", "recursive": False},
        bypass_tool_gate=True,
    )
    print(
        "\n[IDENTITY_SMOKE] PROJECT_AGENT execute_tool(list_files) "
        f"ok={(_smoke or {}).get('ok')}"
    )
    sys.exit(0)


messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT,
    },
    {
        "role": "user",
        "content": USER_REQUEST,
    },
]

# --- pre_web_answer_candidate（観測のみ。本番 messages / Gate / Web許可には接続しない） ---
# Toolループ・search_web 実行前に、Webなしで生成可能な回答候補を別会話で取得する。
# Web未実行時も同一スキーマで残す。有益性・正誤の自動判定はしない。
_pre_web_content = None
_pre_web_generation_error = None
_skip_pre_web = str(os.environ.get("AI_AGENT_SKIP_PRE_WEB") or "").strip().lower() in (
    "1",
    "true",
    "yes",
)
if not _skip_pre_web:
    try:
        _pre_web_response = chat(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは PROJECT_AGENT です。"
                        "Web検索・外部検索ツールは使えません。"
                        "手元の知識だけでユーザー要求に答えてください。"
                        "不確かな場合は推測と未確認を明示してください。"
                        "これは本番の最終回答ではありません（観測用の回答候補です）。"
                    ),
                },
                {
                    "role": "user",
                    "content": USER_REQUEST,
                },
            ],
        )
        _pre_web_content = getattr(
            getattr(_pre_web_response, "message", None), "content", None
        )
    except Exception as exc:  # noqa: BLE001 — 観測失敗でも本番ループは継続
        _pre_web_generation_error = str(exc)
        _pre_web_content = None
else:
    _pre_web_generation_error = "skipped_by_AI_AGENT_SKIP_PRE_WEB"

_pre_web_obs = build_pre_web_answer_candidate(
    request=USER_REQUEST,
    content=_pre_web_content,
    observation_id=capability_observation_id,
    entrypoint="agent.py",
    generation_error=_pre_web_generation_error,
    extra={
        "collection_case_id": (os.environ.get("AI_AGENT_COLLECTION_CASE_ID") or "").strip()
        or None,
        "collection_category": (
            os.environ.get("AI_AGENT_COLLECTION_CATEGORY") or ""
        ).strip()
        or None,
        "collection_group_id": (
            os.environ.get("AI_AGENT_COLLECTION_GROUP_ID") or ""
        ).strip()
        or None,
    },
)
_pre_web_record = record_pre_web_answer_candidate(_pre_web_obs)
print("\n[PRE_WEB_ANSWER_CANDIDATE]")
print(
    json.dumps(
        {
            "observation_id": _pre_web_obs.get("observation_id"),
            "kind": "pre_web_answer_candidate",
            "char_count": (_pre_web_obs.get("pre_web_answer_candidate") or {}).get(
                "char_count"
            ),
            "surface": (
                (_pre_web_obs.get("pre_web_answer_candidate") or {}).get("surface") or {}
            ).get("status"),
            "generation_error": (_pre_web_obs.get("pre_web_answer_candidate") or {}).get(
                "generation_error"
            ),
            "log": _pre_web_record.get("path"),
            "observation_only": True,
            "does_not_authorize_web_search": True,
        },
        ensure_ascii=False,
        indent=2,
    )
)

proposal_instruction_added = False
_agent_recovery_stop = False
agent_runtime = AgentRuntime()

for _ in range(MAX_TOOL_ROUNDS):
    agent_runtime.transition(AgentRuntimeState.THINKING)
    with agent_runtime.error_boundary():
        response = chat(
            model=MODEL,
            messages=messages,
            tools=ollama_tools_for_llm(tools),
        )

    messages.append(response.message)

    if not response.message.tool_calls:
        _recovery_loop = try_agent_recovery_evaluation_loop(response=response)
        if _recovery_loop and _recovery_loop.get("stop"):
            try:
                from tools.system.context_monitor.agent_recovery_loop import (
                    print_agent_recovery_stop_notice,
                )

                print_agent_recovery_stop_notice(_recovery_loop)
            except ImportError:
                pass
            _agent_recovery_stop = True
        break

    first_tool_name = response.message.tool_calls[0].function.name
    agent_runtime.transition(
        AgentRuntimeState.TOOL_CALL_REQUESTED,
        tool=first_tool_name,
    )
    proposal_called = False

    for tool_call in response.message.tool_calls:
        tool_name = tool_call.function.name
        arguments = tool_call.function.arguments

        print(f"\n選択されたTool: {tool_name}")
        print(f"引数: {arguments}")

        agent_runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool=tool_name)
        with agent_runtime.error_boundary():
            result = execute_tool(
                tool_name,
                arguments,
                related_tools=related_tools,
                reference_tools=reference_tools,
                reference_sources=reference_sources,
            )
        with agent_runtime.error_boundary():
            try:
                from tools.system.network.web_evidence import enrich_web_tool_result

                result = enrich_web_tool_result(tool_name, result)
            except ImportError:
                pass
        # Runtime classification uses the shared tolerant adapter.  The raw Tool
        # Result itself remains unchanged and is still returned to the LLM.
        normalized_result = (
            normalize_tool_result(result, tool_name=tool_name)
            if isinstance(result, dict)
            else None
        )
        normalized_status = (
            normalized_result.get("status")
            if normalized_result is not None
            else "success"
        )
        tool_failed = normalized_status == "failure"
        result_state = {
            "success": AgentRuntimeState.TOOL_SUCCESS,
            "partial": AgentRuntimeState.TOOL_PARTIAL,
            "failure": AgentRuntimeState.TOOL_FAILED,
        }[normalized_status]
        agent_runtime.transition(
            result_state,
            tool=tool_name,
            error=str(result.get("error")) if tool_failed and result.get("error") else None,
        )
        with agent_runtime.error_boundary():
            if web_session_tracker is not None:
                web_session_tracker.record(tool_name, result)
            agent_tools_tried.append(
                build_tool_trial(tool_name, arguments, result)
            )

            # 能力経路: raw result を先に LLM へ返す（stdout要約に依存しない）
            messages.append(
                {
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": json.dumps(result, ensure_ascii=False, indent=2)
                    if not isinstance(result, str)
                    else result,
                }
            )

        # 表示経路: 失敗しても messages への返却は既に完了
        print_tool_result_for_stdout(tool_name, result)

        # Success/failureどちらもraw Tool Resultはmessagesへ入り、次判断で観測可能。
        agent_runtime.transition(AgentRuntimeState.OBSERVING, tool=tool_name)

        if tool_failed and not result.get("blocked"):
            _recovery_loop = try_agent_recovery_evaluation_loop(
                response=response,
                tool_name=tool_name,
                tool_result=result,
            )
            if _recovery_loop and _recovery_loop.get("stop"):
                try:
                    from tools.system.context_monitor.agent_recovery_loop import (
                        print_agent_recovery_stop_notice,
                    )

                    print_agent_recovery_stop_notice(_recovery_loop)
                except ImportError:
                    pass
                _agent_recovery_stop = True
                break

        if tool_name == "create_tool_proposal":
            proposal_called = True

    if _agent_recovery_stop:
        break

    if proposal_called and not proposal_instruction_added:
        messages.append(
            {
                "role": "user",
                "content": PROPOSAL_INSTRUCTIONS,
            }
        )
        proposal_instruction_added = True

        agent_runtime.transition(AgentRuntimeState.THINKING)
        with agent_runtime.error_boundary():
            response = chat(
                model=MODEL,
                messages=messages,
            )
        messages.append(response.message)
        break


# --- capability_route 観測（判断の記録のみ。Gate/Pipeline/権限に接続しない） ---
_capability_obs = build_capability_route_observation(
    request=USER_REQUEST,
    registry=registry,
    related_tools=related_tools,
    agent_tools_tried=agent_tools_tried,
    observation_id=capability_observation_id,
    entrypoint="agent.py",
    extra={
        "clarity_status": clarity_result.get("status"),
        "clarity_next_step": clarity_result.get("next_step"),
        "collection_case_id": (os.environ.get("AI_AGENT_COLLECTION_CASE_ID") or "").strip()
        or None,
        "collection_category": (
            os.environ.get("AI_AGENT_COLLECTION_CATEGORY") or ""
        ).strip()
        or None,
        "collection_group_id": (
            os.environ.get("AI_AGENT_COLLECTION_GROUP_ID") or ""
        ).strip()
        or None,
    },
)
_capability_record = record_capability_route_observation(_capability_obs)
print("\n[CAPABILITY_ROUTE_OBS]")
print(
    json.dumps(
        {
            "observation_id": _capability_obs.get("observation_id"),
            "route": (_capability_obs.get("capability_route") or {}).get("route"),
            "reason": (_capability_obs.get("capability_route") or {}).get("reason"),
            "web_search": _capability_obs.get("web_search"),
            "agent_tools_tried_count": len(agent_tools_tried),
            "log": _capability_record.get("path"),
            "observation_only": True,
        },
        ensure_ascii=False,
        indent=2,
    )
)

print("\n最終回答:")
_final_answer = response.message.content
_web_boundary = None
if web_session_tracker is not None and web_session_tracker.web_tools_used():
    try:
        from tools.system.network.web_answer_boundary import apply_web_answer_boundary

        _web_boundary = apply_web_answer_boundary(_final_answer, web_session_tracker)
        if _web_boundary.get("system_notice"):
            print("\n[WEB_STATUS]")
            print(_web_boundary["system_notice"])
        if _web_boundary.get("boundary_applied"):
            print("[WEB_ANSWER_BOUNDARY] unsupported web claim suppressed")
        _final_answer = _web_boundary.get("answer") or _final_answer
    except ImportError:
        pass
try:
    from ai_tool.policy.enforce import apply_final_answer_policy

    _policy_out = apply_final_answer_policy(_final_answer)
    if _policy_out.get("notice"):
        print("\n[DEVELOPMENT_POLICY]")
        print(_policy_out["notice"])
    _final_answer = _policy_out.get("answer") or _final_answer
except ImportError:
    pass
print(_final_answer)

proposal_payload = extract_json_object(response.message.content)
validation_results = None
if proposal_payload is not None:
    validation_results = validate_proposals(
        proposal_payload,
        request=USER_REQUEST,
    )

if validation_failed(validation_results):
    print("\n提案の検証:")
    print(json.dumps(validation_results, ensure_ascii=False, indent=2))
    print("\n検証エラーのため、1回だけ修正を依頼します。")

    messages.append(
        {
            "role": "user",
            "content": (
                "提案は検証に失敗しました。JSONだけを出し直してください。\n"
                f"ユーザー要求: {USER_REQUEST}\n"
                "対象を変えないこと。GPU Toolを再提案しないこと。\n"
                f"エラー: {json.dumps(validation_results, ensure_ascii=False)}"
            ),
        }
    )
    agent_runtime.transition(AgentRuntimeState.THINKING)
    with agent_runtime.error_boundary():
        response = chat(
            model=MODEL,
            messages=messages,
        )
    messages.append(response.message)

    print("\n最終回答:")
    print(response.message.content)

    proposal_payload = extract_json_object(response.message.content)
    if proposal_payload is not None:
        validation_results = validate_proposals(
            proposal_payload,
            request=USER_REQUEST,
        )

if validation_results is not None:
    print("\n提案の検証:")
    print(json.dumps(validation_results, ensure_ascii=False, indent=2))

# --- Stage 2: 判断→実行→最終回答の表面比較（誤判定分類・Web有益判定はしない） ---
_outcome_compare = build_capability_outcome_compare(
    capability_observation=_capability_obs,
    final_answer_content=getattr(response.message, "content", None),
    observation_id=capability_observation_id,
    entrypoint="agent.py",
    pre_web_answer_candidate=_pre_web_obs,
    web_search_results=build_web_search_results_digest(agent_tools_tried),
    extra={
        "collection_case_id": (os.environ.get("AI_AGENT_COLLECTION_CASE_ID") or "").strip()
        or None,
        "collection_category": (
            os.environ.get("AI_AGENT_COLLECTION_CATEGORY") or ""
        ).strip()
        or None,
        "collection_group_id": (
            os.environ.get("AI_AGENT_COLLECTION_GROUP_ID") or ""
        ).strip()
        or None,
    },
)
_outcome_record = record_capability_outcome_compare(_outcome_compare)
print("\n[CAPABILITY_OUTCOME_COMPARE]")
print(
    json.dumps(
        {
            "observation_id": _outcome_compare.get("observation_id"),
            "stage": 2,
            "web_pattern": (_outcome_compare.get("compare_summary") or {}).get(
                "web_pattern"
            ),
            "pre_web_surface": (_outcome_compare.get("compare_summary") or {}).get(
                "pre_web_surface_status"
            ),
            "chain_keys": list((_outcome_compare.get("chain") or {}).keys()),
            "misjudgment_classification": _outcome_compare.get(
                "misjudgment_classification"
            ),
            "log": _outcome_record.get("path"),
            "observation_only": True,
            "not_web_usefulness_judgment": True,
        },
        ensure_ascii=False,
        indent=2,
    )
)

if not _agent_recovery_stop and agent_runtime.current_state not in (
    AgentRuntimeState.ERROR,
    AgentRuntimeState.CANCELLED,
):
    agent_runtime.transition(AgentRuntimeState.COMPLETED)
