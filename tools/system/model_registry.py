"""
Model Registry アクセス層。

正本: registry/models.json
Model 接続プロファイル: config/llm_models.yaml（Ollama 接続パラメータ）
Execution Profile（think 等・暫定 v0）: config/llm_execution_profiles.yaml
Agent active 参照: config/pipeline.yaml active_model（profile id）

自動選択・Router は実装しない。管理と参照のみ。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.system.config import ROOT, active_model_id, get_llm_profile


MODEL_REGISTRY_PATH = ROOT / "registry" / "models.json"

_registry_cache: dict[str, Any] | None = None


class ModelRegistryError(Exception):
    """Model Registry の読込・参照エラー。"""


class ModelNotFoundError(ModelRegistryError):
    """登録されていない model id。"""


def load_model_registry(*, reload: bool = False) -> dict[str, Any]:
    global _registry_cache
    if _registry_cache is None or reload:
        if not MODEL_REGISTRY_PATH.is_file():
            raise ModelRegistryError(f"Model Registry が見つかりません: {MODEL_REGISTRY_PATH}")
        _registry_cache = json.loads(MODEL_REGISTRY_PATH.read_text(encoding="utf-8"))
    return _registry_cache


def _models_index(registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = registry or load_model_registry()
    index: dict[str, dict[str, Any]] = {}
    for item in registry.get("models") or []:
        model_id = str(item.get("id") or "")
        if model_id:
            index[model_id] = item
    return index


def list_models(*, reload: bool = False) -> list[dict[str, Any]]:
    registry = load_model_registry(reload=reload)
    return [dict(item) for item in registry.get("models") or []]


def list_roles(*, reload: bool = False) -> list[dict[str, Any]]:
    registry = load_model_registry(reload=reload)
    return [dict(item) for item in registry.get("roles") or []]


def get_model(model_id: str, *, reload: bool = False) -> dict[str, Any]:
    item = _models_index(load_model_registry(reload=reload)).get(str(model_id))
    if item is None:
        raise ModelNotFoundError(f"Model Registry に model id がありません: {model_id}")
    return dict(item)


def get_models_by_role(role: str, *, reload: bool = False) -> list[dict[str, Any]]:
    role_id = str(role)
    return [
        dict(item)
        for item in list_models(reload=reload)
        if role_id in (item.get("roles") or [])
    ]


def get_model_capabilities(model_id: str, *, reload: bool = False) -> dict[str, Any]:
    return dict(get_model(model_id, reload=reload).get("capabilities") or {})


def get_model_status(model_id: str, *, reload: bool = False) -> str:
    return str(get_model(model_id, reload=reload).get("status") or "unknown")


def get_model_evaluation(model_id: str, *, reload: bool = False) -> dict[str, Any]:
    return dict(get_model(model_id, reload=reload).get("evaluation") or {})


def tool_calling_capability(model_id: str, *, reload: bool = False) -> dict[str, Any]:
    caps = get_model_capabilities(model_id, reload=reload)
    tc = caps.get("tool_calling") or {}
    return {
        "model_id": model_id,
        "supported": bool(tc.get("supported")),
        "verified": bool(tc.get("verified")),
        "verification_method": tc.get("verification_method"),
        "verification_date": tc.get("verification_date"),
    }


def is_tool_calling_supported(model_id: str, *, reload: bool = False) -> bool:
    return bool(tool_calling_capability(model_id, reload=reload).get("supported"))


def is_tool_calling_verified(model_id: str, *, reload: bool = False) -> bool:
    cap = tool_calling_capability(model_id, reload=reload)
    return bool(cap.get("supported") and cap.get("verified"))


def get_pipeline_active_model_id() -> str | None:
    """config/pipeline.yaml（または AI_AGENT_MODEL）が指す profile id。"""
    return active_model_id()


def get_active_model(*, reload: bool = False) -> dict[str, Any]:
    """pipeline active_model に対応する Registry エントリ。"""
    model_id = get_pipeline_active_model_id()
    if not model_id:
        raise ModelRegistryError("active_model が設定されていません")
    return get_model(model_id, reload=reload)


def resolve_provider_model_name(identifier: str | None = None) -> str:
    """Resolve Registry/profile identity to the provider-facing model name."""
    requested = str(identifier or active_model_id() or "").strip()
    for item in list_models():
        identities = {
            str(item.get(key) or "").strip()
            for key in ("id", "profile_id", "model", "display_name")
        }
        if requested in identities:
            return str(item.get("model") or requested).strip()
    try:
        return str(get_llm_profile(requested).get("model") or requested).strip()
    except KeyError:
        return requested


def registry_summary(*, reload: bool = False) -> dict[str, Any]:
    """起動時観測用の要約。自動選択は行わない。"""
    active_id = get_pipeline_active_model_id()
    active = get_active_model(reload=reload) if active_id else None
    return {
        "registry_path": str(MODEL_REGISTRY_PATH),
        "model_count": len(list_models(reload=reload)),
        "role_count": len(list_roles(reload=reload)),
        "pipeline_active_model_id": active_id,
        "pipeline_active_status": active.get("status") if active else None,
        "pipeline_active_tool_calling": tool_calling_capability(active_id, reload=reload)
        if active_id
        else None,
    }
