# Human Requirement Resolution Architecture (READ-ONLY DESIGN)

**Date:** 2026-09-12  
**Revision:** 2026-09-12 — HD-1…HD-5 **closed** (human-adopted)  
**Basis:** `reports/HUMAN_REQUIREMENT_PRESERVATION_AUDIT.md` (confirmed facts at HEAD)  
**Scope:** Minimum architecture design only — **no implementation** in this revision.

---

## ADOPTED_HUMAN_DECISIONS (closed)

| ID | Decision | Adopted | Rationale (recorded) |
|----|----------|---------|----------------------|
| **HD-1** | Free-text extraction | **Span-first + LLM proposal + validator** | Fix human text first; LLM emits interpretation candidates only |
| **HD-2** | Unresolved `PREFERENCE` | **Stop Design only when `materiality=blocks_design`** | Avoid grill overload on every preference |
| **HD-3** | `development` vs build routing | **Any path that proceeds to implementation must pass Requirement Gate** | Boundary is “enters implementation”, not route label |
| **HD-4** | Canonical store | **Mission is requirement authority** | Closest to runtime; handoff and others are projections |
| **HD-5** | Prohibitions | **`disposition=CONSTRAINT` + `constraint_subtype=PROHIBITION`** | Minimal new concepts; clear semantics |

**Extraction pipeline (HD-1, normative):**

```text
original_goal (immutable)
  → span segmentation (mechanical / rule-assisted; covers full utterance)
  → per-span LLM proposal (disposition, unknown_kind, normalized_meaning candidate)
  → validator (coverage, no silent drop, provenance rules, validate_conditions)
  → mission.structured_requirements[]
```

**Implementation entry (HD-3, normative):** `classify_request` route (`chat` | `development` | `tool_creation` | …) does **not** exempt a turn from the gate. If the turn will create or advance an **implementation-class** orchestrator (tools that mutate workspace / task graph / test execution per policy), `requirement_resolution_phase` must be `REQUIREMENTS_RESOLVED` first. Spec-proposal-only paths that **do not** enter implementation may remain outside the gate until product defines otherwise.

---

## CURRENT_REUSABLE_COMPONENTS

| Component | Role today | Reuse for resolution architecture |
|-----------|------------|-----------------------------------|
| `mission.original_goal` | Immutable full user text | **Canonical Original Request** (unchanged) |
| `mission.explicit_conditions` / `explicit_constraints` | String arrays; constraints must not be LLM-invented | **Partial sink** for resolved acceptance / hard constraints after human confirmation |
| `mission.user_confirmed_supplements` + `confirmed_clarifications` | Human-confirmed text + `decision_id` / `decision_key` / `source` enum | **Human resolution outcomes** and provenance |
| `RequirementDecomposition` / `RequirementCondition` | Pre-orchestrator extraction; `status`, `ambiguity`, `original_description`, `source` | **Extraction + validation envelope** (extend fields, do not replace) |
| `RequirementStatus` | `READY`, `AMBIGUOUS`, `NEEDS_HUMAN_DECISION`, `TOOL_GAP`, … | **Gate statuses** before orchestrator; map to resolution phases |
| `validate_conditions` | Mechanical validators (`_VAGUE`, `_HUMAN_DECISION`, tool_gap) | **Non-LLM safety net**; must not be sole extractor for free text |
| `decompose_requirements` `_SYSTEM` prompt | Exists but **not called** on HEAD for free text | Candidate **LLM extractor** if wired with strict validator + provenance |
| `detect_unknown_concept` / `ConceptResolution` | Workspace identifier / definition gaps | **FACT_UNKNOWN** (definition) path; not vague adjectives |
| `gap_resolution_router.GapKind` | `fact_gap`, `target_identity_gap`, `spec_meaning_gap`, … | **Post-execution** gap taxonomy; pattern for unknown routing |
| `GapResolutionDecision` + `CapabilityId` | Routes to grill, tool evidence, replan, … | **Resolution routing** after gaps observed |
| `GrillQuestionContract` + `boundary_grill` | Material spec fork; `acceptance` dimension v0 | **Human question UI contract**; extend `grill_reason` |
| Conversation Grill / Goal Completion Gate | Identity / completion human loops | **Narrow Human paths**; resume patterns proven |
| `decision_change_gate` + `human_decision_premise` | `decision_key`, supersede, premise on tasks | **Stable human decision records** tied to tasks |
| `goal_handoff.schema.json` | `acceptance_criteria`, `open_questions`, `human_gates`, `scope.non_goals` | **AI Design Zone input** when Dev Skill path used; not default NL chat |
| `precondition_contract` + `environment_precondition_checker` | `evaluation.status` UNKNOWN/SATISFIED/… | **ENVIRONMENT_UNKNOWN** probe results (deterministic checks) |
| `ChatTaskOrchestrator` | `request`, tasks, `user_explicit_conditions`, grill state, snapshot | **Runtime carrier** during session; mirror mission resolution state |
| `is_agent_task` / `classify_request` | Regex routing | **Pre-resolution routing** (must run before contract gate) |
| `run_chat_turn` clarification branch | Blocks orchestrator when `requirement.status != READY` | **Existing gate hook** (only hit for failed numbered-list validation today) |

