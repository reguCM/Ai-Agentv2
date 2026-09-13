"""Map Tool Spec → Experimental module. Not Production. Not a Reasoning Core.

The generated client is a fixture stand-in for technology A (LibA):
JSON object in, dict out. It records runtime / license / unknowns from the
spec and does not claim the API is feasible, safe, or correct.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
DEFAULT_DEST = _REPO / "ai_tool" / "experimental" / "liba_demo_tool"


def _python_token(runtime: str) -> str:
    m = re.search(r"3\.\d+(?:\.\d+)?", str(runtime or ""))
    return m.group(0) if m else "UNKNOWN"


def render_client_source(spec: dict[str, Any]) -> str:
    name = str(spec.get("tool_name") or "tool_liba")
    runtime = _python_token(str(spec.get("runtime") or spec.get("environment", {}).get("python") or ""))
    license_ = str(spec.get("license") or "UNKNOWN")
    version = str(spec.get("version") or "UNKNOWN")
    unknowns = list(spec.get("unknowns") or [])
    provenance = str(spec.get("provenance_note") or "Draft from Web Research — not verified by execution")
    unk_repr = repr(unknowns)
    return f'''"""Experimental LibA demo client — generated from ToolSpecificationDraft.

Not a Production Tool. Not connected to real hardware or live LibA.
Basic usage stand-in: JSON object text → dict.
"""
from __future__ import annotations

import json
from typing import Any

TOOL_NAME = {name!r}
RUNTIME_PYTHON = {runtime!r}
LICENSE = {license_!r}
LIBRARY_VERSION = {version!r}
PROVENANCE_NOTE = {provenance!r}
UNKNOWN = {unk_repr}


def parse_a_payload(text: str) -> dict[str, Any]:
    """Fixture API for technology A: a JSON object is the basic payload."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("LibA fixture expects a JSON object")
    return data
'''


def write_experimental_client(
    spec: dict[str, Any],
    dest_dir: Path | None = None,
) -> dict[str, Any]:
    dest = Path(dest_dir) if dest_dir is not None else DEFAULT_DEST
    dest.mkdir(parents=True, exist_ok=True)
    init_path = dest / "__init__.py"
    client_path = dest / "client.py"
    source = render_client_source(spec)
    if not init_path.exists():
        init_path.write_text(
            '"""Experimental fixture Tool for technology A (LibA). Not Production."""\n',
            encoding="utf-8",
        )
    client_path.write_text(source, encoding="utf-8")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return {
        "path": str(client_path),
        "tool_name": spec.get("tool_name"),
        "runtime_python": _python_token(str(spec.get("runtime") or "")),
        "license": spec.get("license"),
        "sha256_16": digest,
        "label": "EXPERIMENTAL",
        "auto_executable_claim": False,
    }


_RUNTIME_LINE = re.compile(r"^RUNTIME_PYTHON = .+$", re.M)
_UNKNOWN_LINE = re.compile(r"^UNKNOWN = .+$", re.M)
_PAYLOAD_FN = re.compile(
    r"def parse_a_payload\(text: str\) -> dict\[str, Any\]:.*?(?=\n(?:def |\Z))",
    re.S,
)


def patch_runtime_only(
    spec: dict[str, Any],
    dest_dir: Path | None = None,
) -> dict[str, Any]:
    """Change RUNTIME_PYTHON / UNKNOWN only. Do not rewrite the payload function."""
    dest = Path(dest_dir) if dest_dir is not None else DEFAULT_DEST
    client_path = dest / "client.py"
    if not client_path.exists():
        return {**write_experimental_client(spec, dest_dir=dest), "patch": "created"}
    before = client_path.read_text(encoding="utf-8")
    body_before = _PAYLOAD_FN.search(before)
    runtime = _python_token(str(spec.get("runtime") or ""))
    unknowns = list(spec.get("unknowns") or [])
    after = _RUNTIME_LINE.sub(f"RUNTIME_PYTHON = {runtime!r}", before, count=1)
    if _UNKNOWN_LINE.search(after):
        after = _UNKNOWN_LINE.sub(f"UNKNOWN = {unknowns!r}", after, count=1)
    client_path.write_text(after, encoding="utf-8")
    body_after = _PAYLOAD_FN.search(after)
    body_ok = bool(body_before and body_after and body_before.group(0) == body_after.group(0))
    digest = hashlib.sha256(after.encode("utf-8")).hexdigest()[:16]
    return {
        "path": str(client_path),
        "runtime_python": runtime,
        "sha256_16": digest,
        "patch": "runtime_only",
        "payload_function_unchanged": body_ok,
        "copied_old_python_evidence": False,
        "label": "EXPERIMENTAL",
    }


def source_contains_spec(source: str, spec: dict[str, Any]) -> dict[str, bool]:
    runtime = _python_token(str(spec.get("runtime") or ""))
    return {
        "tool_name": str(spec.get("tool_name") or "") in source,
        "runtime": runtime != "UNKNOWN" and runtime in source,
        "license": str(spec.get("license") or "") in source,
        "provenance": "not" in source.lower() and "verif" in source.lower(),
    }
