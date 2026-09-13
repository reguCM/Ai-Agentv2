"""LLM Execution Profile v0 — central think-mode policy (provisional).

Model connection parameters remain in config/llm_models.yaml.
Execution behavior (think on/off, future sampling overrides) lives here.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

from tools.system.config import ROOT

EXECUTION_PROFILES_PATH = ROOT / "config" / "llm_execution_profiles.yaml"

KNOWN_PROFILE_IDS = frozenset(
    {
        "human_intent",
        "fast_tool",
        "structured_output",
        "deep_reasoning",
        "vision_reasoning",
    }
)


class ExecutionProfileError(Exception):
    """Execution profile load or resolve error."""


class ExecutionProfileNotFoundError(ExecutionProfileError):
    """Unknown execution profile id."""


@lru_cache(maxsize=1)
def load_execution_profiles_config(*, reload: bool = False) -> dict[str, Any]:
    if reload:
        load_execution_profiles_config.cache_clear()
    if not EXECUTION_PROFILES_PATH.is_file():
        raise ExecutionProfileError(
            f"Execution profile config not found: {EXECUTION_PROFILES_PATH}"
        )
    payload = yaml.safe_load(EXECUTION_PROFILES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExecutionProfileError("Execution profile config root must be a mapping")
    return payload


def list_execution_profiles(*, reload: bool = False) -> list[dict[str, Any]]:
    config = load_execution_profiles_config(reload=reload)
    profiles = config.get("profiles") or {}
    if not isinstance(profiles, dict):
        return []
    return [
        {"id": profile_id, **dict(definition)}
        for profile_id, definition in profiles.items()
        if isinstance(definition, dict)
    ]


def get_execution_profile(profile_id: str, *, reload: bool = False) -> dict[str, Any]:
    config = load_execution_profiles_config(reload=reload)
    profiles = config.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise ExecutionProfileNotFoundError(f"profiles section missing for: {profile_id}")
    definition = profiles.get(str(profile_id))
    if not isinstance(definition, dict):
        raise ExecutionProfileNotFoundError(f"Unknown execution profile: {profile_id}")
    return {"id": str(profile_id), **dict(definition)}


def agent_turn_phase_profile(phase: str, *, reload: bool = False) -> str:
    config = load_execution_profiles_config(reload=reload)
    mapping = config.get("agent_turn_phase_profiles") or {}
    if not isinstance(mapping, dict):
        return "fast_tool"
    return str(mapping.get(str(phase)) or "fast_tool")


def messages_have_images(messages: Any) -> bool:
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        images = message.get("images")
        if isinstance(images, list) and images:
            return True
    return False


def resolve_execution_profile(
    profile_id: str,
    *,
    has_images: bool = False,
    reload: bool = False,
) -> dict[str, Any]:
    """Resolve profile id to chat kwargs fragment (currently `think` only)."""
    profile = get_execution_profile(profile_id, reload=reload)
    if profile_id == "vision_reasoning":
        think = bool(
            profile.get("think_when_images")
            if has_images
            else profile.get("think_when_no_images")
        )
    else:
        think = bool(profile.get("think"))
    return {
        "execution_profile_id": profile_id,
        "think": think,
        "has_images": has_images,
        "profile_status": str(
            load_execution_profiles_config(reload=reload).get("status") or "provisional"
        ),
    }


def apply_execution_profile(
    chat_kwargs: Mapping[str, Any],
    profile_id: str,
    *,
    has_images: bool | None = None,
    reload: bool = False,
) -> dict[str, Any]:
    """Merge execution profile into chat kwargs unless caller set `think` explicitly."""
    merged = dict(chat_kwargs)
    if "think" in merged:
        return merged
    resolved_has_images = (
        has_images if has_images is not None else messages_have_images(merged.get("messages"))
    )
    resolved = resolve_execution_profile(
        profile_id,
        has_images=resolved_has_images,
        reload=reload,
    )
    merged["think"] = resolved["think"]
    meta = dict(merged.get("execution_profile_meta") or {})
    meta.update(resolved)
    merged["execution_profile_meta"] = meta
    return merged


__all__ = [
    "EXECUTION_PROFILES_PATH",
    "ExecutionProfileError",
    "ExecutionProfileNotFoundError",
    "KNOWN_PROFILE_IDS",
    "agent_turn_phase_profile",
    "apply_execution_profile",
    "get_execution_profile",
    "list_execution_profiles",
    "load_execution_profiles_config",
    "messages_have_images",
    "resolve_execution_profile",
]
