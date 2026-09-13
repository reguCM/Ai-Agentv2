"""Requirement-driven Facet Discovery — experimental adapter, not a Reasoning Core.

Goal Abstraction answers: what does the user want to achieve?
Facet Discovery answers: what must be known to judge that goal?
It does not answer: executable / safe / compatible.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from ai_tool.experimental.development_assistance.research_record import ResearchRecord, ResearchStore
from ai_tool.experimental.development_assistance.research_reuse import extract_requirement_facets
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement

# Discovery-only concepts (not robot catalog ids, not verdicts).
CAPABILITY_CONCEPTS = (
    "llm_limitation",
    "external_evidence",
    "validation_capability",
    "observation",
    "decision_boundary",
    "human_review",
)
AMBIGUOUS_CONCEPTS = (
    "target",
    "capability",
    "difficulty",
    "external_knowledge_need",
    "environment",
    "existing_tool",
    "version",
    "evidence",
    "feasibility",
)

_DECISION_KEYS = frozenset(
    {
        "verdict",
        "feasible",
        "infeasible",
        "safe",
        "unsafe",
        "compatible",
        "executable",
        "decision",
        "approved",
        "build",
        "reject",
        "correct",
        "incorrect",
    }
)

_VERSION_RE = re.compile(r"\d+\.\d+(?:\.\d+)?")
_PYTHON_VER = re.compile(r"python\s*(3\.\d+(?:\.\d+)?)", re.I)
_CUDA_VER = re.compile(r"cuda\s*(12(?:\.\d+)?|11(?:\.\d+)?)", re.I)

# Cue table: goal-type → needed catalog facets. Pattern match, not inference.
_CUES: list[dict[str, Any]] = [
    {
        "id": "human_handoff",
        "pattern": re.compile(r"人間が|polyscope|再開|handoff|操作を再開", re.I),
        "needed": [
            "transport",
            "control_authority",
            "operational_mode",
            "operational_mode_source",
            "program_state",
            "safety_state",
            "human_handoff",
        ],
        "explicit": ["human_handoff", "control_authority"],
        "implicit": [
            "transport",
            "operational_mode",
            "operational_mode_source",
            "program_state",
            "safety_state",
        ],
        "research_needed": True,
    },
    {
        "id": "urscript_execution",
        "pattern": re.compile(r"urscript", re.I),
        "needed": [
            "urscript_api",
            "version",
            "ursim",
            "program_state",
            "execution_observation",
        ],
        "explicit": ["urscript_api"],
        "implicit": ["program_state", "execution_observation", "version", "ursim"],
        "research_needed": True,
    },
    {
        "id": "docker_environment",
        "pattern": re.compile(r"docker", re.I),
        "needed": [
            "docker",
            "storage",
        ],
        "explicit": ["docker"],
        "implicit": ["storage"],
        "concepts": ["container", "runtime", "os", "dependencies"],
        "research_needed": True,
    },
    {
        "id": "cycle_unknown",
        "pattern": re.compile(r"cycle|外部トリガ|n回|counted", re.I),
        "needed": [
            "cycle_controller",
            "safety_state",
            "operational_mode",
            "program_state",
            "execution_observation",
        ],
        "explicit": ["cycle_controller"],
        "implicit": ["safety_state", "operational_mode", "program_state", "execution_observation"],
        "research_needed": True,
        "unknown_facets": ["cycle_controller", "safety_state"],
    },
    {
        "id": "pytorch_env",
        "pattern": re.compile(r"pytorch", re.I),
        "needed": ["python_version", "cuda", "license"],
        "explicit": ["python_version"],
        "implicit": ["cuda", "license"],
        "research_needed": True,
    },
    {
        "id": "license_embed",
        "pattern": re.compile(r"ライセンス|license|組み込", re.I),
        "needed": ["license"],
        "concepts": ["distribution", "modification", "dependency", "source", "version"],
        "explicit": ["license"],
        "implicit": [],
        "research_needed": True,
    },
    {
        "id": "api_availability",
        "pattern": re.compile(r"このapi|apiが|apiを使える|apiがあると", re.I),
        "needed": ["version"],
        "concepts": ["api", "availability", "source", "currentness", "version"],
        "explicit": ["api"],
        "implicit": ["availability", "source", "currentness"],
        "research_needed": True,
    },
    {
        "id": "hardware_env",
        "pattern": re.compile(r"rtx|vram|3060|gpu", re.I),
        "needed": ["hardware", "vram"],
        "concepts": ["hardware", "vram", "os", "runtime", "performance"],
        "explicit": ["hardware"],
        "implicit": ["vram", "runtime"],
        "research_needed": True,
    },
    {
        "id": "os_windows",
        "pattern": re.compile(r"windows", re.I),
        "needed": [],
        "concepts": ["os", "environment"],
        "explicit": ["os"],
        "research_needed": True,
    },
    {
        "id": "capability_validation",
        "pattern": re.compile(r"llmだけでは|学習内容だけでは|検証tool|判断できない", re.I),
        "needed": [],
        "concepts": list(CAPABILITY_CONCEPTS),
        "explicit": ["llm_limitation", "validation_capability"],
        "implicit": ["external_evidence", "observation", "decision_boundary", "human_review"],
        "research_needed": True,
        "avoid_only": ["safety_state"],
    },
    {
        "id": "ambiguous_tda",
        "pattern": re.compile(r"難しそうなtoolを1つ|作れそうなところまで", re.I),
        "needed": [],
        "concepts": list(AMBIGUOUS_CONCEPTS),
        "explicit": ["external_knowledge_need", "feasibility"],
        "implicit": ["environment", "existing_tool", "evidence"],
        "research_needed": True,
        "cap_abstract": True,
    },
]


@dataclass
class FacetNeed:
    facet_id: str
    source: str  # explicit | implicit | version | environment | follow_up | negative | comparison
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FacetDiscoveryResult:
    requirement: str
    needed: list[FacetNeed] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    versions: list[str] = field(default_factory=list)
    python: str = ""
    cuda: str = ""
    comparison: bool = False
    target_comparison: bool = False
    follow_up: bool = False
    partial_only: bool = False
    research_needed: bool = False
    unresolved_references: list[str] = field(default_factory=list)
    clarifications: list[str] = field(default_factory=list)
    target_research_id: str = ""
    dependencies: list[dict[str, str]] = field(default_factory=list)
    granularity: str = "useful"  # too_concrete | useful | too_abstract

    def catalog_ids(self) -> list[str]:
        return [n.facet_id for n in self.needed if n.facet_id not in self.excluded]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["needed"] = [n.to_dict() if hasattr(n, "to_dict") else n for n in self.needed]
        d["catalog_ids"] = self.catalog_ids()
        return d


@dataclass
class FollowUpPlan:
    matched_research_id: str
    target: str
    requested_facets: list[str]
    requested_version: str
    reusable: list[str]
    version_sensitive: list[str]
    missing: list[str]
    full_reresearch: bool
    searches_estimate: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_goal_abstraction_slots(goals: dict[str, Any]) -> dict[str, Any]:
    """N-1: L0–L3 are prose strings; they do not slot target/version/constraints."""
    joined = " ".join(str(goals.get(k) or "") for k in ("level_0", "level_1", "level_2", "level_3"))
    return {
        "holds_target_slot": False,
        "holds_operation_slot": False,
        "holds_condition_slot": False,
        "holds_version_slot": False,
        "holds_environment_slot": False,
        "holds_capability_slot": False,
        "holds_constraint_slot": False,
        "holds_success_criteria_slot": False,
        "holds_uncertainty_slot": False,
        "holds_comparison_slot": False,
        "holds_follow_up_slot": False,
        "what_it_holds": "L0–L3 canned goal prose + derived capability names",
        "prose": joined[:240],
    }


def _add(needed: list[FacetNeed], fid: str, source: str, reason: str) -> None:
    if any(n.facet_id == fid for n in needed):
        return
    needed.append(FacetNeed(facet_id=fid, source=source, reason=reason))


def _negative_exclusions(requirement: str) -> list[str]:
    excluded: list[str] = []
    if re.search(r"docker.{0,12}(不要|じゃなくて)|docker環境については今回は不要", requirement, re.I):
        excluded.extend(["docker", "wsl2", "storage", "cpu_virtualization", "ram", "network_ports"])
    if re.search(r"じゃなくてvm", requirement, re.I):
        excluded.extend(["docker", "wsl2"])
    return excluded


def resolve_research_reference(
    requirement: str,
    store: ResearchStore,
    *,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve conversational pointers against ResearchStore. Do not guess."""
    unresolved: list[str] = []
    clarifications: list[str] = []
    matched: ResearchRecord | None = None

    if re.search(r"そのpython版|その python", requirement, re.I):
        ctx_py = (session or {}).get("last_python") or ""
        if not ctx_py:
            unresolved.append("そのPython版")
            clarifications.append("Which Python version / which prior research?")

    if re.search(r"3\.12の方だけ", requirement):
        if session and session.get("last_python"):
            pass
        elif not _PYTHON_VER.search(requirement) and not any(
            "3.12" in (r.environment_facts or {}).get("python", "") for r in store.records
        ):
            clarifications.append("3.12の方だけ: bind to prior Python comparison if present")

    if re.match(r"A[をに]", requirement.strip()):
        hits = [
            r
            for r in store.records
            if r.research_id.upper() in {"RR-A", "A"}
            or (r.environment_facts or {}).get("label", "").upper() == "A"
        ]
        if len(hits) == 1:
            matched = hits[0]
        elif not hits:
            unresolved.append("A")
            clarifications.append("Cannot bind 'A' to a ResearchRecord without guessing")
        elif len(hits) > 1:
            unresolved.append("A")
            clarifications.append("Multiple records match A")

    m_a = re.search(
        r"さっき調べた\s*([A-Za-z])|さっきの([A-Za-z])\b|前に調べた\s*([A-Za-z])",
        requirement,
    )
    if m_a:
        letter = next(g for g in m_a.groups() if g)
        hits = [
            r
            for r in store.records
            if r.research_id.upper().endswith(f"-{letter.upper()}")
            or r.research_id.upper() == f"RR-{letter.upper()}"
            or r.topic.strip().upper().startswith(letter.upper() + " ")
            or (r.environment_facts or {}).get("label", "").upper() == letter.upper()
        ]
        if len(hits) == 1:
            matched = hits[0]
        elif len(hits) > 1:
            clarifications.append(f"Multiple records match '{letter}'")
            unresolved.append(letter)
        else:
            unresolved.append(letter)
            clarifications.append(f"Cannot bind '{letter}' to a ResearchRecord without guessing")

    if re.search(r"前に調べたursim|調べたursim", requirement, re.I):
        hits = store.find_by_topic_token("ursim") or store.find_by_technology("URSim")
        if not hits:
            hits = [r for r in store.records if "ursim" in r.requirement.lower() or "ursim" in r.topic.lower()]
        if len(hits) == 1:
            matched = matched or hits[0]
        elif len(hits) > 1:
            clarifications.append("Multiple URSim records")
            unresolved.append("前に調べたURSim")
        elif not hits:
            unresolved.append("前に調べたURSim")
            clarifications.append("No URSim ResearchRecord in store")

    if re.search(r"その環境なら", requirement):
        if not (session or {}).get("last_environment"):
            unresolved.append("その環境")
            clarifications.append("Which environment snapshot?")

    if re.search(r"前のやつ", requirement):
        if not (session or {}).get("last_research_id"):
            unresolved.append("前のやつ")
            clarifications.append("Cannot bind 前のやつ without session target")

    if re.search(r"さっきの条件を変えたら", requirement):
        unresolved.append("さっきの条件")
        clarifications.append("Which prior condition should change?")

    if re.search(r"その方法じゃなく|別の方法なら", requirement):
        unresolved.append("別の方法")
        clarifications.append("Name the alternative method; do not infer")

    if re.search(r"Aの方だけもう少し", requirement):
        hits = [
            r
            for r in store.records
            if r.research_id.upper() in {"RR-A", "A"}
            or (r.environment_facts or {}).get("label", "").upper() == "A"
        ]
        if len(hits) == 1:
            matched = hits[0]
        elif not hits:
            unresolved.append("A")
            clarifications.append("Cannot bind A")

    if re.search(r"dockerじゃなくてvm", requirement, re.I):
        vm_hits = [r for r in store.records if "vm" in r.topic.lower() or "vm" in r.requirement.lower()]
        if not vm_hits:
            unresolved.append("VMの方")
            clarifications.append("No VM research in store; not inferred from Docker")

    return {
        "matched": matched,
        "unresolved": unresolved,
        "clarifications": clarifications,
    }


