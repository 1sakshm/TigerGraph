"""Exact answer contract from the supplied HHGOA README."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ActionName = Literal[
    "ALLOW_TRANSACTION", "DECLINE_TRANSACTION", "MONITOR_CARD",
    "MONITOR_CONNECTED_CARDS", "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER",
    "STEP_UP_AUTH", "BLOCK_CARD", "BLOCK_ALL_CARDS", "GENERATE_REPORT",
    "CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceItem(StrictModel):
    claim: str = Field(min_length=1)
    source: Literal["graph", "document", "customer", "external"]
    ref: str = Field(min_length=1)
    entity_ids: list[str]


class CasePart(StrictModel):
    status: Literal["open", "closed_fraud", "closed_legitimate", "escalated"]
    verdict: Literal["fraud", "legitimate", "uncertain"]
    fraud_probability: float = Field(ge=0, le=1)
    pattern: Literal["card_testing", "card_not_present_fraud", "card_not_present_new_device",
                     "out_of_region_use", "account_takeover", "undocumented", "none"]
    pattern_description: str
    affected_txn_ids: list[str]
    first_suspicious_txn_id: str
    connected_card_ids: list[str]
    connected_device_profiles: list[str]
    exposure_usd: float = Field(ge=0)
    evidence: list[EvidenceItem]
    similar_prior_cases: list[str]
    summary: str = Field(min_length=1)
    written_to_graph: bool
    graph_case_id: str

    @model_validator(mode="after")
    def coherent(self):
        if self.pattern == "undocumented" and not self.pattern_description.strip():
            raise ValueError("Undocumented patterns require a description")
        if self.pattern != "undocumented" and self.pattern_description:
            raise ValueError("Only undocumented patterns have a description")
        if self.verdict == "legitimate" and (self.affected_txn_ids or self.exposure_usd):
            raise ValueError("Legitimate cases have no fraud exposure")
        if self.written_to_graph != bool(self.graph_case_id):
            raise ValueError("Graph case ID must reflect actual writeback")
        return self


class EvidenceRequest(StrictModel):
    type: Literal["customer_validation", "step_up_auth", "analyst_info"]
    asked_after_step: int = Field(ge=1)
    assumed_response: str = Field(min_length=1)


class Action(StrictModel):
    action: ActionName
    route: Literal["auto", "L1", "L2"]
    reason: str = Field(min_length=1)


class NextActions(StrictModel):
    initial: list[Action]
    final: list[Action]
    what_changed: str = Field(min_length=1)


class Sar(StrictModel):
    file: bool
    reason: str = Field(min_length=1)
    narrative: str
    subjects: list[str]
    total_amount_usd: float = Field(ge=0)
    activity_dates: list[str]

    @model_validator(mode="after")
    def coherent(self):
        if self.file:
            if not self.narrative or not self.subjects or len(self.activity_dates) != 2:
                raise ValueError("Filed report needs narrative, subjects and date range")
        elif self.narrative or self.subjects or self.total_amount_usd or self.activity_dates:
            raise ValueError("Unfiled report must have empty report fields")
        return self


class Answer(StrictModel):
    case_id: str = Field(pattern=r"^HHG-\d{3}$")
    case: CasePart
    evidence_requests: list[EvidenceRequest]
    next_best_actions: NextActions
    sar: Sar
    stop_reason: str = Field(min_length=1)
    tool_calls: int = Field(ge=0)
    tokens: int = Field(ge=0)
    latency_s: float = Field(ge=0)

    @model_validator(mode="after")
    def report_matches_actions(self):
        if self.sar.file != any(a.action == "FILE_REPORT" for a in self.next_best_actions.final):
            raise ValueError("SAR filing must agree with final actions")
        return self
