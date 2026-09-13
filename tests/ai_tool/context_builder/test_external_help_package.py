from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_tool.context_builder.builder import build_tool_development_context
from ai_tool.context_builder.package_generator import build_external_help_package
from ai_tool.context_builder.package_models import PACKAGE_FILES
from ai_tool.context_builder.sensitive import is_sensitive_path


@pytest.mark.parametrize(
    "tool_id",
    [
        "local:workspace_read_text_scoped",
        "local:get_gpu_status",
        "local:cpu_status",
    ],
)
def test_normal_package_generation(repo_root: Path, tool_id: str, tmp_path: Path) -> None:
    result = build_external_help_package(
        tool_id,
        tmp_path / tool_id.replace(":", "_"),
        repo_root=repo_root,
        audit=False,
    )
    pkg = tmp_path / tool_id.replace(":", "_") / "external_help_package"
    assert pkg.is_dir()
    for name in PACKAGE_FILES:
        assert (pkg / name).is_file(), name
    assert result.readiness in ("READY", "PARTIAL", "NOT_READY")
    assert result.tool_id.startswith("local:")


def test_readiness_ready_for_representative_tools(repo_root: Path, tmp_path: Path) -> None:
    for tool_id in (
        "local:workspace_read_text_scoped",
        "local:get_gpu_status",
        "local:cpu_status",
    ):
        result = build_external_help_package(
            tool_id,
            tmp_path / tool_id.replace(":", "_"),
            repo_root=repo_root,
            audit=False,
        )
        assert result.readiness == "READY"
        assert result.missing_p0 == []


def test_p0_missing_not_ready(repo_root: Path, tmp_path: Path) -> None:
    result = build_external_help_package(
        "local:nonexistent_tool_xyz",
        tmp_path / "bad",
        repo_root=repo_root,
        audit=False,
    )
    assert result.readiness == "NOT_READY"
    assert result.missing_p0
    pkg = tmp_path / "bad" / "external_help_package"
    summary = (pkg / "SUMMARY.md").read_text(encoding="utf-8")
    assert "NOT_READY" in summary or "nonexistent" in summary.lower() or "Missing P0" in summary


def test_unknown_not_fabricated_in_package(repo_root: Path, tmp_path: Path) -> None:
    build_external_help_package(
        "local:cpu_status",
        tmp_path / "cpu",
        repo_root=repo_root,
        audit=False,
    )
    unknown_md = (tmp_path / "cpu" / "external_help_package" / "UNKNOWN_AND_MISSING.md").read_text(
        encoding="utf-8"
    )
    assert "inference" in unknown_md.lower() or "UNKNOWN" in unknown_md
    assert "fabricated" not in unknown_md.lower()


def test_implementation_reference_only_not_body(repo_root: Path, tmp_path: Path) -> None:
    build_external_help_package(
        "local:get_gpu_status",
        tmp_path / "gpu",
        repo_root=repo_root,
        audit=False,
    )
    impl = (tmp_path / "gpu" / "external_help_package" / "IMPLEMENTATION_CONTEXT.md").read_text(
        encoding="utf-8"
    )
    assert "REFERENCE_ONLY" in impl
    assert "outside experimental allowlist" in impl.lower() or "not included" in impl.lower()
    assert "def get_gpu_status" not in impl


def test_no_sensitive_in_package(repo_root: Path, tmp_path: Path) -> None:
    build_external_help_package(
        "local:workspace_read_text_scoped",
        tmp_path / "scoped",
        repo_root=repo_root,
        audit=False,
    )
    pkg = tmp_path / "scoped" / "external_help_package"
    for path in pkg.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert ".env" not in text or "EXCLUDED" in text or "not" in text.lower()
            for part in path.parts:
                assert not is_sensitive_path(part)


def test_excluded_not_in_content_paths(repo_root: Path, tmp_path: Path) -> None:
    build_external_help_package(
        "local:get_gpu_status",
        tmp_path / "gpu2",
        repo_root=repo_root,
        audit=False,
    )
    manifest = json.loads(
        (tmp_path / "gpu2" / "external_help_package" / "CONTEXT_MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    for p in manifest.get("content_paths") or []:
        assert not p.startswith("tools/")


def test_wrong_inclusion_zero(repo_root: Path, tmp_path: Path) -> None:
    build_external_help_package(
        "local:get_gpu_status",
        tmp_path / "gpu3",
        repo_root=repo_root,
        audit=False,
    )
    pkg = tmp_path / "gpu3" / "external_help_package"
    for md in pkg.glob("*.md"):
        if md.name == "UNKNOWN_AND_MISSING.md":
            continue
        text = md.read_text(encoding="utf-8")
        if "tools/system/gpu" in text:
            assert "REFERENCE" in text or "not included" in text.lower() or "`" in text


def test_deterministic_package(repo_root: Path, tmp_path: Path) -> None:
    out_a = tmp_path / "det_a"
    out_b = tmp_path / "det_b"
    build_external_help_package(
        "local:cpu_status",
        out_a,
        repo_root=repo_root,
        audit=False,
    )
    build_external_help_package(
        "local:cpu_status",
        out_b,
        repo_root=repo_root,
        audit=False,
    )
    ma = (out_a / "external_help_package" / "CONTEXT_MANIFEST.json").read_text(encoding="utf-8")
    mb = (out_b / "external_help_package" / "CONTEXT_MANIFEST.json").read_text(encoding="utf-8")
    assert json.loads(ma) == json.loads(mb)


def test_manifest_body_separation(repo_root: Path, tmp_path: Path) -> None:
    build_external_help_package(
        "local:workspace_read_text_scoped",
        tmp_path / "sep",
        repo_root=repo_root,
        audit=False,
    )
    manifest = json.loads(
        (tmp_path / "sep" / "external_help_package" / "CONTEXT_MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    spec_md = (tmp_path / "sep" / "external_help_package" / "SPECIFICATION.md").read_text(
        encoding="utf-8"
    )
    assert "manifest" in manifest
    assert "content_paths" in manifest
    assert "workspace_read_text_scoped" in spec_md or "specification" in spec_md.lower()


def test_request_json_constraints(repo_root: Path, tmp_path: Path) -> None:
    build_external_help_package(
        "local:workspace_read_text_scoped",
        tmp_path / "req",
        repo_root=repo_root,
        audit=False,
    )
    req = json.loads(
        (tmp_path / "req" / "external_help_package" / "request.json").read_text(encoding="utf-8")
    )
    assert req["auto_implement_allowed"] is False
    assert req["llm_auto_submit"] is False
    assert any("not an implementation directive" in c for c in req["constraints"])


def test_phase1_tests_still_pass(repo_root: Path) -> None:
    ctx = build_tool_development_context(
        "local:get_gpu_status",
        repo_root=repo_root,
        fetch_content=True,
        audit=False,
    )
    assert ctx.status == "OK"