**Not reusable as-is for pre-design gate:** Agent loop `_chat_turn` (no structured requirement obligation), default T1 `relevant evidence observed`, `development` route → spec proposal bypass.

---

## PROPOSED_MINIMUM_ARCHITECTURE

End-to-end flow (target behavior):

```text
User message (run_chat_turn)
  → original_goal capture (immutable, immediate)
  → Agent Task routing (is_agent_task / route — implementation-intent only)
  → Human Requirement Extraction (structured records + dispositions)
  → validate_conditions + provenance rules (no silent drop)
  → Unresolved classification (intent / fact / environment)
  → Resolution routes (Grill / Research / Probe)
  → Human Decisions Closed (mission + orchestrator flag)
  → Requirement Contract (structured, execution-bound)
  → AI Design Zone (handoff fields, task decomposition, implementation tools)
```

**Placement principle:** Original Request and Resolved Structured Requirements are **separate layers**. Task Runtime and tool execution consume **Resolved Structured Requirements** + `original_goal` for audit only. Agent loop does not open until **Human Decisions Closed** for implementation-class missions.

**Phase 0 wedge (conceptual):** Single new **pre-`_chat_turn` gate** on the orchestrator creation path in `run_chat_turn` (`agent_turn.py` ~3781–3827), not a parallel runtime.

---

## REQUIREMENT_CONTRACT_LOCATION

### Comparison (no new type name committed)

| Option | Pros | Cons |
|--------|------|------|
| **A. Extend `mission.schema.json`** with `structured_requirements[]` (+ phase flag) | Durable SoT, aligns with `original_goal` immutability, supplements pattern exists | Schema migration, persist on first turn |
| **B. Orchestrator-only in-memory + snapshot** | Fast wedge, uses `snapshot()` | Lost without persist; weak cross-session |
| **C. Reuse `goal_handoff` packet for NL chat** | Richest fields (`acceptance_criteria`, `open_questions`) | PROVISIONAL, Dev Skill–oriented, not wired as NL default |
| **D. Only `RequirementDecomposition` turn JSON** | Already in events | Ephemeral; not execution contract |
| **E. New top-level `GoalContract` type** | Clear name | **No existing type**; duplicates mission + handoff unless carefully merged |

### Recommendation (minimum)

- **Authority:** `mission.original_goal` (original) + **`mission.structured_requirements`** (new block, name TBD in schema) + **`mission.requirement_resolution_phase`** (enum).
- **Session mirror:** `ChatTaskOrchestrator.requirement_contract_ref` → same IDs as mission rows (or embedded snapshot in `orchestrator.snapshot()`).
- **AI Design Zone artifact:** When entering decomposition/implementation, **project** resolved rows into `TaskRecord.completion_conditions`, `explicit_constraints`, and optionally a **`goal_handoff`-shaped view** for Dev Skill continuity — **projection**, not a second SoT.
- **Do not** replace `ChatTaskOrchestrator` or `AgentTaskRuntime`; **gate** them.

**New named `GoalContract` type:** **not required** for minimum wedge if mission block + orchestrator gate suffice.

---

## MINIMUM_REQUIREMENT_RECORD

Derived from existing `RequirementCondition` + mission `decision_record` patterns; **minimize new fields**.

