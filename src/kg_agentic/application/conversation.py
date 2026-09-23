"""Conversation decisions that keep evidence retrieval optional and explicit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

ConversationAction = Literal["respond", "investigate", "navigate"]


@dataclass(frozen=True, slots=True)
class ConversationModelRequest:
    question: str
    history: tuple[dict[str, str], ...]
    selected_node_ids: tuple[str, ...] = ()
    as_of: str | None = None
    retrieval_allowed: bool = True


@dataclass(frozen=True, slots=True)
class ConversationDecision:
    action: ConversationAction
    message: str
    investigation_question: str | None = None
    navigation_target: str | None = None


ConversationModel = Callable[[ConversationModelRequest], ConversationDecision]
