"""Facet Discovery coverage adapter — paraphrase / slots / research overlay.

Not a Reasoning Core. Does not emit safe / feasible / correct / build.
Required vs candidate vs unknown is a measurement envelope, not a new Core.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ai_tool.experimental.development_assistance.discovery_skip_policy import _is_skip
from ai_tool.experimental.development_assistance.facet_discovery import (
    _DECISION_KEYS,
    discover_facets,
    plan_follow_up,
    resolve_research_reference,
)
from ai_tool.experimental.development_assistance.goal_abstraction import abstract_goals
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import extract_requirement_facets

_IMPLICIT_CANDIDATE = frozenset(
    {
        "control_authority",
        "human_handoff",
        "operational_mode",
        "operational_mode_source",
        "cycle_controller",
        "safety_state",
        "program_state",
        "transport",
    }
)

_PYTHON_VER = re.compile(r"python\s*(3\.\d+(?:\.\d+)?)", re.I)
_CUDA_VER = re.compile(r"cuda\s*(12(?:\.\d+)?|11(?:\.\d+)?)", re.I)

# Alias families: same research-need, different wording. Not inference.
_ALIAS_FAMILIES: list[dict[str, Any]] = [
    {
        "id": "research_need",
        "pattern": re.compile(
            r"調べて|確認して|検証して|使えるか見て|実際に試|動く？|いける？|大丈夫？|"
            r"試せるか|使えるか確認",
            re.I,
        ),
        "required_concepts": ["external_evidence"],
    },
    {
        "id": "api",
        "pattern": re.compile(
            r"\bapi\b|使えるapi|apiを調べ|最新.+api|このapi|apiが|apiを使える|apiがあると",
            re.I,
        ),
        "required": ["version"],
        "required_concepts": ["api", "availability", "source", "currentness"],
    },
    {
        "id": "environment_check",
        "pattern": re.compile(r"この環境|環境で|試せる|動かせ|これで動く|本番で|使えるか", re.I),
        "required_concepts": ["environment"],
    },
    {
        "id": "compare",
        "pattern": re.compile(r"どちら|どっち|比較|の方がいい|どっちを使", re.I),
        "required_concepts": [
            "target",
            "environment",
            "version",
            "dependency",
            "license",
            "performance",
            "currentness",
            "unknown",
            "conflict",
        ],
    },
    {
        "id": "version_other",
        "pattern": re.compile(r"別バージョン|別のversion|別version", re.I),
        "required": ["version", "conflict"],
    },
    {
        "id": "license",
        "pattern": re.compile(r"ライセンス|license|組み込", re.I),
        "required": ["license"],
    },
    {
        "id": "human_ops",
        "pattern": re.compile(r"人間が|途中で操作|止められる|操作できる|一緒に使える", re.I),
        "candidate_if_store": [
            "control_authority",
            "human_handoff",
            "operational_mode",
            "program_state",
        ],
        "unknown_if_no_store": ["control_authority"],
    },
    {
        "id": "repeat",
        "pattern": re.compile(r"繰り返|何回も|n回", re.I),
        "candidate_if_store": ["cycle_controller", "execution_observation"],
        "unknown_if_no_store": ["cycle_controller"],
    },
]


@dataclass
class CoverageItem:
    facet_id: str
    status: FacetStatus
    reason: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SlotView:
    purpose: str
    target: str
    python: str
    cuda: str
    os: str
    hardware: str
    changed: list[str]
    confirmation: str
    comparison_targets: list[str]
    follow_up: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CoverageResult:
    mode: CoverageMode
    requirement: str
    slots: SlotView
    items: list[CoverageItem] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    clarifications: list[str] = field(default_factory=list)
    keep_facets: list[str] = field(default_factory=list)
    changed_facets: list[str] = field(default_factory=list)
    comparison_axes: list[str] = field(default_factory=list)
    skipped: bool = False
    research_needed: bool = False
    searches_estimate: int = 0
    target_research_id: str = ""

    def required_ids(self) -> list[str]:
        return [i.facet_id for i in self.items if i.status == "required"]

    def candidate_ids(self) -> list[str]:
        return [i.facet_id for i in self.items if i.status == "candidate"]

    def unknown_ids(self) -> list[str]:
        return [i.facet_id for i in self.items if i.status == "unknown"]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["required"] = self.required_ids()
        d["candidates"] = self.candidate_ids()
        d["unknown"] = self.unknown_ids()
        return d


def asserts_coverage_not_a_decision(result: CoverageResult) -> bool:
    blob = str(result.to_dict()).lower()
    if any(k in result.to_dict() for k in _DECISION_KEYS):
        return False
    forbidden_phrases = (
        "infeasible",
        "production ready",
        "build now",
        "safe to use",
        "unsafe",
        "incorrect",
    )
    return not any(p in blob for p in forbidden_phrases)


def extract_slots(requirement: str, session: dict[str, Any] | None = None) -> SlotView:
    """Surface purpose / target / conditions. Does not judge them."""
    session = session or {}
    py = _PYTHON_VER.search(requirement)
    cuda = _CUDA_VER.search(requirement)
    python = py.group(1) if py else ""
    cuda_s = cuda.group(1) if cuda else ""
    os = ""
    if re.search(r"windows", requirement, re.I):
        os = "windows"
    elif re.search(r"linux", requirement, re.I):
        os = "linux"
    hardware = ""
    if re.search(r"rtx|3060|gpu", requirement, re.I):
        hardware = "rtx_3060" if re.search(r"3060", requirement) else "gpu"
    target = ""
    if re.search(r"pytorch", requirement, re.I):
        target = "PyTorch"
    elif re.search(r"ursim|urscript|polyscope", requirement, re.I):
        target = "UR"
    elif re.search(r"前に調べたA|さっきのA|Aについて", requirement):
        target = "A"
    elif re.search(r"AとB", requirement):
        target = "A,B"
    elif re.match(r"A[をに]", requirement.strip()):
        target = "A"
    comparison: list[str] = []
    if re.search(r"AとB|A と B", requirement):
        comparison = ["A", "B"]
    follow = bool(
        re.search(r"さっき|もう少し|場合だけ|なら？|でも？|前に調べた|その環境|前のやつ|前回", requirement)
    )
    purpose = "knowledge"
    if re.search(r"コードを書いて|関数を作って", requirement):
        purpose = "codegen"
    elif comparison or re.search(r"どちら|比較", requirement):
        purpose = "compare"
    elif re.search(r"できそう|toolにできる|作れそう", requirement, re.I):
        purpose = "feasibility_check"
    elif follow:
        purpose = "follow_up"
    elif re.search(r"調べ|確認|検証|試せ|動かせ|動く", requirement):
        purpose = "research"
    confirmation = ""
    if re.search(r"動く|使える|大丈夫|試せる|確認", requirement):
        confirmation = "availability"
    changed: list[str] = []
    if python and python != session.get("last_python"):
        changed.append("python_version")
    if cuda_s and cuda_s != session.get("last_cuda"):
        changed.append("cuda")
    if os and os != session.get("last_os"):
        changed.append("os")
    if hardware and hardware != session.get("last_hardware"):
        changed.append("hardware")
    return SlotView(
        purpose=purpose,
        target=target,
        python=python,
        cuda=cuda_s,
        os=os,
        hardware=hardware,
        changed=changed,
        confirmation=confirmation,
        comparison_targets=comparison,
        follow_up=follow,
    )


def _add(items: list[CoverageItem], fid: str, status: FacetStatus, reason: str, source: str) -> None:
    existing = next((i for i in items if i.facet_id == fid), None)
    rank = {"unknown": 0, "candidate": 1, "required": 2}
    if existing:
        if rank[status] > rank[existing.status]:
            existing.status = status
            existing.reason = reason
            existing.source = source
        return
    items.append(CoverageItem(fid, status, reason, source))


def _store_facet_ids(store: ResearchStore) -> set[str]:
    ids: set[str] = set()
    for rec in store.records:
        for f in rec.facet_records or []:
            fid = str(f.get("facet_id") or "")
            if fid:
                ids.add(fid)
    return ids


def discover_coverage(
    requirement: str,
    store: ResearchStore | None = None,
    *,
    mode: CoverageMode = "GCR",
    session: dict[str, Any] | None = None,
) -> CoverageResult:
    """List required / candidate / unknown facets. Never a verdict."""
    store = store or ResearchStore()
    session = session or {}
    slots = extract_slots(requirement, session)
    if _is_skip(requirement) or slots.purpose == "codegen":
        return CoverageResult(
            mode=mode,
            requirement=requirement,
            slots=slots,
            skipped=True,
            research_needed=False,
        )

    items: list[CoverageItem] = []
    unresolved: list[str] = []
    clarifications: list[str] = []
    keep: list[str] = []
    axes: list[str] = []

    base = discover_facets(requirement, store, session=session)
    if mode == "K":
        for n in base.needed:
            _add(items, n.facet_id, "required", n.reason, "keyword")
        for c in base.concepts:
            _add(items, c, "required", "cue concept", "keyword")
        return CoverageResult(
            mode="K",
            requirement=requirement,
            slots=slots,
            items=items,
            unresolved=list(base.unresolved_references),
            clarifications=list(base.clarifications),
            changed_facets=list(slots.changed),
            research_needed=base.research_needed,
            searches_estimate=len(slots.changed) or (1 if base.research_needed else 0),
            target_research_id=base.target_research_id,
        )

    for fam in _ALIAS_FAMILIES:
        if not fam["pattern"].search(requirement):
            continue
        for fid in fam.get("required") or []:
            _add(items, fid, "required", f"alias:{fam['id']}", "alias")
        for c in fam.get("required_concepts") or []:
            _add(items, c, "required", f"alias-concept:{fam['id']}", "alias")
        store_ids = _store_facet_ids(store)
        if mode in {"GC", "GCR"}:
            cand = set(fam.get("candidate_if_store") or [])
            hit = store_ids & cand
            if hit:
                for fid in fam.get("candidate_if_store") or []:
                    if fid in store_ids:
                        _add(items, fid, "candidate", f"store-candidate:{fam['id']}", "research")
            else:
                for fid in fam.get("unknown_if_no_store") or []:
                    _add(items, fid, "unknown", f"no-store:{fam['id']}", "alias")

    for n in base.needed:
        if mode in {"GC", "GCR"} and n.facet_id in _IMPLICIT_CANDIDATE:
            _add(items, n.facet_id, "candidate", n.reason + " (implicit, not asserted)", "keyword")
        else:
            _add(items, n.facet_id, "required", n.reason, "keyword")
    if mode == "KA":
        for c in base.concepts:
            _add(items, c, "required", "cue concept", "keyword")

    if mode in {"GC", "GCR"}:
        goals = abstract_goals(requirement)
        rf = extract_requirement_facets(requirement)
        if slots.python or rf.python:
            _add(items, "python_version", "required", "slot python", "slot")
        if slots.cuda or rf.cuda:
            _add(items, "cuda", "required", "slot cuda", "slot")
        if slots.os:
            _add(items, "os", "required", "slot os", "slot")
        if slots.hardware:
            _add(items, "hardware", "required", "slot hardware", "slot")
            if re.search(r"12\s*gb|12gb", requirement, re.I):
                _add(items, "vram", "required", "slot vram", "slot")
        versions = re.findall(r"\d+\.\d+(?:\.\d+)?", requirement)
        if versions and not slots.python:
            _add(items, "version", "required", "slot product version", "slot")
            if len(set(versions)) >= 2:
                _add(items, "conflict", "required", "two versions named", "slot")
        if slots.purpose == "compare":
            axes = ["target", "environment", "version", "license", "conflict"]
            for ax in axes:
                _add(items, ax, "required", "comparison axis", "slot")
        if slots.purpose == "feasibility_check":
            _add(items, "environment", "required", "feasibility needs evidence, not a verdict", "slot")
            _add(items, "evidence", "required", "feasibility check lists evidence need", "slot")
        if slots.confirmation == "availability" and slots.purpose in {
            "research",
            "follow_up",
            "feasibility_check",
        }:
            _add(items, "environment", "required", "availability confirmation", "slot")
        if goals.level_3_justified and slots.purpose == "research":
            _add(items, "external_evidence", "required", "goal research need", "slot")
        if re.search(r"その環境なら", requirement):
            if not session.get("last_environment"):
                unresolved.append("その環境")
                clarifications.append("Which environment snapshot?")
            else:
                _add(items, "environment", "required", "bound prior environment", "slot")
        elif re.search(r"この環境", requirement) and not session.get("last_environment"):
            _add(items, "environment", "required", "environment mentioned, specifics unknown", "slot")
            _add(items, "os", "unknown", "os not named", "slot")
            _add(items, "docker", "unknown", "container not named", "slot")
            _add(items, "hardware", "unknown", "gpu not named", "slot")
        if re.search(r"前と同じ条件で別の方法|別の方法は", requirement):
            unresolved.append("別の方法")
            clarifications.append("Name the alternative method; do not infer")
        if re.search(r"前回の調査結果を使って、ここだけ|ここだけ確認", requirement):
            _add(items, "changed_condition", "required", "partial re-check", "slot")

    ref = resolve_research_reference(requirement, store, session=session)
    unresolved.extend(list(ref.get("unresolved") or []))
    clarifications.extend(list(ref.get("clarifications") or []))
    matched = ref.get("matched")
    target_id = getattr(matched, "research_id", "") or ""

    plan = plan_follow_up(requirement, store, session=session)
    searches = 0
    if plan:
        target_id = target_id or plan.matched_research_id
        keep = list(plan.reusable)
        searches = plan.searches_estimate
        if mode == "GCR":
            for fid in plan.requested_facets:
                _add(items, fid, "required", "follow-up changed facet", "research")
            for fid in plan.reusable:
                if fid not in plan.requested_facets:
                    _add(items, fid, "candidate", "kept from prior research", "research")

    if mode == "GCR" and matched:
        store_ids = _store_facet_ids(store)
        env = matched.environment_facts or {}
        if env.get("python") and "python_version" not in slots.changed:
            _add(items, "python_version", "candidate", "prior env python", "research")
        if env.get("cuda") and "cuda" not in slots.changed:
            _add(items, "cuda", "candidate", "prior env cuda", "research")
        if matched.license_facts and not re.search(r"ライセンス|license|組み込", requirement, re.I):
            _add(items, "license", "candidate", "prior license present", "research")
        if "docker" in store_ids and not re.search(r"docker", requirement, re.I):
            _add(items, "docker", "unknown", "docker not requested; not assumed", "research")

    required = [i.facet_id for i in items if i.status == "required"]
    research_needed = bool(
        required or slots.purpose in {"research", "compare", "follow_up", "feasibility_check"}
    )
    if not searches:
        searches = len(slots.changed) if slots.changed else (0 if keep else (1 if research_needed else 0))

    return CoverageResult(
        mode=mode,
        requirement=requirement,
        slots=slots,
        items=items,
        unresolved=list(dict.fromkeys(unresolved)),
        clarifications=list(dict.fromkeys(clarifications)),
        keep_facets=keep,
        changed_facets=list(slots.changed),
        comparison_axes=axes,
        research_needed=research_needed,
        searches_estimate=searches,
        target_research_id=target_id,
    )
