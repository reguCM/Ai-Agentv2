# Human Requirement Preservation Audit (READ-ONLY)

**Date:** 2026-09-12  
**HEAD:** `dev/current` (post S9 `47b11df`)  
**Scope:** Natural-language Chat → Task Runtime; no code changes.

**Terminology:** Repository has **no type named `GoalContract`**. This audit treats **de facto goal contract** as the combined authority of:

1. `ChatTaskOrchestrator.request` + task/goal graph (`AgentTaskRuntime`)
2. `mission_memory` Mission `original_goal` / `explicit_conditions` / supplements
3. Optional `goal_handoff.schema.json` packet (Dev Skill / production handoff path)

---

## USER_REQUEST_ENTRY

| Step | Location | Evidence |
|------|----------|----------|
| HTTP/UI | `ai_tool/chat_interface/server.py` → `run_chat_turn(session, user_text, …)` | User text as `user_text` |
| Normalize | `text = str(user_text or "").strip()` | Leading/trailing whitespace only |
| Session | `append_session_message`, `session["last_original_request"]` when runtime snapshot restored | `agent_turn.py` ~2952, 2780–2794 |
| Route | `classify_request(text)` — regex only, no LLM | `classify.py` |
| Agent task gate | `is_agent_task(text, …)` — regex + registry keywords | `task_orchestration.py` `is_agent_task` |
| Orchestrator ctor | `ChatTaskOrchestrator(correlation_id, text, completion_conditions=adopted, …)` | `agent_turn.py` ~3811–3818 |
| Agent loop | `_chat_turn` → `messages.append({"role":"user","content": user_text})` | Full turn text to LLM each round |
| Mission | `persist_chat_execution` → `original_goal: orchestrator.request` (immutable) | `chat_persist.py`, `mission.schema.json` |

**Not on main path:** `decompose_requirements()` **does not call the LLM** on HEAD for free-form text (see INTERPRETATION_PATH).

---

## ORIGINAL_REQUEST_PRESERVATION

| Store | Field | Content |
|-------|-------|---------|
| Orchestrator | `self.request` | Full stripped user text for the turn that created the orchestrator |
| Snapshot | `original_request` | Same as `self.request` | `task_orchestration.snapshot()` |
| Mission (on persist) | `original_goal` | Copy of `orchestrator.request`; **overwrite forbidden** | `store.py` |
| Session | `last_original_request` | From snapshot / handoff resume packets |
| Grill states | `original_request` | Preserved in `conversation_grill_state`, `boundary_grill_state`, etc. |
| Goal handoff packet | `goal.summary`, optional `goal.original_request_excerpt` | **Not** automatically `orchestrator.request`; handoff is separate artifact |

**Trace Goal handoff → user verbatim:** Only if `original_request_excerpt` was populated at packet authoring time; **not wired** into `seed_orchestrator_from_handoff` (orchestrator keeps ctor `text`, handoff replaces **graph** only).

```text
ORIGINAL_REQUEST_PRESERVATION: PARTIAL
```

- **FULL** for active Chat orchestrator + Mission `original_goal` (single string, whole utterance).
- **Not** phrase-level or constraint-level provenance inside that string.

---

## INTERPRETATION_PATH

```text
User message
  → classify_request (regex route)
  → [optional] decompose_requirements
  → [optional] detect_unknown_concept
  → ChatTaskOrchestrator.initialize() OR handoff seed
  → _chat_turn (LLM + tools)
```

### `decompose_requirements` (HEAD behavior)

```python
# requirement_decomposition.py
explicit = explicit_conditions(request)  # numbered list only
if explicit:
    return validate_conditions(..., source="explicit")
return RequirementDecomposition([], READY, source="not_enumerated")
```

- **LLM prompt `_SYSTEM` exists** but is **not invoked** by `decompose_requirements` on current HEAD.
- Free-form requests → `READY` with **zero** adopted completion conditions.
- Numbered-list requests → mechanical parse + `validate_conditions` (regex validators, no LLM).

### Routes that bypass Task Runtime

| Route | Handler | LLM role |
|-------|---------|----------|
| `development` | `_spec_proposal_turn` → `propose_specification` | Spec proposal generation |
| `tool_creation` | same | Tool spec proposal |
| `help` | `_help_h_turn` | Help system |

### Agent loop prompts

- `SYSTEM_PROMPT` + `AGENT_CORE_PROMPT` (`agent_turn.py`, `task_orchestration.py`)
- Instructs: use tools for facts, completion conditions drive progress — **no** “delete unimportant user words” instruction.
- `orchestrator.hint()` injects task title, instruction (= request on T1), evidence summaries, failure codes.

---

## LLM_DECISION_POINTS

