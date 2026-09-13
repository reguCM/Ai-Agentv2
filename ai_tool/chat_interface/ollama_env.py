"""Ollama の設定と、認識中モデル一覧。chat() は呼ばない。pull / 削除もしない。"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ai_tool.chat_interface.llm_errors import NO_MODELS_JA, OLLAMA_UNREACHABLE_JA
from tools.system.config import get_llm_profile
from tools.system.model_registry import get_pipeline_active_model_id

OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"


def configured_ollama_model() -> str:
    try:
        return str(get_llm_profile().get("model") or "")
    except Exception:
        return ""


def ollama_list_names() -> tuple[list[str], str | None]:
    try:
        proc = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=20,
            shell=False,
        )
        if proc.returncode != 0:
            return [], (proc.stderr or proc.stdout or "ollama list failed").strip()
        names: list[str] = []
        for line in (proc.stdout or "").splitlines()[1:]:
            name = line.split()[0].strip() if line.strip() else ""
            if name and name.upper() != "NAME":
                names.append(name)
        return names, None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def disk_manifest_models(models_dir: Path | None = None) -> list[str]:
    root = models_dir or Path(os.environ.get("OLLAMA_MODELS") or r"D:\ollama\models")
    library = root / "manifests" / "registry.ollama.ai" / "library"
    if not library.is_dir():
        return []
    found: list[str] = []
    for family in sorted(p for p in library.iterdir() if p.is_dir()):
        for tag in sorted(p for p in family.iterdir() if p.is_file()):
            found.append(f"{family.name}:{tag.name}")
    return found


def _names_from_tags_payload(data: Any) -> list[str]:
    names: list[str] = []
    models = data.get("models") if isinstance(data, dict) else None
    for item in models or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def fetch_ollama_tags() -> tuple[list[str], str | None]:
    """`ollama list` 相当。起動中 Ollama の /api/tags を読む。"""
    try:
        req = urllib.request.Request(OLLAMA_TAGS_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw or "{}")
        return _names_from_tags_payload(data), None
    except urllib.error.URLError as exc:
        return [], str(exc.reason if getattr(exc, "reason", None) else exc)
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def resolve_default_model(available: list[str], configured: str | None = None) -> str:
    cfg = (configured if configured is not None else configured_ollama_model()).strip()
    names = list(available or [])
    if cfg and cfg in names:
        return cfg
    if names:
        return names[0]
    return cfg


def list_live_models() -> dict[str, Any]:
    """現在 Ollama が認識しているモデル。固定リストは使わない。"""
    configured = configured_ollama_model()
    names, http_error = fetch_ollama_tags()
    reachable = http_error is None
    error = http_error
    if not names:
        listed, cli_error = ollama_list_names()
        if listed:
            names = listed
            reachable = True
            error = None
        elif not reachable:
            error = http_error or cli_error
        elif cli_error:
            error = cli_error
    user_message = None
    if not reachable:
        user_message = OLLAMA_UNREACHABLE_JA
    elif not names:
        user_message = NO_MODELS_JA
    return {
        "reachable": reachable,
        "models": names,
        "error": error,
        "user_message": user_message,
        "configured_model": configured,
        "default_model": resolve_default_model(names, configured),
    }


def describe_ollama_env() -> dict[str, Any]:
    configured = configured_ollama_model()
    live = list_live_models()
    listed, list_error = live["models"], live.get("error")
    disk = disk_manifest_models()
    return {
        "configured_model": configured,
        "pipeline_active_model_id": get_pipeline_active_model_id(),
        "ollama_list": listed,
        "ollama_list_error": list_error,
        "reachable": live.get("reachable"),
        "user_message": live.get("user_message"),
        "default_model": live.get("default_model"),
        "ollama_models_env": os.environ.get("OLLAMA_MODELS") or "",
        "disk_manifests": disk,
        "configured_on_disk": configured in disk,
        "configured_in_ollama_list": configured in listed,
        "note": (
            "シェルの OLLAMA_MODELS と、起動中 ollama serve が見ている場所が違うと "
            "list が空になり 404 になる。pipeline.yaml は読んでいない変更をしていない。"
        ),
    }


def as_json() -> str:
    return json.dumps(describe_ollama_env(), ensure_ascii=False, indent=2)
