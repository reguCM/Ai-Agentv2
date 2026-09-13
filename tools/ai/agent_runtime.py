"""Minimal runtime state tracking for the interactive Agent loop.

This is intentionally separate from ``TaskState``.  TaskState describes the
confirmed task; AgentRuntime describes what the process is doing right now.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Callable, Iterator


class AgentRuntimeState(str, Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    TOOL_CALL_REQUESTED = "TOOL_CALL_REQUESTED"
    TOOL_RUNNING = "TOOL_RUNNING"
    TOOL_SUCCESS = "TOOL_SUCCESS"
    TOOL_PARTIAL = "TOOL_PARTIAL"
    TOOL_FAILED = "TOOL_FAILED"
    OBSERVING = "OBSERVING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class AgentRuntime:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_state: AgentRuntimeState = AgentRuntimeState.IDLE
    current_tool: str | None = None
    tool_call_count: int = 0
    # The most recently observed error.  A later success does not clear it.
    last_error: str | None = None
    state_history: list[dict[str, Any]] = field(default_factory=list)
    logger: Callable[[str], None] | None = print
    event_sink: Callable[[dict[str, Any]], None] | None = None

    def __post_init__(self) -> None:
        if not self.state_history:
            self.state_history.append(self._history_entry(AgentRuntimeState.IDLE))

    def _history_entry(
        self,
        state: AgentRuntimeState,
        *,
        tool: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "state": state.value,
            "timestamp": _utc_now(),
            "tool": tool,
            "error": error,
        }

    def transition(
        self,
        state: AgentRuntimeState,
        *,
        tool: str | None = None,
        error: str | None = None,
    ) -> None:
        previous = self.current_state
        history_tool = tool
        if state is AgentRuntimeState.TOOL_RUNNING:
            self.tool_call_count += 1
            self.current_tool = tool
        elif state in (
            AgentRuntimeState.TOOL_SUCCESS,
            AgentRuntimeState.TOOL_PARTIAL,
            AgentRuntimeState.TOOL_FAILED,
            AgentRuntimeState.ERROR,
        ):
            history_tool = tool or self.current_tool
        else:
            # current_tool means currently executing, not most recently used.
            self.current_tool = None
        if error is not None:
            self.last_error = error
        self.current_state = state
        entry = self._history_entry(state, tool=history_tool, error=error)
        self.state_history.append(entry)
        if self.event_sink is not None:
            self.event_sink(dict(entry))
        if state in (
            AgentRuntimeState.TOOL_SUCCESS,
            AgentRuntimeState.TOOL_PARTIAL,
            AgentRuntimeState.TOOL_FAILED,
            AgentRuntimeState.ERROR,
        ):
            self.current_tool = None
        if self.logger is not None:
            self.logger(f"[AgentRuntime] {previous.value} -> {state.value}")

    @contextmanager
    def error_boundary(self) -> Iterator[None]:
        """Record an unexpected operation exception, then preserve it."""
        try:
            yield
        except Exception as exc:
            self.transition(
                AgentRuntimeState.ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "current_state": self.current_state.value,
            "current_tool": self.current_tool,
            "tool_call_count": self.tool_call_count,
            "last_error": self.last_error,
            "state_history": [dict(item) for item in self.state_history],
        }