| Field | Required | Notes |
|-------|----------|-------|
| `requirement_id` | yes | Stable id (e.g. `req-…` or reuse `condition_id` convention) |
| `source_text` | yes | **Verbatim substring** from `original_goal` (or full goal if indivisible in v0) |
| `source_span` | optional v0 | `[start, end]` utf-8 indices when extractor supports |
| `disposition` | yes | Analysis label (see CLASSIFICATION_MODEL); **not** deletion |
| `resolution_status` | yes | `resolved` \| `unresolved` \| `waived_by_human` (waive only via human supplement) |
| `unknown_kind` | when unresolved | Maps to UNKNOWN_RESOLUTION_MODEL |
| `normalized_meaning` | when resolved | Human- or research-confirmed wording; never overwrites `source_text` |
| `provenance` | yes | `user_explicit` \| `human_confirmed` \| `research_confirmed` \| `probe_confirmed` \| `llm_proposed` (llm_proposed **cannot** satisfy gate alone) |
| `materiality` | yes | `blocks_design` \| `informational` (HD-2: only `blocks_design` blocks Design) |
| `constraint_subtype` | when `CONSTRAINT` | e.g. `prohibition` \| `technology` \| `scope` (HD-5: `prohibition` for must-not) |
| `decision_owner` | when unresolved | `human` \| `research` \| `environment_probe` |
| `decision_id` / `decision_key` | optional | Link to `user_confirmed_supplements` / `confirmed_clarifications` |

**Reuse:** `RequirementCondition.description` → provisional `normalized_meaning` or acceptance text; `original_description` → alias for `source_text`; `ambiguity` → feeds `unknown_kind` mapping.

**Explicit constraints (mission):** Populated only from rows with disposition `CONSTRAINT` or `PROHIBITION` and `resolution_status=resolved` + `provenance` ∈ {`user_explicit`, `human_confirmed`}.

---

## CLASSIFICATION_MODEL

User-requested labels are **disposition** values on each **Requirement Record**, not filters that remove text from `original_goal`.

| Disposition | Meaning | Storage rule |
|-------------|---------|--------------|
| `GOAL` | Outcome the user wants | May become acceptance / goal title |
| `CONSTRAINT` | Hard bound (tech, must, must-not) | → `explicit_constraints` when resolved; use `constraint_subtype` |
| *(subtype)* `constraint_subtype=PROHIBITION` | Must-not / preserve (HD-5) | Same disposition `CONSTRAINT`; subtype distinguishes prohibition |
| `PREFERENCE` | Soft priority / tradeoff | Structured field; affects design hints, not silent drop |
| `AMBIGUOUS_REQUIREMENT` | Meaning not executable without human | `unresolved` + `unknown_kind=user_intent` |
| `CONTEXT` | Background, non-binding | Retained; `materiality=informational` |
| `NOISE` | Classifier believes non-requirement | **Still keep `source_text`**; disposition + rationale only |

**Extraction:** LLM or hybrid span extractor **proposes** dispositions; **validator** enforces:

- Every token span accounted for (union covers `original_goal` or explicit “unsegmented remainder” row).
- `NOISE` / `CONTEXT` with `materiality=blocks_design` forbidden without `human_confirmed`.
- No row deleted when disposition changes — **supersede** row via `status=superseded` (mirror mission supplements).

**Adopt as implementation enum?** **Yes**, as `disposition` string enum on requirement records — **not** as runtime routing enum separate from records.

---

## UNKNOWN_RESOLUTION_MODEL

Conceptual mapping to **existing** mechanisms (reuse candidates):

| Conceptual kind | Meaning | Reuse candidate | Route |
|-----------------|---------|-----------------|-------|
| **USER_INTENT_UNKNOWN** | Human must choose meaning | `RequirementStatus.NEEDS_HUMAN_DECISION`, `GrillQuestionContract`, Boundary/Conversation Grill, `user_confirmed_supplements` | Human / Grill |
| **FACT_UNKNOWN** | World/repo fact missing | `detect_unknown_concept`, `GapKind.FACT_GAP`, `CapabilityId.TOOL_EVIDENCE`, research route | Research / read tools |
| **ENVIRONMENT_UNKNOWN** | Runtime/env not verified | `precondition_contract` + `environment_precondition_checker`, handoff `preconditions[]`, `RequirementStatus.TOOL_GAP` (tool availability) | Probe / preflight |

**Do not** add a fourth global taxonomy in code until wedge lands; store `unknown_kind` on the requirement row and map in a **single router function** (analogous to `gap_resolution_router` but **pre-design**).

**LLM role:** Classify `unknown_kind` **proposal only**; gate advances only on `human_confirmed`, `research_confirmed`, or `probe_confirmed` (SATISFIED precondition).

