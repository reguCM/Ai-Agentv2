from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ai_tool.mission_memory.paths import MissionMemoryError
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version, validate_mission


def _mission(**overrides: Any) -> dict[str, Any]:
    record = {
        "schema_version": schema_version(),
        "mission_id": "m1",
        "original_goal": "このPCで動くテトリスを作りたい",
        "explicit_conditions": [],
        "explicit_constraints": [],
        "user_confirmed_supplements": [],
    }
    record.update(overrides)
    return record


def _execution(**overrides: Any) -> dict[str, Any]:
    record = {
        "schema_version": schema_version(),
        "execution_id": "x1",
        "mission_id": "m1",
        "execution_sequence": 1,
        "result_determination": "undetermined",
        "execution_end_state_judgment": "not_judged",
        "goal_achievement_performed": False,
        "stop_reason": "RUNTIME_ERROR",
        "unresolved_items": [],
        "evidence_refs": [],
    }
    record.update(overrides)
    return record


def _evidence(**overrides: Any) -> dict[str, Any]:
    record = {
        "schema_version": schema_version(),
        "persistent_evidence_id": "pe1",
        "created_in_mission_id": "m1",
        "created_by_execution_id": "x1",
        "source_type": "file",
        "source": "docs/example.md",
        "summary": "ファイルを読んだ要約",
        "observed_at": "2026-09-10T02:00:00Z",
    }
    record.update(overrides)
    return record


def test_store_requires_injected_root(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    assert store.paths.root == tmp_path / "memory"
    assert "agent_missions" not in str(store.paths.root)


def test_default_root_is_local_state_not_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ai_tool.mission_memory.paths import (
        DEFAULT_STORE_RELATIVE,
        MISSION_MEMORY_DIR_ENV,
        default_store_root,
    )

    monkeypatch.delenv(MISSION_MEMORY_DIR_ENV, raising=False)
    root = default_store_root()
    assert root.as_posix().endswith("local_state/mission_memory")
    assert "runs" not in DEFAULT_STORE_RELATIVE.parts
    repo = Path(__file__).resolve().parents[3]
    gitignore = (repo / ".gitignore").read_text(encoding="utf-8")
    assert "local_state/mission_memory/" in gitignore


def test_env_overrides_default_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_tool.mission_memory.paths import MISSION_MEMORY_DIR_ENV, default_store_root

    monkeypatch.setenv(MISSION_MEMORY_DIR_ENV, str(tmp_path / "override"))
    assert default_store_root() == tmp_path / "override"
    store = MissionMemoryStore.from_default()
    assert store.paths.root == tmp_path / "override"


def test_roundtrip_mission_execution_evidence(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission())
    store.put_evidence(_evidence())
    store.put_execution(_execution(evidence_refs=["pe1"]))
    loaded_mission = store.get_mission("m1")
    loaded_execution = store.get_execution("m1", "x1")
    loaded_evidence = store.get_evidence("pe1")
    assert loaded_mission == _mission()
    assert loaded_execution == _execution(evidence_refs=["pe1"])
    assert loaded_evidence == _evidence()
    assert loaded_evidence is not None
    assert loaded_evidence["observed_at"] == "2026-09-10T02:00:00Z"
    assert "persisted_at" not in loaded_evidence


def test_evidence_file_is_not_under_mission_directory(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission())
    path = store.put_evidence(_evidence())
    assert path.parent == store.paths.evidence_dir()
    assert store.paths.mission_dir("m1") not in path.parents


def test_original_goal_cannot_be_overwritten(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission())
    updated = _mission(
        user_confirmed_supplements=[{"text": "規模は小さく", "source": "grill"}]
    )
    store.put_mission(updated)
    assert store.get_mission("m1") == updated
    with pytest.raises(MissionMemoryError) as caught:
        store.put_mission(_mission(original_goal="別のGoal"))
    assert caught.value.code == "ORIGINAL_GOAL_IMMUTABLE"
    assert store.get_mission("m1") == updated


def test_execution_and_evidence_are_create_only(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission())
    store.put_evidence(_evidence())
    store.put_execution(_execution(evidence_refs=["pe1"]))
    with pytest.raises(MissionMemoryError) as evidence_caught:
        store.put_evidence(_evidence())
    assert evidence_caught.value.code == "ALREADY_EXISTS"
    with pytest.raises(MissionMemoryError) as execution_caught:
        store.put_execution(_execution(evidence_refs=["pe1"]))
    assert execution_caught.value.code == "ALREADY_EXISTS"


def test_list_executions_uses_sequence_not_filename(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission())
    store.put_execution(_execution(execution_id="x10", execution_sequence=2))
    store.put_execution(_execution(execution_id="x2", execution_sequence=1))
    listed = store.list_executions("m1")
    assert [item["execution_id"] for item in listed] == ["x2", "x10"]
    assert store.next_execution_sequence("m1") == 3


def test_put_execution_requires_mission(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    with pytest.raises(MissionMemoryError) as caught:
        store.put_execution(_execution())
    assert caught.value.code == "NOT_FOUND"
    assert store.get_execution("m1", "x1") is None


def test_put_evidence_allows_missing_creating_execution(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission())
    store.put_evidence(_evidence(created_by_execution_id="x-not-written-yet"))
    assert store.get_evidence("pe1") is not None


def test_put_execution_rejects_unresolved_evidence_ref(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission())
    with pytest.raises(MissionMemoryError) as caught:
        store.put_execution(_execution(evidence_refs=["pe-missing"]))
    assert caught.value.code == "VALIDATION_REJECTED"
    assert store.get_execution("m1", "x1") is None


def test_cross_mission_evidence_ref_roundtrip(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission(mission_id="m-other"))
    store.put_evidence(
        _evidence(
            persistent_evidence_id="pe-other",
            created_in_mission_id="m-other",
            created_by_execution_id="x-other",
        )
    )
    store.put_mission(_mission())
    store.put_execution(_execution(evidence_refs=["pe-other"]))
    loaded = store.get_execution("m1", "x1")
    assert loaded is not None
    assert loaded["evidence_refs"] == ["pe-other"]


def test_invalid_record_is_not_written(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    bad = _mission()
    del bad["explicit_conditions"]
    with pytest.raises(MissionMemoryError) as caught:
        store.put_mission(bad)
    assert caught.value.code == "VALIDATION_REJECTED"
    assert store.get_mission("m1") is None
    assert validate_mission(_mission()).verdict == "ACCEPT"


def test_path_escape_id_is_rejected(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    with pytest.raises(MissionMemoryError) as caught:
        store.put_mission(_mission(mission_id="../outside"))
    assert caught.value.code == "INVALID_ID"
    assert not (tmp_path / "outside").exists()


def test_duplicate_sequence_is_not_written(tmp_path: Path) -> None:
    store = MissionMemoryStore(tmp_path / "memory")
    store.put_mission(_mission())
    store.put_execution(_execution(execution_id="x1", execution_sequence=1))
    with pytest.raises(MissionMemoryError) as caught:
        store.put_execution(_execution(execution_id="x2", execution_sequence=1))
    assert caught.value.code == "VALIDATION_REJECTED"
    assert store.get_execution("m1", "x2") is None
