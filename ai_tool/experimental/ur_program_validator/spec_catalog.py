"""URScript spec catalog — minimal PoC, provenance-backed."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_tool.experimental.ur_program_validator.official_sources import collect_official_sources


@dataclass
class FunctionSpec:
    name: str
    min_args: int
    max_args: int
    arg_types: list[str]
    polyscope_versions: list[str]
    deprecated_in: str = ""
    source_url: str = ""
    source_title: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "min_args": self.min_args,
            "max_args": self.max_args,
            "arg_types": self.arg_types,
            "polyscope_versions": self.polyscope_versions,
            "deprecated_in": self.deprecated_in,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "notes": self.notes,
        }


@dataclass
class SpecCatalog:
    robot: str
    polyscope_version: str
    urscript_version: str
    functions: dict[str, FunctionSpec] = field(default_factory=dict)
    keywords: set[str] = field(default_factory=set)
    provenance: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "robot": self.robot,
            "polyscope_version": self.polyscope_version,
            "urscript_version": self.urscript_version,
            "functions": {k: v.to_dict() for k, v in self.functions.items()},
            "keywords": sorted(self.keywords),
            "provenance": self.provenance,
        }


def build_catalog(
    *,
    polyscope_version: str = "5.15",
    robot: str = "UR3e",
) -> SpecCatalog:
    """
    Minimal catalog from official fixture evidence + PoC scope.
    Not a complete URScript reference — expanded only from observed sources.
    """
    src = collect_official_sources()[0]
    base_url = src.source_url
    base_title = src.source_title

    functions = {
        "movej": FunctionSpec(
            name="movej",
            min_args=2,
            max_args=4,
            arg_types=["pose", "acceleration", "speed", "blend"],
            polyscope_versions=["5.x"],
            source_url=base_url,
            source_title=base_title,
            notes="Joint move — observed in official fixture excerpt",
        ),
        "movel": FunctionSpec(
            name="movel",
            min_args=2,
            max_args=4,
            arg_types=["pose", "acceleration", "speed", "blend"],
            polyscope_versions=["5.x"],
            source_url=base_url,
            source_title=base_title,
        ),
        "set_digital_out": FunctionSpec(
            name="set_digital_out",
            min_args=2,
            max_args=2,
            arg_types=["pin", "value"],
            polyscope_versions=["5.x"],
            source_url=base_url,
            source_title=base_title,
        ),
        "sleep": FunctionSpec(
            name="sleep",
            min_args=1,
            max_args=1,
            arg_types=["seconds"],
            polyscope_versions=["5.x"],
            source_url=base_url,
            source_title=base_title,
            notes="Common builtin — verify full manual for target version",
        ),
        "legacy_move": FunctionSpec(
            name="legacy_move",
            min_args=1,
            max_args=2,
            arg_types=["pose"],
            polyscope_versions=["5.0"],
            deprecated_in="5.10",
            source_url=base_url,
            source_title=base_title,
            notes="Synthetic version-diff example for PoC T6 — not verified against live manual",
        ),
    }

    return SpecCatalog(
        robot=robot,
        polyscope_version=polyscope_version,
        urscript_version=f"URScript/{polyscope_version}",
        functions=functions,
        keywords={"def", "end", "Thread", "if", "else", "while", "return"},
        provenance=[s.to_dict() for s in collect_official_sources()],
    )
