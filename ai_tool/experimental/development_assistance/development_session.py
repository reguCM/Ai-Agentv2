"""Development Session envelope — Experimental adapter, not a Knowledge Base.

Retains named Facets across turns, isolates changed Version evidence,
and records conflicts without picking a winner.

Does not invent Facets. Does not emit feasible / safe / correct.
Not wired into standard_workflow defaults.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ai_tool.experimental.development_assistance.facet_discovery import (
    _cuda_covered,
    _env_key_covered,
    _python_covered,
)
from ai_tool.experimental.development_assistance.pointer_resolution import classify_pointer
from ai_tool.experimental.development_assistance.python_version_delta import parse_python_version_delta
from ai_tool.experimental.development_assistance.research_record import ResearchStore

EvidenceStatus = Literal["confirmed", "UNKNOWN", "MISSING", "historical"]

_CUDA = re.compile(r"cuda(?:\s*|は)(12(?:\.\d+)?)", re.I)
_CERTAIN = re.compile(r"確実に動く|必ず動く|確実に使える|確実に", re.I)


@dataclass
class FacetSlot:
    facet_id: str
    value: str
    evidence: EvidenceStatus
    source: str
    copied_from_old: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VersionEvent:
    from_value: str
    to_value: str
    from_status: EvidenceStatus
    to_status: EvidenceStatus
    copied_evidence: bool
    kept_facets: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DevelopmentSessionState:
    last_research_id: str = ""
    bound_label: str = ""
    facets: dict[str, FacetSlot] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    version_log: list[VersionEvent] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    last_spec: dict[str, Any] | None = None
    last_test: dict[str, Any] | None = None
    tool_path: str = ""
    tool_hash: str = ""
    last_python: str = ""
    last_os: str = ""
    last_environment: str = ""
    last_cuda: str = ""
    awaiting_human_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_research_id": self.last_research_id,
            "bound_label": self.bound_label,
            "facets": {k: v.to_dict() for k, v in self.facets.items()},
            "history": list(self.history),
            "version_log": [e.to_dict() for e in self.version_log],
            "conflicts": list(self.conflicts),
            "last_spec": self.last_spec,
            "last_test": self.last_test,
            "tool_path": self.tool_path,
            "last_python": self.last_python,
            "last_os": self.last_os,
            "last_environment": self.last_environment,
            "last_cuda": self.last_cuda,
            "awaiting_human_review": self.awaiting_human_review,
            "last_test_result": self.last_test,
        }

    def as_session_dict(self) -> dict[str, Any]:
        """Keys extract_slots / pointer code already read."""
        return {
            "last_research_id": self.last_research_id,
            "bound_label": self.bound_label,
            "last_python": self.last_python,
            "last_os": self.last_os,
            "last_environment": self.last_environment,
            "last_cuda": self.last_cuda,
            "last_spec": self.last_spec,
            "tool_path": self.tool_path,
            "last_test_result": self.last_test,
            "awaiting_human_review": self.awaiting_human_review,
        }


def _set_facet(
    state: DevelopmentSessionState,
    facet_id: str,
    value: str,
    evidence: EvidenceStatus,
    source: str,
    *,
    copied: bool = False,
) -> None:
    state.facets[facet_id] = FacetSlot(facet_id, value, evidence, source, copied_from_old=copied)


def attach_research(state: DevelopmentSessionState, research_id: str, label: str = "A") -> None:
    state.last_research_id = research_id
    state.bound_label = label


def seed_from_record(state: DevelopmentSessionState, rec) -> None:
    """Fill session from one ResearchRecord only. Do not merge siblings."""
    from ai_tool.experimental.development_assistance.memory_slice import hydrate_session_slots

    label = str((rec.environment_facts or {}).get("label") or "A")
    attach_research(state, rec.research_id, label)
    slots = hydrate_session_slots(rec)
    if slots.get("python_version"):
        _set_facet(state, "python_version", slots["python_version"], "confirmed", "research_record")
        state.last_python = slots["python_version"]
    if slots.get("os"):
        _set_facet(state, "os", slots["os"], "confirmed", "research_record")
        state.last_os = slots["os"]
        state.last_environment = slots["os"]
    if slots.get("cuda"):
        _set_facet(state, "cuda", slots["cuda"], "confirmed", "research_record")
        state.last_cuda = slots["cuda"]
    if slots.get("license"):
        _set_facet(state, "license", slots["license"], "confirmed", "research_record")


def add_official_vs_third_party_conflict(state: DevelopmentSessionState) -> dict[str, Any]:
    """Record both evidences. Do not pick a winner."""
    conflict = {
        "facet_id": "python_version",
        "evidence_a": {"version": "3.12", "source": "official", "claim": "supported"},
        "evidence_b": {"version": "3.13", "source": "third_party", "claim": "supported"},
        "winner": None,
        "kept": True,
    }
    state.conflicts.append(conflict)
    return conflict


def certainty_reply(requirement: str, state: DevelopmentSessionState) -> dict[str, Any] | None:
    """Never emit feasible / safe / correct. UNKNOWN when evidence is split or missing."""
    if not _CERTAIN.search(requirement):
        return None
    py = parse_python_version_delta(requirement, state.as_session_dict()).selected
    if not py:
        m = re.search(r"3\.\d+", requirement)
        py = m.group(0) if m else ""
    has_conflict = any(c.get("facet_id") == "python_version" for c in state.conflicts)
    slot = state.facets.get("python_version")
    unknown = (
        has_conflict
        or slot is None
        or slot.evidence in {"UNKNOWN", "MISSING"}
        or (py and slot.value != py)
        or (py == "3.13" and has_conflict)
    )
    return {
        "question": requirement,
        "target": py,
        "answer": "UNKNOWN" if unknown else "UNKNOWN",
        "reason": (
            "Official and third-party claims conflict, or official evidence is missing. "
            "Not a feasible/safe/correct verdict."
        ),
        "feasible": None,
        "safe": None,
        "correct": None,
        "conflict_kept": has_conflict,
    }


def apply_requirement(
    state: DevelopmentSessionState,
    requirement: str,
    store: ResearchStore,
) -> dict[str, Any]:
    """Update retained Facets from this requirement only. No LLM invention."""
    pointer = classify_pointer(requirement, store=store, session=state.as_session_dict())
    rec = next((r for r in store.records if r.research_id == state.last_research_id), None)
    delta = parse_python_version_delta(requirement, state.as_session_dict())
    changed: list[str] = []
    retained_before = sorted(state.facets.keys())

    if pointer.status == "BOUND" and pointer.bound_research_id:
        state.last_research_id = pointer.bound_research_id
        if pointer.bound_label:
            state.bound_label = pointer.bound_label
        rec = next((r for r in store.records if r.research_id == state.last_research_id), None)

    if delta.replacement_detected and delta.selected:
        old = state.facets.get("python_version")
        old_val = delta.replaced_from or (old.value if old else "")
        if old:
            hist = old.to_dict()
            hist["evidence"] = "historical"
            state.history.append(hist)
        reverting = any(
            h.get("facet_id") == "python_version"
            and h.get("value") == delta.selected
            and h.get("evidence") in {"confirmed", "historical"}
            for h in state.history
        ) or (old and old.value == delta.selected and old.evidence == "confirmed")
        covered = bool(rec) and _python_covered(rec, delta.selected)
        if reverting and (covered or any(h.get("value") == delta.selected for h in state.history)):
            ev: EvidenceStatus = "confirmed"
            src = "historical_restore"
        elif covered:
            ev = "confirmed"
            src = "research_record"
        else:
            ev = "UNKNOWN"
            src = "replacement_missing"
        _set_facet(state, "python_version", delta.selected, ev, src, copied=False)
        state.last_python = delta.selected
        changed.append("python_version")
        kept = [k for k in state.facets if k != "python_version"]
        state.version_log.append(
            VersionEvent(
                from_value=old_val,
                to_value=delta.selected,
                from_status="historical",
                to_status=ev,
                copied_evidence=False,
                kept_facets=kept,
            )
        )
    elif delta.selected and not delta.replacement_detected:
        covered = bool(rec) and _python_covered(rec, delta.selected)
        ev = "confirmed" if covered else "UNKNOWN"
        _set_facet(
            state,
            "python_version",
            delta.selected,
            ev,
            "research_record" if covered else "named_unverified",
        )
        state.last_python = delta.selected
        changed.append("python_version")

    if re.search(r"windows", requirement, re.I) and not re.search(
        r"(linux|ubuntu).{0,8}(にして|へ|に変更)|ではなく.{0,8}(linux|ubuntu)|じゃなく.{0,8}(linux|ubuntu)",
        requirement,
        re.I,
    ):
        old = state.facets.get("os")
        if old and old.value != "windows":
            hist = old.to_dict()
            hist["evidence"] = "historical"
            state.history.append(hist)
        covered = bool(rec) and _env_key_covered(rec, "os", "windows")
        _set_facet(
            state,
            "os",
            "windows",
            "confirmed" if covered else "UNKNOWN",
            "slot",
        )
        state.last_os = "windows"
        state.last_environment = "windows"
        changed.append("os")
    elif re.search(r"linux|ubuntu", requirement, re.I):
        old = state.facets.get("os")
        if old and old.value not in {"linux", "ubuntu"}:
            hist = old.to_dict()
            hist["evidence"] = "historical"
            state.history.append(hist)
        covered = bool(rec) and (
            _env_key_covered(rec, "os", "linux") or _env_key_covered(rec, "os", "ubuntu")
        )
        _set_facet(
            state,
            "os",
            "linux",
            "confirmed" if covered else "UNKNOWN",
            "slot",
            copied=False,
        )
        state.last_os = "linux"
        state.last_environment = "linux"
        changed.append("os")

    docker_off = bool(
        re.search(r"docker.{0,16}(不要|なし|無し|じゃなく|やめて|無しで)", requirement, re.I)
        or re.search(r"(不要|なし|無し|じゃなく).{0,8}docker", requirement, re.I)
    )
    if docker_off:
        old = state.facets.get("docker")
        if old and old.value != "absent":
            hist = old.to_dict()
            hist["evidence"] = "historical"
            state.history.append(hist)
        _set_facet(state, "docker", "absent", "confirmed", "user_constraint", copied=False)
        changed.append("docker")
    elif re.search(r"docker", requirement, re.I):
        covered = bool(rec) and (
            _env_key_covered(rec, "docker") or _env_key_covered(rec, "container")
        )
        _set_facet(
            state,
            "docker",
            "docker",
            "confirmed" if covered else "UNKNOWN",
            "slot",
        )
        changed.append("docker")

    cuda = _CUDA.search(requirement)
    if cuda:
        want = cuda.group(1)
        old = state.facets.get("cuda")
        if old and old.value != want:
            hist = old.to_dict()
            hist["evidence"] = "historical"
            state.history.append(hist)
        covered = bool(rec) and _cuda_covered(rec, want)
        _set_facet(
            state,
            "cuda",
            want,
            "confirmed" if covered else "UNKNOWN",
            "slot",
            copied=False,
        )
        state.last_cuda = want
        changed.append("cuda")
        # Do not reset python_version (or other unchanged Facets).

    if rec and rec.license_facts and "license" not in state.facets:
        if pointer.status == "BOUND" or state.last_research_id:
            _set_facet(state, "license", str(rec.license_facts[0]), "confirmed", "research_record")

    missing: list[str] = []
    reusable: list[str] = []
    for fid, slot in state.facets.items():
        if fid in changed and slot.evidence in {"UNKNOWN", "MISSING"}:
            missing.append(f"{fid}:{slot.value}")
        elif slot.evidence == "confirmed" and fid not in changed:
            reusable.append(fid)
        elif fid in changed and slot.evidence == "confirmed":
            reusable.append(fid)

    return {
        "pointer": pointer.to_dict(),
        "delta": delta.to_dict(),
        "changed": changed,
        "retained": sorted(state.facets.keys()),
        "retained_before": retained_before,
        "missing": missing,
        "reusable": reusable,
        "full_reresearch": False,
        "searches_estimate": len(missing),
        "copied_old_python_evidence": False,
        "facets": {k: v.to_dict() for k, v in state.facets.items()},
    }


def spec_from_session(state: DevelopmentSessionState, requirement: str, store: ResearchStore) -> dict[str, Any] | None:
    """Build a spec from bound candidate + current session Facets. No Core."""
    from ai_tool.experimental.development_assistance.spec_draft import build_spec_draft

    rec = next((r for r in store.records if r.research_id == state.last_research_id), None)
    if not rec or not rec.technology_candidates:
        return None
    cand = dict(rec.technology_candidates[0])
    env = dict(cand.get("environment") or {})
    py = state.facets.get("python_version")
    if py:
        env["python"] = f"Python {py.value}"
        cand["environment"] = env
    spec = build_spec_draft(requirement, cand).to_dict()
    spec["runtime"] = env.get("python") or spec.get("runtime")
    unknowns = list(spec.get("unknowns") or [])
    if py and py.evidence in {"UNKNOWN", "MISSING"}:
        unknowns.append(f"Python {py.value} compatibility is not official evidence")
        spec["copied_from_old_python"] = False
    spec["unknowns"] = unknowns
    spec["session_facets"] = {k: v.to_dict() for k, v in state.facets.items()}
    spec["provenance_note"] = "Draft from session ResearchRecord — not execution-verified"
    return spec