---

## HUMAN_DECISION_GATE

### Materiality / question volume

**Problem:** Not every ambiguous token warrants a grill round.

**Proposed rule (machine-checkable skeleton):**

1. Extractor assigns each row `materiality`.
2. **Default:** `AMBIGUOUS_REQUIREMENT` → `materiality=blocks_design` unless proven otherwise.
3. **Downgrade to informational** only if:
   - deterministic rule says so (e.g. pure politeness particles), **or**
   - human confirms via supplement (`decision_key=requirement:materiality:…`).
4. **HD-2:** Unresolved `PREFERENCE` with `materiality=informational` does **not** block Design; default new preferences to `informational` unless extractor marks `blocks_design` (priority tradeoffs that change acceptance do).
4. **LLM may suggest** `informational` but **cannot** alone downgrade a row that touches goal noun, constraint cue (言語名, 絶対, 消さない), or priority cue (二の次, なるべく).

**Gate condition (Human Decisions Closed):**

```text
requirement_resolution_phase == REQUIREMENTS_RESOLVED
AND no row with resolution_status=unresolved AND decision_owner=human
AND no row with disposition in {GOAL, CONSTRAINT, AMBIGUOUS_REQUIREMENT} and provenance=llm_proposed only
```

**Enforcement point:** After `decompose_requirements` / extraction, **before** `ChatTaskOrchestrator.initialize()` and **before** `_chat_turn` for implementation-class missions.

**Existing hook:** `requirement.status != READY` already blocks orchestrator (~3829); **extend** so free-text extraction returns non-READY when unresolved human rows exist (today free text is always READY with zero conditions).

```text
HUMAN_DECISION_GATE (target): ENFORCED for implementation-class agent tasks
HUMAN_DECISION_GATE (today): PARTIAL
```

---

## AI_DESIGN_BOUNDARY

**Human Requirement Zone (closed before):**

- What to build, for whom, hard constraints, prohibitions, priorities, ambiguous scope resolved.

**AI Design Zone (open after gate):**

- Architecture, modules, algorithms, class decomposition, detailed test design, file layout — unless user explicitly fixed them in resolved **CONSTRAINT** rows.

**Mechanism:**

- `orchestrator.initialize()` / task graph expansion / `run_test_plan` / write tools require `REQUIREMENTS_RESOLVED`.
- LLM system hints: inject **Resolved Structured Requirements** block; forbid contradicting `explicit_constraints` and resolved `GOAL` rows.
- **Handoff path:** `goal_handoff.status=ready` + `human_gates` remain parallel gate for Dev Skill; NL path should **converge** on same phase flag before implementation.

**Today:** Design and implementation proceed under default observation task — **gap to close**.

---

## AGENT_TASK_ROUTING

### Current behavior (confirmed)

- `classify_request`: `development` if `実装して|開発して|テストして|…`; bare `作って` → **`chat`**.
- `is_agent_task`: `_AGENT_TASK` includes 実装/テスト/…; **not** `作って` / bare “build”.

### Cases

| Utterance | `classify_request` | `is_agent_task` (typical) |
|-----------|-------------------|---------------------------|
| テトリスを作って | chat | **false** (unless registry keyword match) |
| 簡単なテトリスを作って | chat | **false** / indeterminate |
| Pythonで小さなツールを作って | chat or tool_creation if 「ツールを作」 | tool_creation if matched |

### Recommended approach (no implementation)

**Combination (most natural to existing architecture):**

1. **Regex wedge** on `is_agent_task`: add Japanese/English **creation intent** (`作って|作る|作成|build|create( a)?|implement` as secondary pattern) with **negative boundary** `_GENERAL_KNOWLEDGE_REQUEST` retained.
2. **Keep** `classify_request` separate; optionally add `作って` to a **non–spec-proposal** chat branch only (avoid stealing `development` spec path).
3. **Registry keywords** (already in `is_agent_task`): document product keywords (e.g. game names) via `agent_visible_tools[].keywords` — data-driven, not hardcoded Tetris.
4. **Defer** full semantic classifier to Phase 2; require **resolution gate** even when routing is wrong so mis-routed chat does not implement silently.

**Semantic classifier:** Not first wedge; regex + keywords + mandatory pre-turn requirement phase.

---

## GRILL_REUSE