def _python_covered(rec: ResearchRecord, want: str) -> bool:
    env = str((rec.environment_facts or {}).get("python") or "")
    if want and want in env.replace("Python ", ""):
        return True
    for vf in rec.version_facts or []:
        if want in str(vf.get("python") or "").replace("Python ", ""):
            return True
        if str(vf.get("technology") or "").lower() == "python" and want in str(vf.get("version") or ""):
            return True
    return False


def _cuda_covered(rec: ResearchRecord, want: str) -> bool:
    env = str((rec.environment_facts or {}).get("cuda") or "")
    if want and want in env.replace("CUDA ", "").replace("cuda ", ""):
        return True
    for vf in rec.version_facts or []:
        if want in str(vf.get("cuda") or ""):
            return True
        if str(vf.get("technology") or "").lower() == "cuda" and want in str(vf.get("version") or ""):
            return True
    return False


def _env_key_covered(rec: ResearchRecord, key: str, want: str = "") -> bool:
    val = str((rec.environment_facts or {}).get(key) or "")
    if not val:
        return False
    if not want:
        return True
    return want.lower() in val.lower()


def plan_follow_up(
    requirement: str,
    store: ResearchStore,
    *,
    session: dict[str, Any] | None = None,
) -> FollowUpPlan | None:
    """Partial reuse plan. 'もう少し調べて' is not full re-research."""
    follow = bool(
        re.search(
            r"さっき|もう少し|場合だけ|再評価|詳しく調べ|確認して|さらに|"
            r"前に調べた|必要な変更|何が変わる|使いたい|動かしたい|組み込|向いている|"
            r"その場合|どうなる|なら？|比較して",
            requirement,
        )
    )
    if not follow:
        return None
    ref = resolve_research_reference(requirement, store, session=session)
    rec = ref.get("matched")
    if rec is None and store.records:
        facets = extract_requirement_facets(requirement)
        if facets.technologies:
            named = []
            for r in store.records:
                names = [n.lower() for n in r.technology_names]
                if any(t.lower() in n or n in t.lower() for t in facets.technologies for n in names):
                    named.append(r)
            if len(named) == 1:
                rec = named[0]
        if rec is None and store.records and follow:
            sid = (session or {}).get("last_research_id")
            if sid:
                rec = next((r for r in store.records if r.research_id == sid), None)
            if rec is None and len(store.records) == 1:
                rec = store.records[0]
    if rec is None:
        return FollowUpPlan(
            matched_research_id="",
            target="",
            requested_facets=[],
            requested_version="",
            reusable=[],
            version_sensitive=[],
            missing=["target_research"],
            full_reresearch=False,
            searches_estimate=0,
        )

    py = _PYTHON_VER.search(requirement)
    cuda = _CUDA_VER.search(requirement)
    requested: list[str] = []
    version = ""
    reusable: list[str] = []
    version_sensitive: list[str] = []
    missing: list[str] = []
    env = rec.environment_facts or {}

    if py:
        requested.append("python_version")
        version = py.group(1)
        version_sensitive.append("python_version")
        if _python_covered(rec, version):
            reusable.append("python_version")
        else:
            missing.append(f"python {version} evidence")
    elif env.get("python"):
        reusable.append("python_version")

    if cuda:
        requested.append("cuda")
        want_cuda = cuda.group(1)
        if not version:
            version = want_cuda
        version_sensitive.append("cuda")
        if _cuda_covered(rec, want_cuda):
            reusable.append("cuda")
        else:
            missing.append(f"cuda {want_cuda} evidence")
    elif env.get("cuda"):
        reusable.append("cuda")

    if re.search(r"docker", requirement, re.I):
        requested.append("docker")
        if _env_key_covered(rec, "docker") or _env_key_covered(rec, "container"):
            reusable.append("docker")
        else:
            missing.append("docker environment evidence")

    if re.search(r"windows", requirement, re.I):
        requested.append("os")
        if _env_key_covered(rec, "os", "windows"):
            reusable.append("os")
        else:
            missing.append("os Windows evidence")

    if re.search(r"rtx|3060", requirement, re.I):
        requested.append("hardware")
        if _env_key_covered(rec, "gpu", "3060") or _env_key_covered(rec, "hardware", "3060"):
            reusable.append("hardware")
        else:
            missing.append("hardware RTX 3060 evidence")
        if re.search(r"12\s*gb|12gb", requirement, re.I):
            requested.append("vram")
            if _env_key_covered(rec, "vram", "12"):
                reusable.append("vram")
            else:
                missing.append("vram 12GB evidence")

    if re.search(r"ライセンス|license|組み込", requirement, re.I):
        requested.append("license")
        if rec.license_facts:
            reusable.append("license")
        else:
            missing.append("license evidence")
    elif rec.license_facts:
        reusable.append("license")

    if rec.technology_names:
        reusable.extend([n for n in rec.technology_names if n])

    reusable = list(dict.fromkeys(reusable))
    full = False
    searches = len(missing)
    return FollowUpPlan(
        matched_research_id=rec.research_id,
        target=rec.topic or (rec.technology_names[0] if rec.technology_names else rec.research_id),
        requested_facets=requested,
        requested_version=version,
        reusable=reusable,
        version_sensitive=list(dict.fromkeys(version_sensitive)),
        missing=missing,
        full_reresearch=full,
        searches_estimate=searches,
    )


