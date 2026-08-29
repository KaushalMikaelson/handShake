"""Audit trail read models (US-9)."""
from datetime import datetime

from pydantic import BaseModel, Field


class AuditEventOut(BaseModel):
    event_id: str
    sequence: int
    timestamp: datetime
    agent_id: str
    action: str
    purchase_intent_id: str | None = None
    input_reference: dict | None = None
    output_reference: dict | None = None
    reason: str
    policy_result: dict | None = None
    status: str


class AuditTimelineOut(BaseModel):
    purchase_intent_id: str
    event_count: int
    events: list[AuditEventOut] = Field(default_factory=list)
