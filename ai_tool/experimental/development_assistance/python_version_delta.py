"""Python version replacement overlay — not a Reasoning Core.

Existing extract_slots / plan_follow_up use re.search, so
「Python 3.12ではなくPython 3.13」reads as 3.12 first.

This adapter only parses the replacement. It does not judge
compatibility and is not wired into standard_workflow defaults.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

_PY = re.compile(r"python(?:\s*|は|を)(3\.\d+(?:\.\d+)?)", re.I)
_BARE = re.compile(r"(?<!\d)(3\.\d+(?:\.\d+)?)")
_REPLACE = re.compile(r"ではなく|じゃなく|ではなくて")
_ONLY_CHANGE = re.compile(r"だけ.{0,8}変更|だけ.{0,8}確認|に戻して|へ変更")


@dataclass
class PythonVersionDelta:
    mentioned: list[str]
    selected: str
    replaced_from: str
    replacement_detected: bool
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _collect_versions(requirement: str) -> list[str]:
    named = [m.group(1) for m in _PY.finditer(requirement)]
    if _REPLACE.search(requirement) or _ONLY_CHANGE.search(requirement):
        named.extend(_BARE.findall(requirement))
    return list(dict.fromkeys(named))


def parse_python_version_delta(
    requirement: str,
    session: dict[str, Any] | None = None,
) -> PythonVersionDelta:
    """Read replacement intent. Do not infer unstated versions.

    Optional session.last_python fills replaced_from when the text names
    only the new version (「Pythonだけ3.13に変更」).
    """
    unique = _collect_versions(requirement)
    session_py = str((session or {}).get("last_python") or "")
    if _REPLACE.search(requirement) and len(unique) >= 2:
        return PythonVersionDelta(
            mentioned=unique,
            selected=unique[-1],
            replaced_from=unique[0],
            replacement_detected=True,
            note="Replacement named in text; first-match must not stand in for the new version.",
        )
    if (
        len(unique) == 1
        and session_py
        and session_py != unique[0]
        and (
            _ONLY_CHANGE.search(requirement)
            or re.search(r"python", requirement, re.I)
        )
    ):
        return PythonVersionDelta(
            mentioned=unique,
            selected=unique[0],
            replaced_from=session_py,
            replacement_detected=True,
            note="Named Python differs from session; replaced_from is session, not guessed OS/CUDA.",
        )
    selected = unique[-1] if unique else ""
    return PythonVersionDelta(
        mentioned=unique,
        selected=selected,
        replaced_from="",
        replacement_detected=False,
        note="Single version or none; no replacement overlay.",
    )