def discover_facets(
    requirement: str,
    store: ResearchStore | None = None,
    *,
    session: dict[str, Any] | None = None,
) -> FacetDiscoveryResult:
    """List what must be known. Never sets a truth/safety verdict."""
    store = store or ResearchStore()
    needed: list[FacetNeed] = []
    concepts: list[str] = []
    research_needed = False
    unknown_facets: list[str] = []
    cap_abstract = False

    for cue in _CUES:
        if not cue["pattern"].search(requirement):
            continue
        research_needed = research_needed or bool(cue.get("research_needed"))
        cap_abstract = cap_abstract or bool(cue.get("cap_abstract"))
        for fid in cue.get("needed") or []:
            src = "explicit" if fid in (cue.get("explicit") or []) else "implicit"
            _add(needed, fid, src, f"cue:{cue['id']}")
        for c in cue.get("concepts") or []:
            if c not in concepts:
                concepts.append(c)
        unknown_facets.extend(cue.get("unknown_facets") or [])

    versions = _VERSION_RE.findall(requirement)
    comparison = len(set(versions)) >= 2
    if comparison:
        _add(needed, "version", "comparison", "two versions in requirement")
        _add(needed, "conflict", "comparison", "version pair needs conflict envelope")
        concepts.extend([c for c in ("feature", "compatibility", "evidence", "conflict") if c not in concepts])
        research_needed = True

    py = _PYTHON_VER.search(requirement)
    cuda = _CUDA_VER.search(requirement)
    python = f"Python {py.group(1)}" if py else ""
    cuda_s = f"CUDA {cuda.group(1)}" if cuda else ""
    if py:
        _add(needed, "python_version", "version", f"python {py.group(1)}")
        research_needed = True
    if cuda:
        _add(needed, "cuda", "environment", f"cuda {cuda.group(1)}")
        research_needed = True

    has_ur = bool(re.search(r"ursim|urscript|polyscope", requirement, re.I))
    if any(n.facet_id == "docker" for n in needed) and has_ur:
        for fid in ("ursim", "version", "wsl2", "cpu_virtualization", "ram", "network_ports"):
            _add(needed, fid, "implicit", "docker+ur companion")
    if any(n.facet_id == "docker" for n in needed) and re.search(r"rtx|cuda|gpu", requirement, re.I):
        _add(needed, "gpu_passthrough", "implicit", "docker+gpu")
        if "gpu_passthrough" not in concepts:
            concepts.append("gpu_passthrough")

    target_comparison = bool(re.search(r"AとB|A と B", requirement) and "比較" in requirement)
    if target_comparison or "比較" in requirement:
        if target_comparison or "比較" in requirement:
            for c in (
                "target",
                "environment",
                "version",
                "dependency",
                "license",
                "performance",
                "currentness",
                "unknown",
                "conflict",
            ):
                if c not in concepts:
                    concepts.append(c)
            research_needed = True

    if py:
        for c in ("target", "environment", "compatibility"):
            if c not in concepts:
                concepts.append(c)

    if re.search(r"windows", requirement, re.I):
        _add(needed, "os", "environment", "windows")

    excluded = _negative_exclusions(requirement)
    follow_up = bool(
        re.search(
            r"さっき|もう少し|場合だけ|再評価|詳しく調べ|確認して|さらに|"
            r"前に調べた|必要な変更|何が変わる|使いたい|動かしたい|組み込|向いている|"
            r"その場合|どうなる|なら？|比較して",
            requirement,
        )
    )
    partial_only = bool(re.search(r"もう少し|場合だけ|だけ調べ|だけ再評価|だけ確認|必要な変更だけ", requirement))

    ref = resolve_research_reference(requirement, store, session=session)
    target_id = ref["matched"].research_id if ref.get("matched") else ""

    deps: list[dict[str, str]] = []
    if py or any(n.facet_id == "python_version" for n in needed):
        if any(n.facet_id == "cuda" for n in needed) or "pytorch" in requirement.lower():
            deps.append({"from": "python_version", "to": "pytorch_compatibility", "via": "metadata"})
            deps.append({"from": "python_version", "to": "cuda_compatibility", "via": "metadata"})
            deps.append({"from": "cuda_compatibility", "to": "environment_feasibility", "via": "metadata"})

    ids = [n.facet_id for n in needed if n.facet_id not in excluded]
    granularity = "useful"
    if cap_abstract and len(concepts) <= 2:
        granularity = "too_abstract"
    if len(ids) >= 18:
        granularity = "too_concrete"
    if any(c["id"] == "capability_validation" and c["pattern"].search(requirement) for c in _CUES):
        if ids == ["safety_state"] or (not concepts and "safety_state" in ids):
            granularity = "too_abstract"

    if unknown_facets:
        research_needed = True

    existing_gate = assess_research_requirement(requirement)
    if research_needed and existing_gate.decision == "RESEARCH_NOT_REQUIRED":
        # Discovery disagrees with Gate; still not a verdict — only a research-need signal.
        pass

    return FacetDiscoveryResult(
        requirement=requirement,
        needed=needed,
        excluded=excluded,
        concepts=concepts,
        versions=list(dict.fromkeys(versions)),
        python=python,
        cuda=cuda_s,
        comparison=comparison,
        target_comparison=target_comparison,
        follow_up=follow_up,
        partial_only=partial_only,
        research_needed=research_needed,
        unresolved_references=list(ref.get("unresolved") or []),
        clarifications=list(ref.get("clarifications") or []),
        target_research_id=target_id,
        dependencies=deps,
        granularity=granularity,
    )