| Stage | INPUT | LLM_DECISION | OUTPUT | VALIDATOR | HUMAN_CHECK |
|-------|-------|--------------|--------|-----------|-------------|
| Requirement decompose (unused LLM path) | N/C on HEAD | N/C | N/C | `validate_conditions` if explicit list | Clarification turn if status ≠ READY |
| `classify_request` | text | **No** | route enum | Regex | No |
| `is_agent_task` | text | **No** | bool | Regex/keywords | No |
| `_chat_turn` tool loop | messages + tools | Tool choice, edits, answers | tool calls / final answer | Tool gate, relevance audit, loops | Grill / boundary / goal completion gates (conditional) |
| `propose_specification` | user text | Spec content | proposal JSON | parse_status / human_confirmation_required | `awaiting_human_review` |
| Production handoff pipeline | orchestrator + LLM | Task plan / handoff fields | `goal_handoff` packet | `validate_handoff_packet` | `human_gates`, readiness blockers |

**Direct LLM → “goal contract” without validator:** Agent loop can act on LLM interpretation of `user_text` in messages **without** mapping each phrase to structured requirements (no per-phrase contract).

---

## NON_LLM_TRANSFORMS

| Kind | Example | Effect |
|------|---------|--------|
| **LOSS_BY_SCHEMA** | `goal_handoff.schema.json` `additionalProperties: false` | Fields not in schema cannot be stored in packet |
| **LOSS_BY_PARSER** | `explicit_conditions` / `_explicit_completion_conditions` only numbered lines | Prose constraints not in `1.` list → not adopted as completion conditions |
| **LOSS_BY_RUNTIME** | `filter_definition_first_conditions` | Defers speculative conditions when concept unresolved |
| **LOSS_BY_RUNTIME** | Default T1 conditions `["relevant evidence observed"]` when none enumerated | User specifics not in numbered list are not completion conditions |
| **LOSS_BY_LLM** | Active: entire agent reasoning | Not mechanically logged as dropped requirements |

---

## GOAL_CONTRACT_FIELDS (de facto)

### `ChatTaskOrchestrator` / `AgentTaskRuntime`

- `request` (string)
- `TaskRecord`: `title`, `instruction`, `completion_conditions`, `satisfied_conditions`, `condition_status`, `evidence_ids`, …
- `GoalNode`: `title`, `completion_conditions`, …
- `user_explicit_conditions` (list, from numbered decomposition only on create)
- `concept_resolution`, `capability_resolutions`, `confirmed_clarifications`, grill-related state
- **No** `constraints`, `preferences`, `unknowns`, `prohibited_actions` first-class fields on orchestrator

### `RequirementDecomposition` (turn JSON, optional)

- `conditions[]`: `description`, `ambiguity`, `source_hint`, `original_description` (on normalize path), `source` (`explicit` | `not_enumerated` | …)

### Mission `mission.schema.json`

- `original_goal`, `explicit_conditions[]`, `explicit_constraints[]` (must be `[]` if none — **LLM-invented constraints must not be stored** per schema description)
- `user_confirmed_supplements[]` with `source` enum: `grill` | `goal_completion` | `boundary_grill`

### `goal_handoff.schema.json`

- `goal.summary`, `goal.original_request_excerpt` (optional)
- `scope.in_scope`, `scope.non_goals`, `acceptance_criteria[]`, `implementation_tasks[]`, `open_questions[]`, `human_gates[]`, `test_plan`, …

---

## REQUIREMENT_PROVENANCE

| Mechanism | Supports |
|-----------|----------|
| Mission `user_confirmed_supplements[].source` | Human-confirmed text from named grill sources only |
| `RequirementCondition.source` / `source_hint_certainty` | `explicit` vs `not_enumerated`; certainty default `UNVERIFIED` |
| `original_description` on normalized conditions | Partial trace when action-shaped rows rewritten |
| Task `completion_conditions` | **No** per-condition provenance (USER vs LLM) |

```text
REQUIREMENT_PROVENANCE: PARTIAL
```

---

## AMBIGUITY_HANDLING

| Mechanism | Detects | Notes |
|-----------|---------|-------|
| `validate_conditions` + `_VAGUE` | 適切に, いい感じ, … | **Not** `簡単な` |
| `validate_conditions` + `ambiguity` field | If LLM path used (inactive on HEAD for free text) | — |
| `RequirementStatus` ≠ READY | Blocks orchestrator creation | Rare for free text (`not_enumerated` → READY) |
| `goal_needs_human_grill` | Unresolved **file/path identity** in search | Not general vague adjectives |
| `needs_boundary_spec_clarification` | Material spec fork in **request text** (regex) | After T1 observation complete; needs `acceptance` dimension |
| `open_questions` on handoff packet | Stored if author fills | Not NL Chat auto-fill |

