"""Verification baselines and fingerprint comparison for project assets (Phase 2A.1)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "reports" / "verification_evidence"

PATH_LIKE = re.compile(r"^[a-zA-Z0-9_./-]+\.(?:py|md|mdc|json|yaml|yml|txt)$")
PATH_LIKE_JSON = re.compile(r"^[a-zA-Z0-9_./-]+\.schema\.json$")

REASON_DIRECT = "DIRECT_CONTENT_CHANGE"
REASON_DEPENDENCY = "DEPENDENCY_CHANGE"
REASON_DELETED = "PATH_DELETED"
REASON_RENAMED = "PATH_RENAMED"
REASON_BASELINE_MISSING = "BASELINE_MISSING"
REASON_WATCH_UNKNOWN = "WATCH_MAPPING_UNKNOWN"


def _norm_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        return normalized[2:]
    return normalized


def _looks_like_repo_path(token: str) -> bool:
    token = _norm_path(token)
    if not token or " " in token or token.startswith("NOT_"):
        return False
    if token.endswith("/"):
        return True
    if PATH_LIKE.match(token) or PATH_LIKE_JSON.match(token):
        return True
    if "/" not in token:
        return False
    return "." not in Path(token).name


def _extract_paths_from_source_of_truth(value: str) -> list[str]:
    if not value or value.startswith("NOT_OBSERVED"):
        return []
    paths: list[str] = []
    for token in re.findall(r"`([^`]+)`", value):
        if _looks_like_repo_path(token):
            paths.append(_norm_path(token))
    primary = value.split(" + ")[0].split(" (")[0].strip()
    if _looks_like_repo_path(primary):
        paths.append(_norm_path(primary))
    return paths


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def git_head_revision(repo_root: Path) -> str:
    proc = _run_git(repo_root, "rev-parse", "HEAD")
    return proc.stdout.strip() if proc.returncode == 0 else "NOT_OBSERVED"


def _git_state_for_path(repo_root: Path, path: str) -> dict[str, Any]:
    rel = _norm_path(path)
    state: dict[str, Any] = {"path": rel}
    proc = _run_git(repo_root, "ls-files", "--error-unmatch", rel)
    state["tracked"] = proc.returncode == 0
    proc = _run_git(repo_root, "status", "--porcelain", "--", rel)
    porcelain = (proc.stdout or "").strip()
    state["porcelain"] = porcelain or None
    if porcelain:
        state["index_status"] = porcelain[:2].strip() or porcelain[0:2]
    return state


def content_fingerprint(repo_root: Path, path: str) -> tuple[bool, str]:
    target = repo_root / _norm_path(path)
    if not target.is_file():
        return False, "MISSING"
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return True, f"sha256:{digest}"


def build_direct_watch_paths(asset: dict[str, Any], assets_by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Direct staleness watch paths. Does not include related_assets."""
    paths: list[str] = []
    path = asset.get("path")
    if isinstance(path, str) and _looks_like_repo_path(path):
        paths.append(_norm_path(path))
    paths.extend(_extract_paths_from_source_of_truth(str(asset.get("source_of_truth") or "")))
    for item in asset.get("related_tests") or []:
        token = str(item).strip()
        if _looks_like_repo_path(token):
            paths.append(_norm_path(token))
    for item in asset.get("related_validators") or []:
        token = str(item).strip()
        if _looks_like_repo_path(token):
            paths.append(_norm_path(token))
    for policy_id in asset.get("related_policies") or []:
        ref = assets_by_id.get(str(policy_id))
        if ref and isinstance(ref.get("path"), str) and _looks_like_repo_path(ref["path"]):
            paths.append(_norm_path(ref["path"]))
    seen: set[str] = set()
    unique: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def resolve_freshness_dependency_paths(
    asset: dict[str, Any], assets_by_id: dict[str, dict[str, Any]]
) -> list[tuple[str, str]]:
    """Return (path, dependency_label) for freshness_dependencies only."""
    out: list[tuple[str, str]] = []
    for dep in asset.get("freshness_dependencies") or []:
        if not isinstance(dep, dict):
            continue
        kind = str(dep.get("kind") or "")
        if kind == "path" and _looks_like_repo_path(str(dep.get("path") or "")):
            out.append((_norm_path(str(dep["path"])), f"freshness_dependencies:path:{dep['path']}"))
        elif kind == "asset_id":
            dep_id = str(dep.get("asset_id") or "")
            ref = assets_by_id.get(dep_id)
            if ref is None:
                continue
            for watch_path in build_direct_watch_paths(ref, assets_by_id):
                out.append((watch_path, f"freshness_dependencies:asset_id:{dep_id}"))
    return out


