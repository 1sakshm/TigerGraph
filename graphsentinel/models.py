from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    account_id: str
    customer_id: str | None = None
    device_id: str | None = None
    merchant_id: str | None = None
    occurred_at: datetime
    amount: float = Field(ge=0)
    currency: str = "USD"
    model_score: float | None = Field(default=None, ge=0, le=1)


class DevicePeer(BaseModel):
    transaction_id: str
    account_id: str
    customer_id: str | None = None
    device_id: str
    model_score: float | None = None


class PriorCase(BaseModel):
    id: str
    entity_ids: list[str]
    pattern: str
    outcome: str
    action: str
    summary: str
    similarity: float = Field(default=0.0, ge=0, le=1)


class Neighborhood(BaseModel):
    transaction: Transaction
    account_history: list[Transaction] = Field(default_factory=list)
    device_peers: list[DevicePeer] = Field(default_factory=list)
    related_cases: list[PriorCase] = Field(default_factory=list)


class Evidence(BaseModel):
    id: str
    kind: str
    claim: str
    entity_ids: list[str]
    source: str
    strength: float = Field(ge=0, le=1)


class TraceEvent(BaseModel):
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: str
    tool: str | None = None
    parameters: dict = Field(default_factory=dict)
    reason: str
    result: str
    latency_ms: float | None = None


class Recommendation(BaseModel):
    action: str
    reason: str
    evidence_ids: list[str]
    risk: float
    confidence: float
    policy_reference: str
    approval_required: bool
    status: Literal["proposed", "pending_approval", "executed", "rejected"] = "proposed"


class CaseRecord(BaseModel):
    id: str
    transaction_id: str
    trigger: str
    data_provenance: str = "UNSPECIFIED"
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence: list[Evidence] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    related_cases: list[PriorCase] = Field(default_factory=list)
    risk: float = 0.0
    confidence: float = 0.0
    hypotheses: dict[str, float] = Field(default_factory=dict)
    missing_evidence: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)
    outcome: str | None = None
    analyst_feedback: str | None = None
    reasoning_summary: str = ""
    stop_reason: str = ""
    graph: dict = Field(default_factory=dict)