No first-class **User Intent Unknown / Fact Unknown / Environment Unknown** taxonomy in Chat Runtime.

---

## HUMAN_FEEDBACK_PATH

| Stage | Status |
|-------|--------|
| **QUESTION_GENERATION** | Conversation Grill (`build_conversation_grill`), Boundary Grill (`GrillQuestionContract`), Goal Completion Gate, requirement `clarification` string |
| **HUMAN_RESPONSE_CAPTURE** | `awaiting_human_grill`, `awaiting_boundary_grill`, `awaiting_goal_completion_human`, grill answer in `run_chat_turn` |
| **CONTRACT_UPDATE** | `apply_human_grill_answer`, `apply_boundary_grill_answer`, mission supplements, `user_explicit_conditions` on boundary restore |
| **RESUME** | `restore_from_grill_resume`, `_boundary_grill_resume_turn`, goal continuation packets |

**NOT_CONNECTED** for: automatic ambiguity on arbitrary vague adjectives before agent loop.

---

## HUMAN_REQUIREMENT_GATE

| Gate | When | Effect |
|------|------|--------|
| `requirement.status != READY` | Numbered-list validation fails | No orchestrator; clarification answer |
| Boundary / conversation / goal completion | Session flags | Pause agent loop; await user |
| Production handoff readiness | Explicit handoff trigger | Block packet if blockers |
| Default free-text chat + `is_agent_task` | — | **Orchestrator starts** with default observation gate |

```text
HUMAN_REQUIREMENT_GATE: PARTIAL
```

Task decomposition / tool execution / implementation **can proceed** without resolved human decisions for most free-form requests.

---

## DIRECT_GOAL_PATH

| Path | Status |
|------|--------|
| Cursor `/goal` + `CreateGoal` | **`NOT_FOUND` in repository** (IDE command only) |
| `run_chat_turn(..., handoff_packet=…)` | Structured seed via `seed_orchestrator_from_handoff` |
| Production handoff / Dev Skill pipeline | LLM-built `goal_handoff` JSON + schema validation |
| `session["production_handoff_plan_tasks"]` | Planned tasks for handoff generation |

Natural language vs direct handoff: **different** requirement richness; handoff carries acceptance/tasks; NL path often only `original_goal` string + default conditions.

```text
DIRECT_GOAL_PATH: PARTIAL (handoff / pipeline only; no /goal in repo)
```

---

## REQUIREMENT_SOURCE_OF_TRUTH

| Layer | Authority | Drift risk |
|-------|-----------|------------|
| `Mission.original_goal` | Immutable user text (mission store) | vs later LLM answers |
| `orchestrator.request` | Same string at execution time | Handoff seed does not replace `request` |
| `TaskRecord.instruction` | Initially `request`; handoff tasks use composed `_task_instruction` | Handoff path diverges from NL utterance |
| `completion_conditions` | Numbered explicit only, or handoff acceptance, or defaults | **Most NL detail not here** |
| LLM chat messages | Ephemeral interpretation each turn | Not canonical store |
| `goal_handoff` document | Design-time contract when used | Optional; PROVISIONAL schema |

**Practical SoT for “what did the user ask”:** `original_goal` / `orchestrator.request` (whole string). **Not** for “what must be satisfied” unless enumerated or handoff-authored.

---

## CONFIRMED_INFORMATION_LOSS_POINTS

| Stage | Input | Transform | LLM? | Retained | Potentially lost | Human check | Evidence |
|-------|-------|-----------|------|----------|------------------|-------------|----------|
| A | Raw user text | `strip()` | No | `user_text` | Edge whitespace | No | `run_chat_turn` |
| B | User text | `classify_request` | No | Route label | Nuance in route bucket | No | `classify.py` |
| C | User text | `is_agent_task` false | No | — | **No Task Runtime at all** | No | `agent_turn` ~3781 |
| D | User text | `decompose_requirements` | **No** (HEAD) | `[]` conditions READY | All non-numbered requirements as **completion conditions** | Only if explicit list invalid | `requirement_decomposition.py` |
| E | Adopted conditions | `ChatTaskOrchestrator(..., completion_conditions=adopted)` | No | Only numbered items | Prose in `request` not in conditions | No | `agent_turn` |
| F | Request | `initialize()` default | No | `relevant evidence observed` | Explicit user criteria | No | `task_orchestration.initialize` |
| G | User text | LLM agent loop | Yes | Tool results + answer | Unstated constraints LLM ignores | Partial (grills) | `_chat_turn` |
| H | User text | `development` route | Yes | Spec proposal | Direct agent task path skipped | `awaiting_human_review` | `_spec_proposal_turn` |
| I | Handoff | `goal.summary` | Often LLM-authored | Summary paragraph | Full utterance unless `original_request_excerpt` | `human_gates` / status `ready` | `goal_handoff.schema.json` |