def snapshot_watch_path(repo_root: Path, path: str) -> dict[str, Any]:
    existence, fingerprint = content_fingerprint(repo_root, path)
    return {
        "path": _norm_path(path),
        "existence": existence,
        "content_fingerprint": fingerprint,
        "git_state_if_available": _git_state_for_path(repo_root, path),
    }


def build_verification_evidence(
    asset: dict[str, Any],
    assets_by_id: dict[str, dict[str, Any]],
    repo_root: Path,
    *,
    verification_id: str,
    verification_method: str,
    verified_revision: str | None = None,
) -> dict[str, Any]:
    watch_paths = build_direct_watch_paths(asset, assets_by_id)
    if not watch_paths:
        raise ValueError(f"No direct watch paths for asset {asset.get('asset_id')}")
    dep_paths = [p for p, _ in resolve_freshness_dependency_paths(asset, assets_by_id)]
    seen: set[str] = set()
    resolved: list[str] = []
    for p in watch_paths + dep_paths:
        if p not in seen:
            seen.add(p)
            resolved.append(p)
    verified_at = datetime.now(timezone.utc).isoformat()
    rev = verified_revision or git_head_revision(repo_root)
    snapshots = [snapshot_watch_path(repo_root, p) for p in resolved]
    return {
        "schema_version": "1",
        "verification_id": verification_id,
        "asset_id": str(asset["asset_id"]),
        "verified_at": verified_at,
        "verified_revision": rev,
        "verification_method": verification_method,
        "resolved_watch_paths": resolved,
        "watch_snapshots": snapshots,
    }


