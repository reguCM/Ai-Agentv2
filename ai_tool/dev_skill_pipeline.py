"""Bounded Dev Skill pipeline harness for E2E and observation.

Loads steps from `registry/skills.json` compositions and produces validated
Goal Handoff artifacts before Production Chat implementation.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator

from ai_tool.grill_me_loop import (
    PHASE1_GRILL,
    GrillMeResult,
    SIMULATED_HUMAN_RESPONSE_KIND,
    TEST_AUTO_RECOMMENDATION_POLICY,
    run_grill_me_loop,
)
from ai_tool.precondition_contract import validate_preconditions
from ai_tool.llm_json_parse import (
    LLMEmptyResponseError,
    llm_response_diagnostics,
    message_content,
    parse_json_content,
    strip_json_fence,
)
from ai_tool.pipeline_observations import (
    PipelineBudgetExceeded,
    PipelineObserver,
    observed_llm_json,
)

PHASE2_SKILLS = "phase2_skills"
from ai_tool.skill_applicability import (
    SkillApplicabilityItem,
    SkillApplicabilityReport,
    SkillArtifacts,
    SkillStepOutcome,
    run_skill_value_consumption_loop,
)
from tools.system.llm import chat as llm_chat


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "registry" / "skills.json"
HANDOFF_SCHEMA_PATH = REPO_ROOT / "registry" / "schema" / "goal_handoff.schema.json"

VAGUE_REQUEST_EXAMPLE = "テトリスを作って"
LLM_JSON_MAX_ATTEMPTS = 3


@dataclass
class SkillStepResult:
    skill_id: str
    status: str
    artifact_paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class DevSkillPipelineResult:
    composition_id: str
    skill_steps: list[str]
    initial_request: str
    selection_policy: str
    grill_report: dict[str, Any] | None = None
    aligned_spec: dict[str, Any] | None = None
    phase1_spec_finalized: bool = False
    value_consumption_report: dict[str, Any] | None = None
    step_results: list[SkillStepResult] = field(default_factory=list)
    handoff_packet: dict[str, Any] = field(default_factory=dict)
    implementation_prompt: str = ""
    applicability_report: SkillApplicabilityReport | None = None
    timing_summary: dict[str, Any] | None = None
    budget_report: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["step_results"] = [asdict(item) for item in self.step_results]
        if self.applicability_report is not None:
            payload["applicability_report"] = self.applicability_report.as_dict()
        return payload


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_skill_path(skill_id: str, registry: Mapping[str, Any] | None = None) -> Path:
    catalog = registry or load_registry()
    for skill in catalog.get("skills") or []:
        if skill.get("id") == skill_id:
            return REPO_ROOT / str(skill["path"])
    raise KeyError(f"Unknown skill id: {skill_id}")


def load_skill_instructions(skill_id: str, registry: Mapping[str, Any] | None = None) -> str:
    path = load_skill_path(skill_id, registry)
    return path.read_text(encoding="utf-8")


def composition_steps(
    composition_id: str,
    registry: Mapping[str, Any] | None = None,
) -> list[str]:
    catalog = registry or load_registry()
    for composition in catalog.get("compositions") or []:
        if composition.get("id") == composition_id:
            return list(composition.get("steps") or [])
    raise KeyError(f"Unknown composition id: {composition_id}")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _handoff_id(slug: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cleaned = re.sub(r"[^a-z0-9-]", "-", slug.casefold()).strip("-")
    cleaned = cleaned[:40] or "tetris"
    return f"gh-{stamp}-{cleaned}"


def _git_observation() -> dict[str, str]:
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    return {
        "branch": branch,
        "head": head,
        "worktree": str(REPO_ROOT),
    }


def _message_content(response: Any) -> str:
    return message_content(response)


def _strip_json_fence(text: str) -> str:
    return strip_json_fence(text)


def build_implementation_prompt(spec: Mapping[str, Any]) -> str:
    title = str(spec.get("title") or "Implementation request").strip()
    summary = str(spec.get("summary") or "").strip()
    conditions = [str(item).strip() for item in (spec.get("numbered_conditions") or []) if str(item).strip()]
    non_goals = [str(item).strip() for item in (spec.get("non_goals") or []) if str(item).strip()]
    acceptance = [
        str(item).strip() for item in (spec.get("acceptance_criteria") or []) if str(item).strip()
    ]
    lines = [title]
    if summary:
        lines.extend(["", summary])
    if conditions:
        lines.extend(["", "完了条件:"])
        lines.extend(f"{index}. {item}" for index, item in enumerate(conditions, 1))
    if non_goals:
        lines.extend(["", "非目標:"])
        lines.extend(f"- {item}" for item in non_goals)
    if acceptance:
        lines.extend(["", "受け入れ基準:"])
        lines.extend(f"- {item}" for item in acceptance)
    return "\n".join(lines).strip()


def _call_llm_json(
    *,
    model: str,
    system: str,
    user: str,
    chat_fn: Callable[..., Any] | None = None,
    observer: PipelineObserver | None = None,
    phase: str = PHASE2_SKILLS,
    skill_id: str = "unknown",
) -> dict[str, Any]:
    fn = chat_fn or llm_chat

    def _invoke() -> dict[str, Any]:
        last_empty: LLMEmptyResponseError | None = None
        for attempt in range(LLM_JSON_MAX_ATTEMPTS):
            response = fn(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                format="json",
                execution_profile="structured_output",
            )
            diagnostics = llm_response_diagnostics(response)
            diagnostics["attempt"] = attempt + 1
            try:
                return parse_json_content(
                    _message_content(response),
                    diagnostics=diagnostics,
                )
            except LLMEmptyResponseError as exc:
                last_empty = exc
                if attempt + 1 >= LLM_JSON_MAX_ATTEMPTS:
                    raise
        if last_empty is not None:
            raise last_empty
        raise LLMEmptyResponseError("LLM JSON call produced no payload")

    return observed_llm_json(
        observer,
        phase=phase,
        skill_id=skill_id,
        model=model,
        round_index=None,
        call_llm=_invoke,
    )


def _artifact_rel_path(path: Path, output_dir: Path) -> str:
    for base in (REPO_ROOT, output_dir):
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def _write_text(path: Path, content: str, *, output_dir: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return _artifact_rel_path(path, output_dir)


def _skill_system(skill_id: str, registry: Mapping[str, Any]) -> str:
    body = load_skill_instructions(skill_id, registry)
    return (
        f"You are executing the repository Dev Skill `{skill_id}` inside an autonomous E2E harness.\n"
        "Follow the skill intent, but respond ONLY with JSON as requested.\n"
        "When the skill expects human answers, emit a recommended_answer field and the harness "
        "will auto-select it.\n\n"
        f"--- SKILL.md ({skill_id}) ---\n"
        f"{body[:6000]}\n"
        "--- END SKILL ---"
    )


def _aligned_spec_from_prd(prd: Mapping[str, Any], initial_request: str) -> dict[str, Any]:
    acceptance = [str(item) for item in (prd.get("acceptance_criteria") or []) if str(item).strip()]
    numbered = list(acceptance)
    requirements = prd.get("requirements")
    if isinstance(requirements, str) and requirements.strip():
        for line in requirements.splitlines():
            cleaned = re.sub(r"^\s*[-*]\s*|\s*\[[ xX]\]\s*", "", line).strip()
            if cleaned and cleaned not in numbered:
                numbered.append(cleaned)
    non_goals_raw = prd.get("non_goals")
    non_goals: list[str] = []
    if isinstance(non_goals_raw, list):
        non_goals = [str(item) for item in non_goals_raw if str(item).strip()]
    elif isinstance(non_goals_raw, str) and non_goals_raw.strip():
        non_goals = [
            re.sub(r"^\s*[-*]\s*", "", line).strip()
            for line in non_goals_raw.splitlines()
            if line.strip()
        ]
    return {
        "title": str(prd.get("title") or "Implementation goal"),
        "summary": str(prd.get("goals") or prd.get("problem") or initial_request),
        "numbered_conditions": numbered or [initial_request],
        "non_goals": non_goals,
        "acceptance_criteria": acceptance,
    }


def _generate_grill_me(
    *,
    model: str,
    initial_request: str,
    registry: Mapping[str, Any],
    chat_fn: Callable[..., Any] | None,
) -> dict[str, Any]:
    return _call_llm_json(
        model=model,
        system=(
            _skill_system("grill-me", registry)
            + "\n\nHarness policy: single-shot freeform mode. "
            "Do NOT run multi-round interview loops. "
            "Emit GRILL_JSON with keys: "
            "aligned_spec (object with title, summary, numbered_conditions, non_goals, acceptance_criteria), "
            "ambiguity_report (object with dimensions, aggregate, threshold, weakest), "
            "gate_passed (bool), recommended_answer."
        ),
        user=(
            f"Initial request:\n{initial_request}\n\n"
            "Resolve ambiguity in one response for downstream write-prd."
        ),
        chat_fn=chat_fn,
    )


def _generate_prd(
    *,
    model: str,
    initial_request: str,
    aligned_spec: Mapping[str, Any] | None,
    registry: Mapping[str, Any],
    chat_fn: Callable[..., Any] | None,
    observer: PipelineObserver | None = None,
) -> dict[str, Any]:
    aligned_block = ""
    if aligned_spec:
        aligned_block = (
            "\n\nPrior grill-me aligned_spec JSON:\n"
            f"{json.dumps(dict(aligned_spec), ensure_ascii=False, indent=2)}"
        )
    return _call_llm_json(
        model=model,
        system=(
            _skill_system("write-prd", registry)
            + "\n\nHarness policy: run Phase 4 only in a single response. "
            "Phase 1 standalone grill-me already finalized the spec; do NOT re-run Phase 3 "
            "or Phase 5 interview loops or re-open resolved decisions."
        ),
        user=(
            f"Initial request:\n{initial_request}"
            f"{aligned_block}\n\n"
            "Emit PRD_JSON with keys: title, problem, goals, requirements, non_goals, constraints, "
            "acceptance_criteria (array), recommended_answer (summary for harness auto-select)."
        ),
        chat_fn=chat_fn,
        observer=observer,
        skill_id="write-prd",
    )


def _generate_tech_spec(
    *,
    model: str,
    prd: Mapping[str, Any],
    registry: Mapping[str, Any],
    chat_fn: Callable[..., Any] | None,
    observer: PipelineObserver | None = None,
) -> dict[str, Any]:
    return _call_llm_json(
        model=model,
        system=(
            _skill_system("tech-spec", registry)
            + "\n\nHarness policy: skip Phase 6 grill-me gate. Single TECH_SPEC_JSON response only."
        ),
        user=(
            f"PRD JSON:\n{json.dumps(dict(prd), ensure_ascii=False, indent=2)}\n\n"
            "For this E2E, implementation target is Dedicated Sandbox via Production Chat "
            "create_file only. Emit TECH_SPEC_JSON with keys: summary, modules, sequencing, "
            "sandbox_constraints, implementation_tasks (array of {id,title,acceptance,size}), "
            "recommended_answer."
        ),
        chat_fn=chat_fn,
        observer=observer,
        skill_id="tech-spec",
    )


def _generate_plan(
    *,
    model: str,
    tech_spec: Mapping[str, Any],
    registry: Mapping[str, Any],
    chat_fn: Callable[..., Any] | None,
    observer: PipelineObserver | None = None,
    confirmed_clarifications: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    from ai_tool.human_decision_premise import (
        active_decision_catalog,
        format_active_decision_catalog_for_prompt,
    )

    catalog_block = ""
    catalog = active_decision_catalog(confirmed_clarifications)
    if catalog:
        catalog_block = (
            "\n\nActive Human Decisions:\n"
            f"{format_active_decision_catalog_for_prompt(catalog)}\n\n"
            "For each task, include premise_decision_keys only when that task semantically "
            "depends on a listed decision. Do not attach every decision to every task. "
            "Use exact decision_key strings from the catalog."
        )
    return _call_llm_json(
        model=model,
        system=_skill_system("planning-and-task-breakdown", registry),
        user=(
            f"Tech spec JSON:\n{json.dumps(dict(tech_spec), ensure_ascii=False, indent=2)}"
            f"{catalog_block}\n\n"
            "Emit PLAN_JSON with keys: plan_markdown, todo_markdown, tasks "
            "(array of {id,title,acceptance,verification,size,dependencies,premise_decision_keys}), "
            "recommended_answer."
        ),
        chat_fn=chat_fn,
        observer=observer,
        skill_id="planning-and-task-breakdown",
    )


def _normalize_task_id(raw: Any, index: int) -> str:
    """Legacy helper; handoff packet building uses positional ids via normalize_implementation_tasks."""
    text = str(raw or "").strip()
    if re.fullmatch(r"T\d+", text, re.I):
        return "T" + text[1:]
    digits = re.sub(r"\D", "", text)
    if digits:
        return f"T{int(digits)}"
    return f"T{index}"


def _register_task_id_alias(remap: dict[str, str], raw: Any, canonical: str) -> None:
    text = str(raw or "").strip()
    if not text:
        return
    remap[text] = canonical
    if re.fullmatch(r"T\d+", text, re.I):
        remap["T" + text[1:]] = canonical
    digits = re.sub(r"\D", "", text)
    if digits:
        remap[digits] = canonical
        remap[f"T{int(digits)}"] = canonical


def _build_task_id_remap(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    """Map LLM-supplied aliases to deterministic positional task ids (T1..Tn)."""
    remap: dict[str, str] = {}
    for index, row in enumerate(rows, 1):
        canonical = f"T{index}"
        remap[canonical] = canonical
        remap[str(index)] = canonical
        for key in ("id", "task_id"):
            _register_task_id_alias(remap, row.get(key), canonical)
    return remap


def _resolve_task_dependency(
    raw: Any,
    remap: Mapping[str, str],
    *,
    task_count: int,
) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text in remap:
        return remap[text]
    if re.fullmatch(r"T\d+", text, re.I):
        normalized = "T" + text[1:]
        if normalized in remap:
            return remap[normalized]
    digits = re.sub(r"\D", "", text)
    if digits:
        for key in (digits, f"T{int(digits)}"):
            if key in remap:
                return remap[key]
        ordinal = int(digits)
        if 1 <= ordinal <= task_count:
            return f"T{ordinal}"
    return None


def coerce_task_string_list(value: Any) -> list[str]:
    """Normalize acceptance/verification lists; repair accidental char-split strings."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    if len(items) >= 8 and all(len(item) == 1 for item in items):
        joined = "".join(items)
        if len(joined) >= 8:
            return [joined]
    return items


