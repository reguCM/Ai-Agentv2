"""Experimental conversation resolution package."""
from ai_tool.experimental.conversation_resolution.candidate_builder import (
    build_candidates_from_sources,
    build_envelope,
    classify_candidate_relation,
    choose_presentation_mode,
)
from ai_tool.experimental.conversation_resolution.models import (
    Candidate,
    ConversationState,
    UserFacingPresentation,
)
from ai_tool.experimental.conversation_resolution.presenter import (
    build_presentation,
    format_source_navigation,
)
from ai_tool.experimental.conversation_resolution.resolver import (
    handle_follow_up,
    initialize_conversation,
    parse_follow_up_intent,
    resolve_initial_turn,
)

__all__ = [
    "Candidate",
    "ConversationState",
    "UserFacingPresentation",
    "build_candidates_from_sources",
    "build_envelope",
    "build_presentation",
    "classify_candidate_relation",
    "choose_presentation_mode",
    "format_source_navigation",
    "handle_follow_up",
    "initialize_conversation",
    "parse_follow_up_intent",
    "resolve_initial_turn",
]
