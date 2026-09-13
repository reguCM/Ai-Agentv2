from __future__ import annotations

from pathlib import Path

BINARY_SNIFF_BYTES = 8192


def find_repo_root(*, anchor: Path | None = None) -> Path:
    """Locate repository root via registry/tools.json marker."""
    start = (anchor or Path(__file__)).resolve()
    candidates = [start, *start.parents]
    for base in candidates:
        marker = base / "registry" / "tools.json"
        if marker.is_file():
            return base
    raise RuntimeError("repository root not found (registry/tools.json missing)")


def has_parent_segment(raw_path: str) -> bool:
    return ".." in Path(raw_path).parts


def resolve_repo_path(raw_path: str, repo_root: Path) -> Path:
    """Resolve input path under repo root without following symlinks."""
    candidate = Path(raw_path)
    root = repo_root.resolve()
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    return (root / candidate).resolve(strict=False)


def is_under_root(resolved: Path, root: Path) -> bool:
    try:
        resolved.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def match_allowlist_root(
    resolved: Path,
    allowlist_roots: tuple[tuple[str, Path], ...],
) -> str | None:
    """Return the most specific (deepest) matching allowlist root id."""
    target = resolved.resolve()
    best_id: str | None = None
    best_len = -1
    for root_id, root_path in allowlist_roots:
        root_resolved = root_path.resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError:
            continue
        length = len(root_resolved.parts)
        if length > best_len:
            best_len = length
            best_id = root_id
    return best_id


def to_repo_relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def is_probably_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            chunk = handle.read(BINARY_SNIFF_BYTES)
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    if not chunk:
        return False
    textish = sum(1 for b in chunk if b in (9, 10, 13) or 32 <= b <= 126 or b >= 128)
    return (textish / len(chunk)) < 0.85