---

## "SIMPLE_TETRIS" STATIC TRACE

Input: `簡単なテトリスを作って`

| Fragment | Static trace |
|----------|----------------|
| Whole sentence | `orchestrator.request` / `mission.original_goal` if `is_agent_task` true and orchestrator created |
| `テトリスを作る` | In `request` string; **not** automatically a `completion_condition` (no numbered list) |
| `簡単な` | Remains inside `request` string only; **not** matched by `_VAGUE` regex; **no** dedicated field |

**`is_agent_task`:** `_AGENT_TASK` regex includes 実装/テスト/… but **not** bare `作って`. May be **false** → **no orchestrator** → only generic `_chat_turn` without task runtime.

**`classify_request`:** Default `chat` unless `実装して` etc. matches `development`.

```text
STATIC_TRACE_INDETERMINATE
```

for whether this utterance enters Task Runtime at all; **if it does**, full string preserved, **semantic decomposition not performed** by non-LLM stages.

---

## Confirmed Fact

- Entry: `run_chat_turn` → optional orchestrator → `_chat_turn`.
- Whole-user-text preservation on orchestrator + mission `original_goal`.
- Numbered-list-only mechanical adoption into `completion_conditions` / `explicit_conditions`.
- Free-form requests: `decompose_requirements` returns READY with zero conditions without LLM.
- Multiple human-feedback loops exist but are **narrowly triggered** (grill identity, boundary fork, goal completion, requirement validation failures on lists).
- No `GoalContract` type; handoff packet is closest structured contract artifact.
- `/goal` CreateGoal **not in repo**.

## Confirmed Gap

- No phrase-level requirement provenance in Task Runtime.
- NL constraints/preferences/prohibitions not captured unless numbered, handoff-authored, or human supplement.
- Agent loop can implement/decompose without closing ambiguous requirements.
- `recovery_hint` / default observation task not aligned with “build X” product goals (separate from this audit’s S10 note).
- `development` route diverts to spec proposal, not orchestrated implementation contract.

## Design Candidate (not current spec)

- Wire or remove dead LLM branch in `decompose_requirements`.
- Provenance tags on completion conditions.
- Pre-execution gate linking vague terms to Human / Grill.
- Mandatory `original_request_excerpt` + bind handoff to mission.

---

## EXISTING_COMPONENTS_REUSABLE

- `original_goal` immutability + supplements with `source` enum
- `RequirementDecomposition` + `validate_conditions` (for numbered input)
- Boundary / Conversation Grill + Goal Completion resume
- `goal_handoff` schema + validation + `open_questions` / `human_gates`
- `orchestrator.snapshot()` for audit trail

---

## MINIMUM_NEXT_WEDGE (audit recommendation only)

1. Document/deide: either **enable** LLM decomposition for free text or **explicitly** state NL contracts are `original_goal` + default observation only.
2. Extend `is_agent_task` or route rules so “作って”-class build requests consistently enter orchestrator (if product intent).
3. Narrow **HUMAN_REQUIREMENT_GATE** for implementation-class requests without enumerating acceptance (product decision).

---

## IMPLEMENTATION_READY

**false** for a complete Human Requirement Preservation system. **true** only for auditing current behavior.

---

## Final questions (Q1–Q5)

### Q1 — 語句が GoalContract まで原文または provenance で保持されるか

**PARTIAL.** 全文は `request` / `original_goal` に保持。語句単位の provenance や GoalContract フィールドへの分解は **未接続**（番号リスト・handoff・human supplement 以外）。

### Q2 — LLM が「重要でない」Requirement を黙って捨てられる構造か

**YES（Agent loop path）。** 構造化必須フィールドが無いため、LLM は messages 上の user 文を解釈しつつ、契約オブジェクトへ全語句を写す義務がない。番号リスト経路は mechanical parse が条件を写す。

### Q3 — 「簡単な」等の曖昧 Requirement を検出できるか

**STATIC_TRACE_INDETERMINATE / 実質 NO** for active NL path. `_VAGUE` は「簡単な」を含まない。Boundary grill は material spec **fork** 用。Free text は `not_enumerated` READY。

### Q4 — 人間へ返し、回答まで設計・分解を止めるか

**PARTIAL.** 番号リスト validation 失敗・特定 grill 状態・spec proposal review は停止。通常の自由文 + agent task では **停止せず** tool loop 可能。

### Q5 — Human Requirement 確定後のみ AI Design へ進むか

**NO** for default Chat. **PARTIAL** for handoff (`status: ready`, gates) and spec proposal `awaiting_human_review`. Implementation tools can run under default observation task without prior human closure.
