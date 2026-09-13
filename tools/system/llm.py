import subprocess
import time

import httpx
from ollama import Client

from tools.system.config import get_llm_profile
from tools.system.execution_profile import apply_execution_profile, messages_have_images
from tools.system.model_registry import resolve_provider_model_name
from tools.system.timing import record_llm


_client = None
_client_timeout = None


class LLMTimeoutError(RuntimeError):
    pass


def _profile():
    return get_llm_profile()


def request_hard_timeout_seconds(profile=None):
    """Transport safety cap; LONG_RUNNING is a UI state, not this deadline."""
    selected = profile or _profile()
    return int(
        selected.get("hard_timeout_seconds")
        or selected.get("timeout_seconds")
        or 90
    )


def get_client():
    global _client, _client_timeout
    timeout = request_hard_timeout_seconds()
    if _client is None or _client_timeout != timeout:
        _client = Client(timeout=timeout)
        _client_timeout = timeout
    return _client


def chat(**kwargs):
    profile = _profile()
    kwargs.setdefault("model", profile["model"])
    kwargs["model"] = resolve_provider_model_name(kwargs.get("model"))
    monitor_meta = kwargs.pop("context_monitor_meta", None) or {}
    runtime_context = kwargs.pop("runtime_context", None)
    execution_profile = kwargs.pop("execution_profile", None)
    has_images = kwargs.pop("has_images", None)
    if execution_profile:
        kwargs = apply_execution_profile(
            kwargs,
            str(execution_profile),
            has_images=has_images,
        )
    execution_profile_meta = dict(kwargs.pop("execution_profile_meta", None) or {})

    options = dict(kwargs.get("options") or {})
    options.setdefault("num_predict", int(profile.get("num_predict") or 2048))
    options.setdefault("temperature", float(profile.get("temperature") or 0))
    if runtime_context is not None:
        options["num_ctx"] = int(runtime_context)
    elif profile.get("context_limit"):
        options.setdefault("num_ctx", int(profile.get("context_limit")))
    kwargs["options"] = options
    kwargs.setdefault("keep_alive", profile.get("keep_alive") or "5m")
    timeout = request_hard_timeout_seconds(profile)

    obs_meta = {
        "profile_id": profile.get("id"),
        "execution_profile_id": execution_profile_meta.get("execution_profile_id"),
        "execution_profile_status": execution_profile_meta.get("profile_status"),
        "think": kwargs.get("think"),
        "has_images": (
            has_images
            if has_images is not None
            else messages_have_images(kwargs.get("messages"))
        ),
        "context_size": options.get("num_ctx") or profile.get("context_limit"),
        "source": "llm.chat",
        "limits": {
            "configured_context_limit": profile.get("context_limit"),
        },
    }
    if runtime_context is not None:
        obs_meta["limits"]["runtime_context"] = int(runtime_context)
    if isinstance(monitor_meta, dict):
        obs_meta.update(monitor_meta)

    started = time.perf_counter()
    try:
        from tools.system.context_monitor.record import begin_chat_observation

        with begin_chat_observation(obs_meta, dict(kwargs)) as obs:
            try:
                result = get_client().chat(**kwargs)
                obs.record_outcome(_outcome_from_chat_response(result))
                return result
            except httpx.TimeoutException as exc:
                obs.mark_timeout()
                raise LLMTimeoutError(
                    f"LLM応答が {timeout} 秒以内に終わりませんでした"
                ) from exc
    except ImportError:
        try:
            return get_client().chat(**kwargs)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"LLM応答が {timeout} 秒以内に終わりませんでした"
            ) from exc
    finally:
        record_llm(time.perf_counter() - started)


def _outcome_from_chat_response(response) -> dict:
    """Native tool call 等の事実を response から抽出。"""
    outcome: dict = {
        "native_tool_call": False,
        "native_tool_names": [],
        "content_len": 0,
        "thinking_len": 0,
        "eval_count": None,
        "prompt_eval_count": None,
        "done_reason": None,
    }
    try:
        msg = getattr(response, "message", None)
        content = str(getattr(msg, "content", None) or "")
        thinking = str(getattr(msg, "thinking", None) or "")
        outcome["content_len"] = len(content)
        outcome["thinking_len"] = len(thinking)
        outcome["empty_response"] = not content.strip()
        tcs = getattr(msg, "tool_calls", None) or []
        names = []
        for tc in tcs:
            fn = getattr(tc, "function", None)
            if fn and getattr(fn, "name", None):
                names.append(fn.name)
        outcome["native_tool_call"] = bool(names)
        outcome["native_tool_names"] = names
        if hasattr(response, "model_dump"):
            dumped = response.model_dump()
            outcome["eval_count"] = dumped.get("eval_count")
            outcome["prompt_eval_count"] = dumped.get("prompt_eval_count")
            outcome["done_reason"] = dumped.get("done_reason")
    except Exception:
        pass
    return outcome


def stop_model(model=None):
    subprocess.run(
        ["ollama", "stop", resolve_provider_model_name(model or _profile()["model"])],
        timeout=30,
        check=False,
        capture_output=True,
        text=True,
    )
