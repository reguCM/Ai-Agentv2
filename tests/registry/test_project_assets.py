"""Validate project governance asset registry and generated SYSTEM_ASSET_INDEX."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "registry" / "project_assets.json"
SCHEMA_PATH = REPO_ROOT / "registry" / "schema" / "project_assets.schema.json"
INDEX_PATH = REPO_ROOT / "docs" / "SYSTEM_ASSET_INDEX.md"
GENERATOR = REPO_ROOT / "tools" / "generate_system_asset_index.py"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(instance: dict, schema: dict, label: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    assert not errors, f"{label} schema errors: " + "; ".join(error.message for error in errors)


def test_project_assets_registry_matches_schema() -> None:
    registry = _load_json(REGISTRY_PATH)
    schema = _load_json(SCHEMA_PATH)
    _validate(registry, schema, "registry/project_assets.json")


def test_project_assets_asset_ids_unique() -> None:
    registry = _load_json(REGISTRY_PATH)
    ids = [row["asset_id"] for row in registry["assets"]]
    assert len(ids) == len(set(ids)), "duplicate asset_id: " + ", ".join(sorted(set(ids)))


def test_project_assets_repository_paths_exist() -> None:
    registry = _load_json(REGISTRY_PATH)
    missing: list[str] = []
    for row in registry["assets"]:
        path = row.get("path")
        if not path:
            continue
        if "EXTERNAL" in row.get("scope", []) and "REPOSITORY" not in row.get("scope", []):
            continue
        target = REPO_ROOT / path
        if not target.exists():
            missing.append(path)
    assert not missing, "missing paths: " + ", ".join(missing)


def test_project_assets_source_of_truth_paths_not_broken() -> None:
    registry = _load_json(REGISTRY_PATH)
    broken: list[str] = []
    for row in registry["assets"]:
        sot = row["source_of_truth"]
        if sot.startswith("NOT_OBSERVED"):
            continue
        for token in re.findall(r"`([^`]+)`", sot):
            if "/" in token and not token.startswith("http"):
                if not (REPO_ROOT / token).exists():
                    broken.append(f"{row['asset_id']}: `{token}`")
        primary = sot.split(" + ")[0].split(" (")[0].strip()
        if "/" in primary and not primary.startswith("NOT_"):
            if (REPO_ROOT / primary).exists():
                continue
            if primary.endswith(".json") or primary.endswith(".md") or primary.endswith(".mdc") or primary.endswith(".py"):
                if not (REPO_ROOT / primary).exists():
                    broken.append(f"{row['asset_id']}: {primary}")
    assert not broken, "broken source_of_truth refs: " + "; ".join(broken[:12])


def test_generate_system_asset_index_is_deterministic() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from generate_system_asset_index import render_markdown

    registry = _load_json(REGISTRY_PATH)
    first = render_markdown(registry)
    second = render_markdown(registry)
    assert first == second


def test_system_asset_index_matches_registry_generator() -> None:
    proc = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_manual_markdown_edit_detectable_via_digest_comment() -> None:
    registry = _load_json(REGISTRY_PATH)
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from generate_system_asset_index import registry_content_digest, render_markdown

    expected_digest = registry_content_digest(registry)
    text = INDEX_PATH.read_text(encoding="utf-8")
    match = re.search(r"registry-assets-sha256: ([a-f0-9]{64})", text)
    assert match, "generated index missing registry-assets-sha256 comment"
    assert match.group(1) == expected_digest

    tampered = text + "\n<!-- manual edit -->\n"
    assert tampered != render_markdown(registry)
