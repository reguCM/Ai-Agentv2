"""Model Registry アクセス層のテスト。"""

from __future__ import annotations

import json

import pytest

from tools.system.config import active_model_id
from tools.system.model_registry import (
    ModelNotFoundError,
    get_active_model,
    get_model,
    get_model_capabilities,
    get_model_evaluation,
    get_model_status,
    get_models_by_role,
    get_pipeline_active_model_id,
    is_tool_calling_supported,
    is_tool_calling_verified,
    list_models,
    list_roles,
    load_model_registry,
    registry_summary,
    resolve_provider_model_name,
    tool_calling_capability,
)


def test_provider_model_name_resolves_registry_and_profile_identities():
    assert resolve_provider_model_name("qwen3_14b") == "qwen3:14b"
    assert resolve_provider_model_name("qwen3:14b") == "qwen3:14b"
    assert resolve_provider_model_name("custom:model") == "custom:model"


def test_load_registry_has_models():
    registry = load_model_registry()
    assert registry.get("version") == 1
    assert len(registry.get("models") or []) >= 5


def test_get_model_success():
    item = get_model("qwen3_14b")
    assert item["model"] == "qwen3:14b"
    assert item["profile_id"] == "qwen3_14b"


def test_get_model_missing():
    with pytest.raises(ModelNotFoundError):
        get_model("does_not_exist_model_xyz")


def test_get_models_by_role():
    agents = get_models_by_role("general_agent")
    ids = {item["id"] for item in agents}
    assert "qwen3_14b" in ids
    assert "qwen3_8b" in ids
    assert "deepseek_coder_v2_16b" not in ids


def test_get_model_capabilities():
    caps = get_model_capabilities("qwen3_14b")
    assert caps["tool_calling"]["supported"] is True
    assert "text" in caps


def test_tool_calling_capability_supported_and_verified():
    tc = tool_calling_capability("qwen3_14b")
    assert tc["supported"] is True
    assert tc["verified"] is True
    assert is_tool_calling_supported("qwen3_14b")
    assert is_tool_calling_verified("qwen3_14b")


def test_tool_calling_capability_unsupported_verified():
    tc = tool_calling_capability("deepseek_coder_v2_16b")
    assert tc["supported"] is False
    assert tc["verified"] is True
    assert is_tool_calling_supported("deepseek_coder_v2_16b") is False


def test_get_model_status():
    assert get_model_status("qwen3_14b") == "active"
    assert get_model_status("qwen3_8b") == "candidate"


def test_get_model_evaluation():
    ev = get_model_evaluation("qwen3_14b")
    assert ev["tool_calling"]["single_tool"] == "PASS"
    assert ev["tool_calling"]["source_task"] == "TC-REGISTRY-FOUNDATION-P0"


def test_active_model_matches_pipeline():
    assert get_pipeline_active_model_id() == active_model_id()
    active = get_active_model()
    assert active["id"] == "qwen3_14b"
    assert active["pipeline_active"] is True


def test_registry_summary():
    summary = registry_summary()
    assert summary["pipeline_active_model_id"] == "qwen3_14b"
    assert summary["pipeline_active_tool_calling"]["supported"] is True


def test_list_roles_minimal():
    roles = list_roles()
    ids = {item["id"] for item in roles}
    assert "general_agent" in ids
    assert "coding" in ids
    assert len(roles) <= 6


def test_all_registered_models_have_profile_id():
    for item in list_models():
        assert item.get("profile_id")
        assert item.get("model")
        assert item.get("status")


def test_registry_json_valid():
    from pathlib import Path

    data = json.loads(Path("registry/models.json").read_text(encoding="utf-8"))
    assert data["models"]
