"""Validate Skill registry and Goal Handoff contract examples."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = REPO_ROOT / "registry"
SCHEMA_DIR = REGISTRY_DIR / "schema"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(instance: dict, schema: dict, label: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    assert not errors, f"{label} schema errors: " + "; ".join(error.message for error in errors)


def test_skills_registry_matches_schema() -> None:
    registry = _load_json(REGISTRY_DIR / "skills.json")
    schema = _load_json(SCHEMA_DIR / "skills.schema.json")
    _validate(registry, schema, "registry/skills.json")

    skill_ids = {item["id"] for item in registry["skills"]}
    assert skill_ids == {
        "grill-me",
        "write-prd",
        "graph-engineering",
        "tech-spec",
        "planning-and-task-breakdown",
        "goal-handoff",
        "session-start",
    }

    for skill in registry["skills"]:
        assert Path(skill["path"]).as_posix() == skill["path"]
        assert (REPO_ROOT / skill["path"]).is_file(), skill["path"]

    for alias, skill_id in registry["alias_index"].items():
        assert skill_id in skill_ids, alias

    for composition in registry["compositions"]:
        for step in composition["steps"]:
            assert step in skill_ids, composition["id"]


def test_goal_handoff_trial_packet_matches_schema() -> None:
    schema = _load_json(SCHEMA_DIR / "goal_handoff.schema.json")
    packet = _load_json(
        REPO_ROOT / "docs/handoffs/gh-20260910T094912Z-session-start-skill.json"
    )
    _validate(packet, schema, "docs/handoffs/gh-20260910T094912Z-session-start-skill.json")
    assert packet["status"] == "ready"


def test_goal_handoff_example_matches_schema() -> None:
    registry = _load_json(REGISTRY_DIR / "skills.json")
    contract = registry["output_contracts"]["goal_handoff"]
    example = _load_json(REPO_ROOT / contract["example_path"])
    schema = _load_json(REPO_ROOT / contract["schema_path"])
    _validate(example, schema, contract["example_path"])