def asserts_not_a_decision(result: FacetDiscoveryResult) -> bool:
    keys = set(result.to_dict().keys())
    return keys.isdisjoint(_DECISION_KEYS)


def facet_hierarchy_view(present_ids: list[str]) -> dict[str, Any]:
    """Nested dict — not a Graph Core. Prune to ids/concepts present."""
    tree = {
        "target": {
            "version": {},
            "environment": {
                "os": {},
                "hardware": {},
                "runtime": {},
                "container": {},
            },
            "dependency": {},
            "api": {},
            "license": {},
            "performance": {},
        }
    }
    present = set(present_ids)
    env_map = {
        "os": "os",
        "hardware": "hardware",
        "vram": "hardware",
        "runtime": "runtime",
        "docker": "container",
        "gpu_passthrough": "container",
        "storage": "container",
    }
    shown_env = {env_map[i] for i in present if i in env_map}
    if shown_env:
        tree["target"]["environment"] = {k: {} for k in shown_env}
    else:
        tree["target"].pop("environment", None)
    for leaf in ("version", "dependency", "api", "license", "performance"):
        aliases = {
            "version": {"version", "python_version"},
            "dependency": {"cuda", "dependencies"},
            "api": {"api_availability", "version"},
            "license": {"license", "distribution", "modification"},
            "performance": {"performance", "vram"},
        }
        if not (present & aliases[leaf]):
            tree["target"].pop(leaf, None)
    return tree


def existing_mode_a_ids(requirement: str) -> list[str]:
    """What existing RequirementFacets + Goal Abstraction actually emit as facet ids."""
    rf = extract_requirement_facets(requirement)
    selected: list[str] = []
    if rf.python:
        selected.append("python_version")
    if rf.cuda:
        selected.append("cuda")
    if rf.license_preference:
        selected.append("license")
    for t in rf.technologies:
        tl = t.lower()
        if tl == "urscript":
            selected.append("urscript_api")
        elif tl == "pytorch":
            selected.append("python_version")
        elif tl in {"json", "pandas", "polars"}:
            selected.append("documentation_version")
    return list(dict.fromkeys(selected))
