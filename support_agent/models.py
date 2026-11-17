"""Validated request bodies for the documented helpdesk action endpoints."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Language = Literal["nl", "en", "de"]
Category = Literal["bug", "billing", "feature_request", "question", "other"]
Priority = Literal["P1", "P2", "P3", "P4"]
Action = Literal["reply", "handoff", "close"]
EscalationIntent = Literal[
    "refund",
    "disputed_charge",
    "cancellation",
    "contract_change",
    "personal_data_request",
    "security_incident",
    "legal_threat",
    "threat_to_leave",
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Language | None
    category: Category
    priority: Priority
    reason: NonEmptyText
    is_spam: bool
    proposed_action: Action
    escalation_intents: list[EscalationIntent]


class FAQMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matched_faq_ids: list[NonEmptyText]
    fully_supported: bool
    confidence: Annotated[float, Field(ge=0, le=1)]


class ReplyVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: NonEmptyText


class DecisionMetadata(BaseModel):
    """Fields required by every action, plus optional confidence."""

    model_config = ConfigDict(extra="forbid")

    language: Language
    category: Category
    priority: Priority
    reason: NonEmptyText
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None


class ReplyRequest(DecisionMetadata):
    """Request body for POST /tickets/{id}/reply."""

    draft_reply: NonEmptyText


class HandoffRequest(DecisionMetadata):
    """Request body for POST /tickets/{id}/handoff."""

    handoff_note: NonEmptyText


class CloseRequest(DecisionMetadata):
    """Request body for POST /tickets/{id}/close."""