def evidence_path_for_id(evidence_dir: Path, verification_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", verification_id)
    return evidence_dir / f"{safe}.json"


def stable_evidence_path(evidence_dir: Path, asset_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", asset_id)
    return evidence_dir / f"asset_{safe}.json"


def write_evidence_file(evidence: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


class EvidenceHistoryConflictError(ValueError):
    """Historical evidence for verification_id already exists with different content."""


class SameVerificationIdConflictError(ValueError):
    """Same verification_id would be written with different fingerprint content."""


def evidence_payload_digest(evidence: dict[str, Any]) -> str:
    payload = {
        "verification_id": evidence.get("verification_id"),
        "asset_id": evidence.get("asset_id"),
        "verified_at": evidence.get("verified_at"),
        "verified_revision": evidence.get("verified_revision"),
        "verification_method": evidence.get("verification_method"),
        "resolved_watch_paths": evidence.get("resolved_watch_paths"),
        "watch_snapshots": evidence.get("watch_snapshots"),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def history_evidence_path(evidence_dir: Path, asset_id: str, verification_id: str) -> Path:
    safe_asset = re.sub(r"[^a-zA-Z0-9._-]+", "_", asset_id)
    safe_vid = re.sub(r"[^a-zA-Z0-9._-]+", "_", verification_id)
    return evidence_dir / "history" / safe_asset / f"{safe_vid}.json"


def persist_evidence_with_history(
    evidence_dir: Path,
    asset_id: str,
    evidence: dict[str, Any],
) -> Path:
    """Write current snapshot and immutable history entry; enforce verification_id invariants."""
    current_path = stable_evidence_path(evidence_dir, asset_id)
    digest = evidence_payload_digest(evidence)
    verification_id = str(evidence["verification_id"])
    hist_path = history_evidence_path(evidence_dir, asset_id, verification_id)

    if current_path.is_file():
        current = json.loads(current_path.read_text(encoding="utf-8"))
        current_vid = str(current.get("verification_id") or "")
        if current_vid == verification_id and evidence_payload_digest(current) != digest:
            raise SameVerificationIdConflictError(
                f"Refusing to change content under verification_id {verification_id}"
            )
        if current_vid and current_vid != verification_id:
            archive_path = history_evidence_path(evidence_dir, asset_id, current_vid)
            if not archive_path.is_file():
                write_evidence_file(current, archive_path)

    if hist_path.is_file():
        existing_hist = json.loads(hist_path.read_text(encoding="utf-8"))
        if evidence_payload_digest(existing_hist) != digest:
            raise EvidenceHistoryConflictError(
                f"History already has {verification_id} with different content for {asset_id}"
            )
    else:
        write_evidence_file(evidence, hist_path)

    return write_evidence_file(evidence, current_path)


def save_evidence(evidence: dict[str, Any], evidence_dir: Path) -> Path:
    return write_evidence_file(evidence, evidence_path_for_id(evidence_dir, str(evidence["verification_id"])))


def evidence_ref_for_repo(repo_root: Path, saved_path: Path) -> str:
    """Repo-relative POSIX path for evidence_ref (evidence must live under repo_root)."""
    root = repo_root.resolve()
    saved = saved_path.resolve()
    try:
        return saved.relative_to(root).as_posix()
    except ValueError:
        raise ValueError(
            f"Verification evidence must be stored under repo root ({root}); got {saved}"
        ) from None


def load_evidence(repo_root: Path, evidence_ref: str) -> dict[str, Any] | None:
    path = repo_root / _norm_path(evidence_ref)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_snapshots(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> str | None:
    if baseline.get("existence") and not current.get("existence"):
        return REASON_DELETED
    if not baseline.get("existence") and current.get("existence"):
        return REASON_DIRECT
    if baseline.get("content_fingerprint") != current.get("content_fingerprint"):
        return REASON_DIRECT
    return None


def _git_rename_delete_hints(repo_root: Path, verified_revision: str, head: str = "HEAD") -> dict[str, str]:
    hints: dict[str, str] = {}
    proc = _run_git(repo_root, "rev-parse", "--verify", verified_revision)
    if proc.returncode != 0:
        return hints
    for args in (
        ["diff", "--name-status", "-M", f"{verified_revision}..{head}"],
        ["diff", "--cached", "--name-status", "-M"],
        ["diff", "--name-status", "-M"],
    ):
        proc = _run_git(repo_root, *args)
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            status = parts[0]
            if status.startswith("R") and len(parts) >= 3:
                hints[_norm_path(parts[1])] = REASON_RENAMED
                hints[_norm_path(parts[2])] = REASON_RENAMED
            elif status == "D":
                hints[_norm_path(parts[1])] = REASON_DELETED
    return hints


def detect_single_asset(
    asset: dict[str, Any],
    assets_by_id: dict[str, dict[str, Any]],
    repo_root: Path,
    *,
    head: str = "HEAD",
    evidence_by_ref: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    asset_id = str(asset["asset_id"])
    verification = asset.get("verification") or {}
    freshness = str(verification.get("freshness") or "UNKNOWN")
    verified_revision = str(verification.get("verified_revision") or "NOT_OBSERVED")
    evidence_ref = str(verification.get("evidence_ref") or "").strip()

    watch_paths = build_direct_watch_paths(asset, assets_by_id)
    if not watch_paths:
        return {
            "asset_id": asset_id,
            "name": str(asset.get("name") or asset_id),
            "detection_status": "UNKNOWN",
            "current_freshness": freshness,
            "verified_revision": verified_revision,
            "watch_unknown_reason": REASON_WATCH_UNKNOWN,
            "candidates": [],
        }

    evidence: dict[str, Any] | None = None
    if evidence_ref:
        cache = evidence_by_ref or {}
        evidence = cache.get(evidence_ref)
        if evidence is None:
            evidence = load_evidence(repo_root, evidence_ref)
            if evidence_by_ref is not None and evidence is not None:
                evidence_by_ref[evidence_ref] = evidence

    if evidence is None:
        return {
            "asset_id": asset_id,
            "name": str(asset.get("name") or asset_id),
            "detection_status": "UNKNOWN",
            "current_freshness": freshness,
            "verified_revision": verified_revision,
            "watch_unknown_reason": REASON_BASELINE_MISSING,
            "candidates": [
                {
                    "candidate_reason": REASON_BASELINE_MISSING,
                    "evidence_ref": evidence_ref or None,
                }
            ],
        }

    git_hints = _git_rename_delete_hints(repo_root, str(evidence.get("verified_revision") or verified_revision), head)
    baseline_by_path = {row["path"]: row for row in evidence.get("watch_snapshots") or []}
    candidates: list[dict[str, Any]] = []

    for path in watch_paths:
        baseline = baseline_by_path.get(path)
        current = snapshot_watch_path(repo_root, path)
        if baseline is None:
            candidates.append(
                {
                    "changed_path": path,
                    "candidate_reason": REASON_BASELINE_MISSING,
                    "detection_method": "fingerprint_compare",
                }
            )
            continue
        reason = compare_snapshots(baseline, current)
        if reason:
            candidate_reason = git_hints.get(path, reason)
            if candidate_reason == REASON_DIRECT:
                candidate_reason = REASON_DIRECT
            candidates.append(
                {
                    "changed_path": path,
                    "candidate_reason": candidate_reason,
                    "baseline_fingerprint": baseline.get("content_fingerprint"),
                    "current_fingerprint": current.get("content_fingerprint"),
                    "detection_method": "fingerprint_compare",
                    "git_hint": git_hints.get(path),
                }
            )

    for dep_path, dep_label in resolve_freshness_dependency_paths(asset, assets_by_id):
        if dep_path in watch_paths:
            continue
        base = baseline_by_path.get(dep_path)
        dep_evidence: dict[str, Any] | None = None
        if dep_label.startswith("freshness_dependencies:asset_id:"):
            dep_id = dep_label.split(":", 2)[-1]
            dep_asset = assets_by_id.get(dep_id)
            ref = str((dep_asset.get("verification") or {}).get("evidence_ref") or "") if dep_asset else ""
            if ref:
                cache = evidence_by_ref if evidence_by_ref is not None else {}
                dep_evidence = cache.get(ref)
                if dep_evidence is None:
                    dep_evidence = load_evidence(repo_root, ref)
                    if evidence_by_ref is not None and dep_evidence is not None:
                        evidence_by_ref[ref] = dep_evidence
            if base is None and dep_evidence:
                base = {r["path"]: r for r in dep_evidence.get("watch_snapshots") or []}.get(dep_path)
        if base is None:
            continue
        cur = snapshot_watch_path(repo_root, dep_path)
        if compare_snapshots(base, cur):
            candidates.append(
                {
                    "changed_path": dep_path,
                    "candidate_reason": REASON_DEPENDENCY,
                    "match_reason": dep_label,
                    "detection_method": "dependency_fingerprint_compare",
                }
            )

    status = "CHANGE_CANDIDATE" if candidates else "UNCHANGED"
    return {
        "asset_id": asset_id,
        "name": str(asset.get("name") or asset_id),
        "detection_status": status,
        "current_freshness": freshness,
        "verified_revision": verified_revision,
        "evidence_ref": evidence_ref,
        "candidates": candidates,
    }