def normalize_implementation_tasks(
    rows: Iterable[Mapping[str, Any]],
    *,
    default_acceptance: list[str],
    default_verification: list[str],
) -> list[dict[str, Any]]:
    """Assign deterministic T1..Tn ids and remap dependency references."""
    raw_rows = [row for row in rows if isinstance(row, Mapping)]
    if not raw_rows:
        acceptance = default_acceptance or ["Create minimal console Tetris at tetris/main.py"]
        return [
            {
                "id": "T1",
                "title": "Create tetris/main.py in Dedicated Sandbox",
                "acceptance": acceptance[:3],
                "verification": default_verification,
                "dependencies": [],
                "size": "S",
                "maps_to_acceptance": ["A1"],
            }
        ]

    remap = _build_task_id_remap(raw_rows)
    tasks: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows, 1):
        canonical_id = f"T{index}"
        acceptance = coerce_task_string_list(row.get("acceptance")) or default_acceptance[:1] or [
            "Implement minimal Tetris in Sandbox"
        ]
        verification = coerce_task_string_list(row.get("verification")) or default_verification
        dependencies: list[str] = []
        for item in row.get("dependencies") or []:
            resolved = _resolve_task_dependency(
                item,
                remap,
                task_count=len(raw_rows),
            )
            if resolved and resolved != canonical_id:
                dependencies.append(resolved)
        dependencies = sorted(
            dict.fromkeys(dependencies),
            key=lambda dep: int(re.sub(r"\D", "", dep) or "0"),
        )
        task_row = {
            "id": canonical_id,
            "title": str(row.get("title") or f"Task {index}"),
            "acceptance": acceptance,
            "verification": verification,
            "dependencies": dependencies,
            "size": _normalize_size(row.get("size")),
            "maps_to_acceptance": [f"A{index}"],
        }
        premises = row.get("decision_premises")
        if isinstance(premises, list) and premises:
            task_row["decision_premises"] = premises
        premise_keys = row.get("premise_decision_keys")
        if isinstance(premise_keys, list) and premise_keys:
            task_row["premise_decision_keys"] = [
                str(item).strip() for item in premise_keys if str(item).strip()
            ]
        tasks.append(task_row)
    return tasks


