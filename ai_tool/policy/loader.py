"""開発 Policy の機械契約を読む。ファイルがあるだけでは参照したことにしない。

Local Agent adapter source: development_policy.json
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from ai_tool.policy.paths import policy_json_path

REQUIRED_KEYS = (
    "policy_id",
    "version",
    "item_statuses",
    "completion",
    "human_decision_required_when",
    "definition_boundary",
    "distribution",
)


class PolicyLoadError(RuntimeError):
    """契約ファイルが読めない。完成判定は禁止。"""


def load_development_policy(*, path=None) -> dict[str, Any]:
    target = path or policy_json_path()
    try:
        raw = target.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyLoadError(f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyLoadError("policy が object ではない")
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise PolicyLoadError("required keys missing: " + ", ".join(missing))
    statuses = data.get("item_statuses")
    if not isinstance(statuses, list) or not statuses:
        raise PolicyLoadError("item_statuses が空")
    return data


def _distribution(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("distribution")
    if not isinstance(value, dict):
        raise PolicyLoadError("distribution が object ではない")
    for key in ("schema_version", "policy_version", "canonical_files", "consumers"):
        if key not in value:
            raise PolicyLoadError(f"distribution.{key} がない")
    if not isinstance(value["canonical_files"], list) or not value["canonical_files"]:
        raise PolicyLoadError("distribution.canonical_files が空")
    if not isinstance(value["consumers"], dict) or not value["consumers"]:
        raise PolicyLoadError("distribution.consumers が空")
    return value


def _safe_repo_file(root: Path, relative_path: str) -> Path:
    relative = Path(str(relative_path))
    if relative.is_absolute() or ".." in relative.parts:
        raise PolicyLoadError(f"unsafe repository policy path: {relative_path}")
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise PolicyLoadError(f"policy path escapes repository: {relative_path}") from exc
    return target


def policy_identity(*, path=None, repo_root=None) -> dict[str, Any]:
    """Return deterministic identity for the canonical policy file set."""
    target = Path(path) if path is not None else policy_json_path()
    root = Path(repo_root).resolve() if repo_root is not None else target.resolve().parents[2]
    data = load_development_policy(path=target)
    distribution = _distribution(data)
    canonical_files = [str(item) for item in distribution["canonical_files"]]
    digest = hashlib.sha256()
    for relative_path in sorted(canonical_files):
        canonical = _safe_repo_file(root, relative_path)
        if not canonical.is_file():
            raise PolicyLoadError(f"canonical policy file missing: {relative_path}")
        encoded_name = relative_path.replace("\\", "/").encode("utf-8")
        content = canonical.read_bytes()
        digest.update(len(encoded_name).to_bytes(8, "big"))
        digest.update(encoded_name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return {
        "version": str(distribution["policy_version"]),
        "canonical_hash": f"sha256:{digest.hexdigest()}",
        "loaded": True,
        "canonical_files": canonical_files,
    }


def validate_policy_distribution(*, path=None, repo_root=None) -> dict[str, Any]:
    """Fail closed when a declared consumer is detached or stale."""
    target = Path(path) if path is not None else policy_json_path()
    root = Path(repo_root).resolve() if repo_root is not None else target.resolve().parents[2]
    data = load_development_policy(path=target)
    distribution = _distribution(data)
    identity = policy_identity(path=target, repo_root=root)
    version_marker = f"policy-distribution-version: {identity['version']}"
    checked: dict[str, str] = {}
    for consumer, config in distribution["consumers"].items():
        if not isinstance(config, dict):
            raise PolicyLoadError(f"consumer config is not an object: {consumer}")
        adapter_path = str(config.get("adapter") or "")
        adapter = _safe_repo_file(root, adapter_path)
        if not adapter.is_file():
            raise PolicyLoadError(f"consumer adapter missing: {consumer}: {adapter_path}")
        text = adapter.read_text(encoding="utf-8")
        for reference in config.get("required_references") or []:
            if str(reference) not in text:
                raise PolicyLoadError(
                    f"consumer adapter reference missing: {consumer}: {reference}"
                )
        mode = str(config.get("mode") or "")
        if mode == "reference" and version_marker not in text:
            raise PolicyLoadError(f"consumer adapter version stale: {consumer}")
        if mode == "loader" and "def policy_identity" not in text:
            raise PolicyLoadError(f"consumer loader identity unavailable: {consumer}")
        checked[str(consumer)] = adapter_path
    return {**identity, "consumers": checked, "sync_valid": True}


def policy_identity_snapshot(*, path=None, repo_root=None) -> dict[str, Any]:
    """Artifact-safe identity; failure remains explicit instead of aborting a Run."""
    try:
        return validate_policy_distribution(path=path, repo_root=repo_root)
    except PolicyLoadError as exc:
        return {
            "version": None,
            "canonical_hash": None,
            "loaded": False,
            "canonical_files": [],
            "sync_valid": False,
            "error": str(exc),
        }


def policy_identity_is_current(
    recorded: dict[str, Any], *, current: dict[str, Any] | None = None
) -> bool:
    """Compare an Artifact identity with the current canonical Policy."""
    active = current if current is not None else policy_identity_snapshot()
    return bool(
        recorded.get("loaded") is True
        and active.get("loaded") is True
        and recorded.get("version") == active.get("version")
        and recorded.get("canonical_hash") == active.get("canonical_hash")
    )


def policy_prompt_block(*, path=None) -> str:
    """LLM 入力用の短い機械契約。これだけでは ENFORCED ではない。"""
    try:
        data = load_development_policy(path=path)
    except PolicyLoadError as exc:
        return (
            "development_policy: LOAD_FAILED. "
            f"{exc}. specification_complete is forbidden until policy loads."
        )
    completion = data.get("completion") if isinstance(data.get("completion"), dict) else {}
    compact = {
        "policy_id": data.get("policy_id"),
        "version": data.get("version"),
        "item_statuses": data.get("item_statuses"),
        "min_implementation": data.get("min_implementation"),
        "completion": completion,
        "human_decision_required_when": data.get("human_decision_required_when"),
        "spec_proposal_observation": data.get("spec_proposal_observation"),
        "definition_boundary": data.get("definition_boundary"),
        "concept_definition": data.get("concept_definition"),
        "policy_distribution": policy_identity_snapshot(path=path),
        "note": (
            "pytest PASS is not specification COMPLETE. "
            "CONNECTED is not 'file exists'. "
            "LLM proposal, human revision, human confirmation, and audit reports are not automatic truth. "
            "Do not infer parent_proposal_id from Chat. Dual ID issuance is not automatically a bug. "
            "Clear definitions proceed. Minor ambiguity may proceed as provisional, not as final spec. "
            "Definition expansion signs alone are not a stop. Boundary ambiguity requires a human question "
            "with facts, gap, options, and impacts. "
            "Origin and Current are not ranked. Do not treat newer Current as automatically true, "
            "and do not treat Origin as automatically true. Revert toward Origin is allowed and is not "
            "automatically regression. Do not rewrite Origin. CURRENT / CODE DRIFT needs a human. "
            "learning_method is NOT_DETERMINED."
        ),
    }
    return json.dumps(compact, ensure_ascii=False)