| Step | Existing | Extension |
|------|----------|-----------|
| Question generation | `build_boundary_grill_contract`, Conversation Grill, `requirement.clarification` string | New `grill_reason=requirement_resolution` using `GrillQuestionContract`; one question per **material** unresolved row or batched by dimension |
| Human capture | `awaiting_boundary_grill`, `awaiting_human_grill`, goal completion flags | Add `awaiting_requirement_resolution` (or reuse boundary grill with dimension=`requirements`) |
| Contract update | `apply_boundary_grill_answer`, `apply_human_grill_answer`, mission supplements | Map answers → update `structured_requirements` rows + `provenance=human_confirmed` |
| Gate re-eval | `reroute_after_boundary_grill_answer` | `reevaluate_requirement_resolution_phase()` |

**Materiality:** Reuse `request_has_material_spec_fork` **pattern** (regex for forks), not scope — add **requirement-level** materiality from records.

---

## RESUME_PATH

```text
Session flags (awaiting_*_grill)
  → user answer in run_chat_turn
  → apply_*_grill_answer / apply_requirement (development_session)
  → mission persist (supplements + structured_requirements)
  → restore_from_grill_resume / goal_continuation_resume
  → re-run requirement phase check
  → if REQUIREMENTS_RESOLVED → orchestrator.initialize / _chat_turn
```

**Reuse:** `goal_continuation_resume`, `restore_orchestrator_from_boundary_grill`, `chat_persist` mission write.

**Gap today:** No requirement-resolution resume because no `structured_requirements` phase — **NOT_CONNECTED** until wedge exists.

---

## SOURCE_OF_TRUTH

| Artifact | Role |
|----------|------|
| `mission.original_goal` | **Immutable evidence** of what the user typed |
| `mission.structured_requirements` (proposed) | **Executable human requirement contract** |
| `mission.explicit_constraints` / `explicit_conditions` | **Projections** of resolved hard requirements / numbered acceptance |
| `user_confirmed_supplements` / `confirmed_clarifications` | **Human decision audit trail** |
| `ChatTaskOrchestrator.request` | Runtime copy of original; must not diverge from `original_goal` |
| `TaskRecord.instruction` / `completion_conditions` | **AI Design execution**; must trace to resolved requirements |
| `goal_handoff` document | Optional **design package**; `status=ready` when Dev Skill path |
| LLM chat messages | **Non-canonical** interpretation |

**Drift rule:** Task Runtime must not satisfy completion using conditions that **cannot** be traced to `structured_requirements` or explicit numbered user list.

**Synchronization:** On persist, mission is authoritative; orchestrator reloads from mission on resume.

---

## REPRESENTATIVE_CASE_RESULTS

Static architecture walkthrough (no LLM execution). Assumes: extraction runs, gate enforced, routing fixed for build intent.

| Case | Expected disposition | Resolution | Survives to contract | Gate |
|------|---------------------|------------|----------------------|------|
| **1** 簡単なテトリスを作って | `GOAL`: テトリスを作る; `AMBIGUOUS`: 簡単な | Human grill on「簡単な」 | Both `source_text` preserved; 簡単な unresolved until answered | **Blocks** design until 簡単な resolved |
| **2** Pythonでテトリスを作って | `CONSTRAINT`: Pythonで | Auto-resolved if explicit | → `explicit_constraints` | **Open** if only constraint+goal clear |
| **3** 赤いボタンは絶対に消さないで | `CONSTRAINT` + `constraint_subtype=PROHIBITION` | User explicit | → `explicit_constraints` + design hints | **Open** if clear (typically `blocks_design` if acceptance depends on UI) |
| **4** 見た目は二の次でいい | `PREFERENCE`, `materiality=informational` (HD-2) | User explicit; not numericized | Preference row retained | **Open** — Design not blocked unless upgraded to `blocks_design` |
| **5** なるべく軽くして | `AMBIGUOUS_REQUIREMENT` or `PREFERENCE` | Human or explicit tradeoff question | **No silent number**; store qualitative until human confirms metric | **Blocks** if materiality=blocks_design |
| **6** 初心者でも使えるように | `AMBIGUOUS_REQUIREMENT` | `USER_INTENT_UNKNOWN` → grill | usability definition human-confirmed | **Blocks** until resolved |

**Case 1 routing note:** Without `is_agent_task` fix, case may never enter orchestrator — routing wedge is **prerequisite** for end-to-end.

---

## NEW_SCHEMA_REQUIRED

```text
NEW_SCHEMA_REQUIRED: YES
```

