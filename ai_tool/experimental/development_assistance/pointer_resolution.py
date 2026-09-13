"""Conversational pointer resolution — Experimental adapter, not a Graph.

Binds only when session already has an id / environment / label.
Does not guess a technology. Unresolvable pointers stay UNRESOLVED.
Not wired into standard_workflow defaults.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from ai_tool.experimental.development_assistance.research_record import ResearchStore

PointerStatus = Literal["BOUND", "UNRESOLVED", "NOT_A_POINTER"]


@dataclass
class PointerResolution:
    pointer: str
    status: PointerStatus
    bound_research_id: str
    bound_label: str
    guessed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["clarification_required"] = self.status == "UNRESOLVED"
        return payload


_TECH_A = re.compile(
    r"その技術A|前の技術A|前に調べた技術A|前に調べたA|技術Aについて|そのAを|そのAに|そのAの|ある技術A",
)
_WIN_PY = re.compile(
    r"windows(?:環境)?で\s*python(?:\s*|は|を)(3\.\d+)|"
    r"python(?:\s*|は|を)(3\.\d+).{0,12}windows",
    re.I,
)
_PREV = re.compile(r"前のやつ|前回のやつ|前の結果")
_ENV = re.compile(r"その環境")
_THAT_TOOL = re.compile(r"そのTool|作ったTool|作成したTool")


def _python_of(rec) -> str:
    env = rec.environment_facts or {}
    m = re.search(r"3\.\d+", str(env.get("python") or ""))
    if m:
        return m.group(0)
    for vf in rec.version_facts or []:
        if str(vf.get("technology") or "").lower() == "python":
            mm = re.search(r"3\.\d+", str(vf.get("version") or ""))
            if mm:
                return mm.group(0)
    return ""


def _os_of(rec) -> str:
    return str((rec.environment_facts or {}).get("os") or "").lower()


def classify_pointer(
    requirement: str,
    *,
    store: ResearchStore | None = None,
    session: dict[str, Any] | None = None,
) -> PointerResolution:
    """Resolve one follow-up pointer. Never invent a ResearchRecord."""
    session = session or {}
    store = store or ResearchStore()
    rid = str(session.get("last_research_id") or "")
    rec = next((r for r in store.records if r.research_id == rid), None) if rid else None
    label = str(
        session.get("bound_label")
        or ((rec.environment_facts or {}).get("label") if rec is not None else "")
        or ""
    )

    win_py = _WIN_PY.search(requirement)
    if win_py:
        py = next((g for g in win_py.groups() if g), "")
        hits = [
            r
            for r in store.records
            if _os_of(r) == "windows" and _python_of(r) == py
        ]
        if len(hits) == 1:
            return PointerResolution(
                pointer="WindowsでPythonの方",
                status="BOUND",
                bound_research_id=hits[0].research_id,
                bound_label=str((hits[0].environment_facts or {}).get("label") or ""),
                guessed=False,
                reason="unique Windows + Python version match",
            )
        return PointerResolution(
            pointer="WindowsでPythonの方",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="0 or 2+ records match Windows + Python; do not guess",
        )

    if re.search(r"windowsの方", requirement, re.I) and not re.search(r"python", requirement, re.I):
        hits = [r for r in store.records if _os_of(r) == "windows"]
        if len(hits) == 1:
            return PointerResolution(
                pointer="Windowsの方",
                status="BOUND",
                bound_research_id=hits[0].research_id,
                bound_label=str((hits[0].environment_facts or {}).get("label") or ""),
                guessed=False,
                reason="unique Windows match",
            )
        return PointerResolution(
            pointer="Windowsの方",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="Windows matches several records; do not guess",
        )

    if _TECH_A.search(requirement):
        if rec is not None and (label.upper() in {"", "A"} or label.upper() == "A"):
            env_label = str((rec.environment_facts or {}).get("label") or "").upper()
            if env_label == "A" or rec.research_id.upper() in {"RR-A", "A"}:
                return PointerResolution(
                    pointer="その技術A",
                    status="BOUND",
                    bound_research_id=rec.research_id,
                    bound_label="A",
                    guessed=False,
                    reason="session last_research_id matches labeled ResearchRecord A",
                )
        if rec is None and rid:
            return PointerResolution(
                pointer="その技術A",
                status="UNRESOLVED",
                bound_research_id="",
                bound_label="",
                guessed=False,
                reason="last_research_id set but record missing from store",
            )
        if rec is None:
            return PointerResolution(
                pointer="その技術A",
                status="UNRESOLVED",
                bound_research_id="",
                bound_label="",
                guessed=False,
                reason="no session last_research_id; do not guess technology A",
            )
        return PointerResolution(
            pointer="その技術A",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="session record is not labeled A; do not rebind by string alone",
        )

    if _ENV.search(requirement):
        env = str(session.get("last_environment") or session.get("last_os") or "")
        if env:
            return PointerResolution(
                pointer="その環境",
                status="BOUND",
                bound_research_id=rid,
                bound_label=env,
                guessed=False,
                reason="session last_environment / last_os",
            )
        return PointerResolution(
            pointer="その環境",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="その環境 has no session snapshot; do not infer Docker/OS",
        )

    if _PREV.search(requirement):
        if rec is not None:
            return PointerResolution(
                pointer="前のやつ",
                status="BOUND",
                bound_research_id=rec.research_id,
                bound_label=label,
                guessed=False,
                reason="session last_research_id",
            )
        return PointerResolution(
            pointer="前のやつ",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="前のやつ has no session target; do not guess",
        )

    if _THAT_TOOL.search(requirement):
        if session.get("tool_path") or session.get("last_spec"):
            return PointerResolution(
                pointer="そのTool",
                status="BOUND",
                bound_research_id=rid,
                bound_label=label or "tool",
                guessed=False,
                reason="session last_spec / tool_path",
            )
        return PointerResolution(
            pointer="そのTool",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="no session Tool spec",
        )

    if re.search(r"前の技術", requirement) and not re.search(r"技術A", requirement):
        # 一意な Record が 1 件だけのときだけ bind。複数なら推測しない。
        if len(store.records) == 1:
            only = store.records[0]
            return PointerResolution(
                pointer="前の技術",
                status="BOUND",
                bound_research_id=only.research_id,
                bound_label=str((only.environment_facts or {}).get("label") or ""),
                guessed=False,
                reason="only one ResearchRecord in store",
            )
        return PointerResolution(
            pointer="前の技術",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="前の技術 matches several records; do not guess",
        )

    if re.search(r"pythonの方", requirement, re.I) and not re.search(r"3\.\d+", requirement):
        hits = [r for r in store.records if _python_of(r)]
        if len(hits) == 1:
            return PointerResolution(
                pointer="Pythonの方",
                status="BOUND",
                bound_research_id=hits[0].research_id,
                bound_label=str((hits[0].environment_facts or {}).get("label") or ""),
                guessed=False,
                reason="unique Python record",
            )
        return PointerResolution(
            pointer="Pythonの方",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="Python matches several records; do not guess",
        )

    if re.search(r"別の方法", requirement):
        return PointerResolution(
            pointer="別の方法",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="別の方法 is not named; do not infer Docker/VM/other stack",
        )

    if re.search(r"その技術", requirement) and not re.search(r"技術A", requirement):
        if len(store.records) == 1:
            only = store.records[0]
            return PointerResolution(
                pointer="その技術",
                status="BOUND",
                bound_research_id=only.research_id,
                bound_label=str((only.environment_facts or {}).get("label") or ""),
                guessed=False,
                reason="only one ResearchRecord in store",
            )
        return PointerResolution(
            pointer="その技術",
            status="UNRESOLVED",
            bound_research_id="",
            bound_label="",
            guessed=False,
            reason="その技術 matches several records; do not guess",
        )

    return PointerResolution(
        pointer="",
        status="NOT_A_POINTER",
        bound_research_id=rid,
        bound_label=label,
        guessed=False,
        reason="no catalogued pointer in text",
    )


def bind_requires_session_id(requirement: str, session: dict[str, Any], store: ResearchStore) -> bool:
    """True only when pointer + session id agree. String match alone is not enough."""
    r = classify_pointer(requirement, store=store, session=session)
    return r.status == "BOUND" and bool(r.bound_research_id)