def _normalize_size(raw: Any) -> str:
    text = str(raw or "").strip().upper()
    if text in {"S", "M", "L", "XL"}:
        return text
    lowered = str(raw or "").casefold()
    if "xl" in lowered or "extra" in lowered:
        return "XL"
    if "large" in lowered or "5-8" in lowered:
        return "L"
    if "medium" in lowered or "3-5" in lowered:
        return "M"
    return "S"


def build_handoff_packet(
    *,
    initial_request: str,
    prd: Mapping[str, Any] | None = None,
    aligned_spec: Mapping[str, Any] | None = None,
    prd_rel: str,
    tech_spec_rel: str,
    plan_rel: str,
    todo_rel: str,
    tech_spec: Mapping[str, Any],
    plan: Mapping[str, Any],
    skill_steps: list[str],
    handoff_slug: str = "tetris-sandbox-e2e",
    confirmed_clarifications: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if prd is not None:
        aligned = _aligned_spec_from_prd(prd, initial_request)
    elif aligned_spec is not None:
        aligned = dict(aligned_spec)
    else:
        aligned = {}
    conditions = [str(item) for item in (aligned.get("numbered_conditions") or []) if str(item).strip()]
    non_goals = [str(item) for item in (aligned.get("non_goals") or []) if str(item).strip()]
    acceptance = [
        str(item) for item in (aligned.get("acceptance_criteria") or []) if str(item).strip()
    ]
    default_acceptance = conditions[:1] or ["Implement minimal Tetris in Sandbox"]
    default_verification = ["Check tetris/main.py exists in Dedicated Sandbox"]
    task_rows = plan.get("tasks") or tech_spec.get("implementation_tasks") or []
    tasks = normalize_implementation_tasks(
        task_rows if isinstance(task_rows, list) else [],
        default_acceptance=default_acceptance,
        default_verification=default_verification,
    )
    if confirmed_clarifications:
        from ai_tool.human_decision_premise import finalize_handoff_implementation_tasks

        tasks = finalize_handoff_implementation_tasks(tasks, confirmed_clarifications)

    acceptance_rows = []
    for index, statement in enumerate(acceptance or conditions[:2] or ["tetris/main.py exists"], 1):
        acceptance_rows.append(
            {
                "id": f"A{index}",
                "statement": statement,
                "verification": "Dedicated Sandbox E2E observation",
            }
        )

    return {
        "handoff_version": "0.1",
        "handoff_id": _handoff_id(handoff_slug),
        "status": "ready",
        "provisional": True,
        "created_at": _utc_iso(),
        "source": {
            "skills": skill_steps,
            "documents": {
                "prd": prd_rel,
                "tech_spec": tech_spec_rel,
                "plan": plan_rel,
                "task_list": todo_rel,
            },
            "git": _git_observation(),
        },
        "goal": {
            "summary": str(
                aligned.get("summary")
                or tech_spec.get("summary")
                or "Dedicated Sandbox 内に最小テトリスを実装する。"
            ),
            "original_request_excerpt": initial_request[:240],
        },
        "scope": {
            "in_scope": conditions
            or [
                "Dedicated Sandbox 内の tetris/main.py 作成",
                "コンソール版最小テトリス",
            ],
            "non_goals": non_goals
            or [
                "Production / dev worktree への書き込み",
                "GUI 版テトリス",
            ],
            "affected_paths": ["tetris/main.py"],
        },
        "acceptance_criteria": acceptance_rows,
        "implementation_tasks": tasks,
        "test_plan": {
            "pytest": ["tests/ai_tool/test_dev_skill_pipeline.py"],
            "e2e": ["ai_tool/run_tetris_sandbox_e2e.py"],
            "manual": ["Confirm Dedicated Sandbox contains tetris/main.py"],
        },
        "human_gates": [],
        "risks": [
            {
                "statement": "Production Chat may fail before Sandbox bootstrap",
                "impact": "high",
                "mitigation": "Observe sandbox_session and create_file tool_result in E2E logs",
            }
        ],
        "open_questions": [],
        "runtime_boundary": {
            "production_connected": False,
            "notes": "E2E harness consumes handoff prompt locally; Production Runtime handoff ingest is NOT CONNECTED.",
        },
    }


def validate_handoff_packet(packet: Mapping[str, Any]) -> list[str]:
    schema = json.loads(HANDOFF_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = [error.message for error in validator.iter_errors(dict(packet))]
    if "preconditions" in packet:
        errors.extend(validate_preconditions(packet.get("preconditions")))
    return sorted(errors)


def _artifacts_from_context(context: Mapping[str, Any]) -> SkillArtifacts:
    artifacts = SkillArtifacts()
    if context.get("grill_me_executed"):
        artifacts.add_outputs("grill-me")
    if context.get("prd") is not None:
        artifacts.add_outputs("write-prd")
    if context.get("knowledge_map") is not None:
        artifacts.add_outputs("graph-engineering")
    if context.get("tech_spec") is not None:
        artifacts.add_outputs("tech-spec")
    if context.get("plan") is not None:
        artifacts.add_outputs("planning-and-task-breakdown")
    if context.get("handoff_rel"):
        artifacts.add_outputs("goal-handoff")
    return artifacts


def _applicability_note(item: SkillApplicabilityItem) -> list[str]:
    notes = [
        f"usability={item.usability}",
        f"value={item.value}",
    ]
    notes.extend(item.usability_reasons)
    notes.extend(item.value_reasons)
    return notes


def handoff_to_implementation_prompt(packet: Mapping[str, Any]) -> str:
    lines = [str((packet.get("goal") or {}).get("summary") or "").strip(), ""]
    scope = packet.get("scope") or {}
    in_scope = [str(item) for item in (scope.get("in_scope") or []) if str(item).strip()]
    if in_scope:
        lines.append("スコープ:")
        lines.extend(f"- {item}" for item in in_scope)
        lines.append("")
    lines.append("完了条件:")
    for index, item in enumerate(in_scope or [], 1):
        lines.append(f"{index}. {item}")
    if not in_scope:
        for index, task in enumerate(packet.get("implementation_tasks") or [], 1):
            if isinstance(task, Mapping):
                lines.append(f"{index}. {task.get('title')}")
    lines.append("")
    lines.append("実装タスク:")
    for task in packet.get("implementation_tasks") or []:
        if not isinstance(task, Mapping):
            continue
        lines.append(f"- {task.get('id')}: {task.get('title')}")
    lines.append("")
    lines.append("非目標:")
    for item in scope.get("non_goals") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).strip()


def _run_composition_skill(
    skill_id: str,
    *,
    initial_request: str,
    context: dict[str, Any],
    result: DevSkillPipelineResult,
    design_dir: Path,
    output_dir: Path,
    model: str,
    registry: Mapping[str, Any],
    steps: list[str],
    executed_skills: list[str],
    chat_fn: Callable[..., Any] | None,
    observer: PipelineObserver | None = None,
) -> tuple[SkillStepResult, SkillStepOutcome]:
    step = SkillStepResult(skill_id=skill_id, status="pending")

    try:
        if skill_id == "write-prd":
            prd_payload = _generate_prd(
                model=model,
                initial_request=initial_request,
                aligned_spec=context.get("aligned_spec"),
                registry=registry,
                chat_fn=chat_fn,
                observer=observer,
            )
            prd_md = (
                f"# {prd_payload.get('title') or 'Tetris PRD'}\n\n"
                f"## Problem\n{prd_payload.get('problem') or ''}\n\n"
                f"## Goals\n{prd_payload.get('goals') or ''}\n\n"
                f"## Requirements\n{prd_payload.get('requirements') or ''}\n\n"
                f"## Non-Goals\n{prd_payload.get('non_goals') or ''}\n\n"
                f"## Constraints\n{prd_payload.get('constraints') or ''}\n\n"
                f"## Acceptance\n{json.dumps(prd_payload.get('acceptance_criteria') or [], ensure_ascii=False, indent=2)}\n"
            )
            prd_rel = _write_text(design_dir / "prd.md", prd_md, output_dir=output_dir)
            context["prd"] = prd_payload
            context["prd_rel"] = prd_rel
            step.artifact_paths.append(prd_rel)
            step.status = "done"
            step.notes.append("phase2_value_loop:after_phase1_grill")
            executed_skills.append(skill_id)
            return step, SkillStepOutcome(status="done", gate_passed=True)

        if skill_id == "tech-spec":
            prd_payload = context.get("prd")
            if prd_payload is None:
                raise RuntimeError("write-prd must run before tech-spec")
            tech_payload = _generate_tech_spec(
                model=model,
                prd=prd_payload,
                registry=registry,
                chat_fn=chat_fn,
                observer=observer,
            )
            tech_md = (
                f"# Tech Spec\n\n"
                f"{tech_payload.get('summary') or ''}\n\n"
                f"## Modules\n{json.dumps(tech_payload.get('modules') or [], ensure_ascii=False, indent=2)}\n\n"
                f"## Sequencing\n{json.dumps(tech_payload.get('sequencing') or [], ensure_ascii=False, indent=2)}\n\n"
                f"## Sandbox Constraints\n{tech_payload.get('sandbox_constraints') or ''}\n"
            )
            tech_rel = _write_text(design_dir / "tech-spec.md", tech_md, output_dir=output_dir)
            context["tech_spec"] = tech_payload
            context["tech_spec_rel"] = tech_rel
            step.artifact_paths.append(tech_rel)
            step.status = "done"
            executed_skills.append(skill_id)
            return step, SkillStepOutcome(status="done", gate_passed=True)

        if skill_id == "planning-and-task-breakdown":
            tech_payload = context.get("tech_spec")
            if tech_payload is None:
                raise RuntimeError("tech-spec must run before planning")
            plan_payload = _generate_plan(
                model=model,
                tech_spec=tech_payload,
                registry=registry,
                chat_fn=chat_fn,
                observer=observer,
                confirmed_clarifications=context.get("confirmed_clarifications"),
            )
            plan_rel = _write_text(
                design_dir / "plan.md",
                str(plan_payload.get("plan_markdown") or "# Plan\n\nImplement tetris/main.py in Sandbox.\n"),
                output_dir=output_dir,
            )
            todo_rel = _write_text(
                design_dir / "todo.md",
                str(plan_payload.get("todo_markdown") or "- [ ] T1 Create tetris/main.py\n"),
                output_dir=output_dir,
            )
            context["plan"] = plan_payload
            context["plan_rel"] = plan_rel
            context["todo_rel"] = todo_rel
            step.artifact_paths.extend([plan_rel, todo_rel])
            step.status = "done"
            executed_skills.append(skill_id)
            return step, SkillStepOutcome(status="done", gate_passed=True)

        if skill_id == "goal-handoff":
            prd_payload = context.get("prd")
            aligned = context.get("aligned_spec")
            if prd_payload is None and not isinstance(aligned, Mapping):
                raise RuntimeError("goal-handoff requires prior write-prd or phase1 grill output")
            packet = build_handoff_packet(
                initial_request=initial_request,
                prd=prd_payload if isinstance(prd_payload, Mapping) else None,
                aligned_spec=aligned if isinstance(aligned, Mapping) else None,
                prd_rel=str(context.get("prd_rel") or ""),
                tech_spec_rel=str(context.get("tech_spec_rel") or ""),
                plan_rel=str(context.get("plan_rel") or ""),
                todo_rel=str(context.get("todo_rel") or ""),
                tech_spec=context.get("tech_spec") or {},
                plan=context.get("plan") or {},
                skill_steps=["grill-me", *executed_skills] if executed_skills else steps,
                confirmed_clarifications=context.get("confirmed_clarifications"),
            )
            errors = validate_handoff_packet(packet)
            if errors:
                raise ValueError("handoff schema errors: " + "; ".join(errors))
            handoff_rel = _write_text(
                design_dir / "handoff.json",
                json.dumps(packet, ensure_ascii=False, indent=2),
                output_dir=output_dir,
            )
            result.handoff_packet = packet
            result.implementation_prompt = handoff_to_implementation_prompt(packet)
            if not result.implementation_prompt and isinstance(aligned, Mapping):
                result.implementation_prompt = build_implementation_prompt(aligned)
            elif not result.implementation_prompt and isinstance(prd_payload, Mapping):
                result.implementation_prompt = build_implementation_prompt(
                    _aligned_spec_from_prd(prd_payload, initial_request)
                )
            context["handoff_rel"] = handoff_rel
            step.artifact_paths.append(handoff_rel)
            step.status = "done"
            executed_skills.append(skill_id)
            return step, SkillStepOutcome(status="done", gate_passed=True)

        if skill_id == "graph-engineering":
            step.status = "skipped"
            step.notes.append("graph-engineering harness not wired in Phase 0")
            return step, SkillStepOutcome(status="skipped")

        step.status = "skipped"
        step.notes.append("skill not wired in harness")
        return step, SkillStepOutcome(status="skipped")

    except LLMEmptyResponseError as exc:
        step.status = "error"
        step.notes.append(f"{type(exc).__name__}: {exc}")
        diagnostics = getattr(exc, "diagnostics", None)
        if isinstance(diagnostics, dict):
            step.notes.append(
                "llm_empty_response:"
                f"content_len={diagnostics.get('content_len')},"
                f"thinking_len={diagnostics.get('thinking_len')},"
                f"done_reason={diagnostics.get('done_reason')}"
            )
        result.errors.append(f"{skill_id}: {type(exc).__name__}: {exc}")
        return step, SkillStepOutcome(status="error", notes=[str(exc)])
    except Exception as exc:  # noqa: BLE001
        step.status = "error"
        step.notes.append(f"{type(exc).__name__}: {exc}")
        result.errors.append(f"{skill_id}: {type(exc).__name__}: {exc}")
        return step, SkillStepOutcome(status="error", notes=[str(exc)])


def _finalize_pipeline_result(
    result: DevSkillPipelineResult,
    observer: PipelineObserver | None,
    *,
    emit_e2e_end: bool = False,
    e2e_status: str = "pipeline_completed",
    notes: list[str] | None = None,
) -> DevSkillPipelineResult:
    if observer is not None:
        result.timing_summary = observer.summarize_timing()
        if emit_e2e_end:
            observer.e2e_end(status=e2e_status, notes=notes)
    return result


def run_dev_skill_pipeline(
    initial_request: str,
    *,
    composition_id: str = "tetris-sandbox-e2e",
    model: str,
    output_dir: Path,
    auto_select: str = TEST_AUTO_RECOMMENDATION_POLICY,
    chat_fn: Callable[..., Any] | None = None,
    consumer: str = "local_agent",
    resume_session: bool = False,
    max_grill_rounds: int = 8,
    min_grill_rounds_before_score: int = 3,
    budget_seconds: float | None = None,
    observer: PipelineObserver | None = None,
    emit_e2e_end: bool = False,
    mission_id: str | None = None,
    confirmed_clarifications: Sequence[Mapping[str, Any]] | None = None,
    orchestrator: Any | None = None,
) -> DevSkillPipelineResult:
    registry = load_registry()
    steps = composition_steps(composition_id, registry)
    result = DevSkillPipelineResult(
        composition_id=composition_id,
        skill_steps=steps,
        initial_request=initial_request,
        selection_policy=auto_select,
    )
    result.applicability_report = SkillApplicabilityReport(
        request_excerpt=str(initial_request or "")[:240],
        consumer=consumer,
        composition_id=composition_id,
    )
    design_dir = output_dir / "design"
    design_dir.mkdir(parents=True, exist_ok=True)

    active_observer = observer or PipelineObserver(output_dir, budget_seconds=budget_seconds)
    active_observer.set_work_plan(composition_steps=steps, include_production_chat=False)
    if budget_seconds is not None:
        result.budget_report = {
            "budget_seconds": budget_seconds,
            "status": "running",
        }

    grill: GrillMeResult | None = None
    try:
        active_observer.phase_start(PHASE1_GRILL)
        active_observer.skill_start(PHASE1_GRILL, "grill-me")
        grill = run_grill_me_loop(
            initial_request,
            model=model,
            mode="freeform",
            max_rounds=max_grill_rounds,
            min_rounds_before_score=min_grill_rounds_before_score,
            auto_select=auto_select,
            chat_fn=chat_fn,
            observer=active_observer,
        )
    except PipelineBudgetExceeded as exc:
        active_observer.skill_end(PHASE1_GRILL, "grill-me", status="budget_exceeded")
        active_observer.phase_end(PHASE1_GRILL, status="budget_exceeded")
        result.budget_report = exc.snapshot
        result.errors.append("pipeline_budget_exceeded")
        return _finalize_pipeline_result(
            result,
            active_observer,
            emit_e2e_end=emit_e2e_end,
            e2e_status="budget_exceeded",
        )

    assert grill is not None
    result.grill_report = {
        "ambiguity_report": grill.ambiguity_report,
        "gate_passed": grill.gate_passed,
        "source": "phase1_standalone_grill_me",
        "rounds": grill.rounds,
        "selection_policy": auto_select,
        "human_response_kind": SIMULATED_HUMAN_RESPONSE_KIND,
        "fallback_used": grill.fallback_used,
        "transcript": [asdict(item) for item in grill.transcript],
    }
    result.aligned_spec = dict(grill.aligned_spec)

    grill_step = SkillStepResult(skill_id="grill-me", status="pending")
    aligned_path = design_dir / "aligned_spec.json"
    aligned_rel = _write_text(
        aligned_path,
        json.dumps(result.aligned_spec, ensure_ascii=False, indent=2),
        output_dir=output_dir,
    )
    report_path = design_dir / "ambiguity_report.json"
    report_rel = _write_text(
        report_path,
        json.dumps(result.grill_report, ensure_ascii=False, indent=2),
        output_dir=output_dir,
    )
    grill_step.artifact_paths.extend([aligned_rel, report_rel])
    grill_step.status = "done" if grill.gate_passed else "partial"
    grill_step.notes.extend(
        [
            "phase1_standalone_spec_gate",
            f"selection_policy={auto_select}",
            f"human_response_kind={SIMULATED_HUMAN_RESPONSE_KIND}",
        ]
    )
    if grill.fallback_used:
        grill_step.notes.append("fallback_spec_used")
    result.step_results.append(grill_step)
    active_observer.skill_end(
        PHASE1_GRILL,
        "grill-me",
        status="done" if grill.gate_passed else "partial",
    )
    active_observer.phase_end(
        PHASE1_GRILL,
        status="done" if grill.gate_passed else "partial",
    )

    if not grill.gate_passed:
        result.errors.extend(grill.errors or ["phase1_grill_gate_not_passed"])
        return _finalize_pipeline_result(
            result,
            active_observer,
            emit_e2e_end=emit_e2e_end,
            e2e_status="phase1_failed",
        )

    result.phase1_spec_finalized = True
    from ai_tool.production_handoff_bridge import resolve_pipeline_clarifications

    pipeline_clarifications = resolve_pipeline_clarifications(
        orchestrator=orchestrator,
        mission_id=mission_id,
        confirmed_clarifications=confirmed_clarifications,
    )
    context: dict[str, Any] = {
        "initial_request": initial_request,
        "aligned_spec": result.aligned_spec,
        "grill_report": result.grill_report,
        "grill_me_executed": True,
        "confirmed_clarifications": pipeline_clarifications,
        "mission_id": mission_id,
    }
    executed_skills: list[str] = []

    initial_artifacts = SkillArtifacts()
    initial_artifacts.add_outputs("grill-me")

    def executor(skill_id: str) -> SkillStepOutcome:
        active_observer.check_budget()
        active_observer.skill_start(PHASE2_SKILLS, skill_id)
        try:
            step, outcome = _run_composition_skill(
                skill_id,
                initial_request=initial_request,
                context=context,
                result=result,
                design_dir=design_dir,
                output_dir=output_dir,
                model=model,
                registry=registry,
                steps=steps,
                executed_skills=executed_skills,
                chat_fn=chat_fn,
                observer=active_observer,
            )
            result.step_results.append(step)
            active_observer.skill_end(PHASE2_SKILLS, skill_id, status=step.status)
            return outcome
        except PipelineBudgetExceeded:
            active_observer.skill_end(PHASE2_SKILLS, skill_id, status="budget_exceeded")
            raise

    try:
        active_observer.phase_start(PHASE2_SKILLS)
        consumption = run_skill_value_consumption_loop(
            request=initial_request,
            composition_id=composition_id,
            executor=executor,
            consumer=consumer,
            registry=registry,
            resume_session=resume_session,
            initial_artifacts=initial_artifacts,
        )
        active_observer.phase_end(PHASE2_SKILLS, status="done")
    except PipelineBudgetExceeded as exc:
        active_observer.phase_end(PHASE2_SKILLS, status="budget_exceeded")
        result.budget_report = exc.snapshot
        result.errors.append("pipeline_budget_exceeded")
        result.timing_summary = active_observer.summarize_timing()
        return _finalize_pipeline_result(
            result,
            active_observer,
            emit_e2e_end=emit_e2e_end,
            e2e_status="budget_exceeded",
        )

    result.value_consumption_report = consumption.as_dict()

    if consumption.rounds:
        result.applicability_report.items = list(consumption.rounds[-1].snapshot)

    if not result.implementation_prompt:
        prd_payload = context.get("prd")
        aligned = context.get("aligned_spec")
        if isinstance(prd_payload, Mapping):
            result.implementation_prompt = build_implementation_prompt(
                _aligned_spec_from_prd(prd_payload, initial_request)
            )
        elif isinstance(aligned, Mapping):
            result.implementation_prompt = build_implementation_prompt(aligned)
        elif grill.implementation_prompt:
            result.implementation_prompt = grill.implementation_prompt

    if budget_seconds is not None:
        result.budget_report = active_observer.budget_snapshot(status="completed")

    return _finalize_pipeline_result(
        result,
        active_observer,
        emit_e2e_end=emit_e2e_end,
        e2e_status="pipeline_completed",
    )


__all__ = [
    "DevSkillPipelineResult",
    "LLMEmptyResponseError",
    "SkillStepResult",
    "VAGUE_REQUEST_EXAMPLE",
    "_aligned_spec_from_prd",
    "build_handoff_packet",
    "build_implementation_prompt",
    "coerce_task_string_list",
    "composition_steps",
    "handoff_to_implementation_prompt",
    "load_registry",
    "load_skill_instructions",
    "normalize_implementation_tasks",
    "parse_json_content",
    "run_dev_skill_pipeline",
    "validate_handoff_packet",
]