**Minimum schema change:** `mission.schema.json` — `structured_requirements[]`, `requirement_resolution_phase` enum, optional row defs aligned with MINIMUM_REQUIREMENT_RECORD.

**Rejected (HD-4):** Orchestrator-only wedge without mission schema — not adopted.

Optional later: JSON Schema for requirement row (like `grill_question_contract.schema.json`).

---

## NEW_RUNTIME_STATE_REQUIRED

```text
NEW_RUNTIME_STATE_REQUIRED: YES
```

- **Adopted:** `requirement_resolution_phase` on mission (HD-4) + mirrored on orchestrator (`REQUIREMENTS_RESOLVED` | `AWAITING_HUMAN_REQUIREMENT` | `AWAITING_FACT_RESOLUTION` | `AWAITING_ENVIRONMENT_RESOLUTION`).

**ActivityStatus:** Could add `REQUIREMENT_RESOLUTION` — optional; not required if phase lives on mission.

---

## HUMAN_DECISIONS_REQUIRED

```text
STATUS: CLOSED (see ADOPTED_HUMAN_DECISIONS)
```

---

## MINIMUM_IMPLEMENTATION_WEDGE

Ordered, smallest path to **ENFORCED** gate for one class of requests:

1. **Routing:** Extend `is_agent_task` for creation-intent regex (AGENT_TASK_ROUTING).
2. **Schema + persist:** `structured_requirements` + `requirement_resolution_phase` on mission; write on first agent-task turn.
3. **Extraction (HD-1):** Span-first segmentation → per-span LLM proposal → validator (`source_text` = span, coverage of `original_goal`, `validate_conditions`, no silent drop).
4. **Gate (HD-3):** In `run_chat_turn`, any **implementation-entry** path with phase ≠ `REQUIREMENTS_RESOLVED` must **not** call `_chat_turn` / mutating tools; emit grill/clarification via `GrillQuestionContract` or `requirement.clarification` (route label irrelevant).
5. **Human loop:** On answer, update rows → supplements → re-eval phase → then `ChatTaskOrchestrator` + `initialize`.
6. **AI Design:** Project resolved `GOAL`/`CONSTRAINT` (incl. `constraint_subtype=PROHIBITION`) into `completion_conditions` / `explicit_constraints`; block tool writes until step 5 passes; honor HD-2 for informational `PREFERENCE`.

**Out of wedge v0:** Full handoff auto-generation, semantic `classify_request` overhaul, universal materiality LLM.

---

## IMPLEMENTATION_READY

```text
IMPLEMENTATION_READY: true
```

Scope: **minimum implementation wedge** (§ MINIMUM_IMPLEMENTATION_WEDGE) per closed HD-1…HD-5. Full Human Requirement Resolution system across all routes and handoff parity remains **PARTIAL** until wedge lands and is verified.

This revision does not include code changes.

---

## Output index (requested fields)

| Field | Value |
|-------|-------|
| CURRENT_REUSABLE_COMPONENTS | § above |
| PROPOSED_MINIMUM_ARCHITECTURE | § above |
| REQUIREMENT_CONTRACT_LOCATION | Mission + orchestrator mirror; no `GoalContract` type |
| MINIMUM_REQUIREMENT_RECORD | § table |
| CLASSIFICATION_MODEL | Disposition enum; no deletion from original |
| UNKNOWN_RESOLUTION_MODEL | intent / fact / env → grill / research / precondition |
| HUMAN_DECISION_GATE | Pre-initialize; materiality rules |
| AI_DESIGN_BOUNDARY | Post `REQUIREMENTS_RESOLVED` |
| AGENT_TASK_ROUTING | Regex + registry keywords; defer semantic |
| GRILL_REUSE | `GrillQuestionContract` + supplements |
| RESUME_PATH | Existing grill resume + new phase re-eval |
| SOURCE_OF_TRUTH | `original_goal` + `structured_requirements` |
| REPRESENTATIVE_CASE_RESULTS | § table |
| NEW_SCHEMA_REQUIRED | **YES** |
| NEW_RUNTIME_STATE_REQUIRED | **YES** (phase enum; partial reuse possible) |
| HUMAN_DECISIONS_REQUIRED | **CLOSED** (ADOPTED_HUMAN_DECISIONS) |
| MINIMUM_IMPLEMENTATION_WEDGE | 6 steps |
| IMPLEMENTATION_READY | **true** (wedge scope only) |
