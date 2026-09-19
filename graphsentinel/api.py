from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from graphsentinel.graph import GraphPort
from graphsentinel.investigator import Investigator
from graphsentinel.models import CaseRecord, TraceEvent
from graphsentinel.policy import PolicyEngine
from graphsentinel.store import CaseStore


class InvestigationRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=200)
    trigger: str = Field(default="analyst_request", min_length=1, max_length=100)


class EvidenceRequest(BaseModel):
    kind: str
    value: str


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    analyst_id: str


class CloseRequest(BaseModel):
    outcome: Literal["confirmed_fraud", "cleared", "inconclusive"]
    analyst_feedback: str = Field(default="", max_length=2000)


def create_app(graph: GraphPort, store: CaseStore, mode: str) -> FastAPI:
    api = FastAPI(title="GraphSentinel", version="0.1.0")
    investigator = Investigator(graph, PolicyEngine())
    for prior in store.list():
        if prior.outcome:
            graph.save_case(prior)

    def fetch(case_id: str) -> CaseRecord:
        case = store.get(case_id)
        if case is None:
            raise HTTPException(404, "Case not found")
        return case

    def persist(case: CaseRecord) -> CaseRecord:
        store.save(case)
        graph.save_case(case)
        return case

    @api.get("/api/health")
    def health():
        return {"status": "ok", "mode": mode, "graph_authoritative": mode == "tigergraph"}

    @api.post("/api/investigations", response_model=CaseRecord, status_code=201)
    def investigate(request: InvestigationRequest):
        try:
            return persist(investigator.investigate(request.transaction_id, request.trigger))
        except KeyError:
            raise HTTPException(404, "Transaction not found")
        except ValueError as error:
            raise HTTPException(400, str(error))

    @api.get("/api/cases", response_model=list[CaseRecord])
    def cases():
        return store.list()

    @api.get("/api/cases/{case_id}", response_model=CaseRecord)
    def case_detail(case_id: str):
        return fetch(case_id)

    @api.post("/api/cases/{case_id}/evidence", response_model=CaseRecord)
    def add_evidence(case_id: str, request: EvidenceRequest):
        case = fetch(case_id)
        if case.status == "CLOSED":
            raise HTTPException(409, "Closed case cannot accept evidence")
        try:
            return persist(investigator.add_evidence(case, request.kind, request.value))
        except ValueError as error:
            raise HTTPException(400, str(error))

    @api.post("/api/cases/{case_id}/decision", response_model=CaseRecord)
    def decide(case_id: str, request: DecisionRequest):
        case = fetch(case_id)
        if case.status == "CLOSED":
            raise HTTPException(409, "Closed case cannot accept decisions")
        try:
            return persist(investigator.decide(case, request.decision, request.analyst_id))
        except PermissionError as error:
            raise HTTPException(403, str(error))
        except ValueError as error:
            raise HTTPException(409, str(error))

    @api.post("/api/cases/{case_id}/close", response_model=CaseRecord)
    def close(case_id: str, request: CloseRequest):
        case = fetch(case_id)
        if case.status == "CLOSED":
            raise HTTPException(409, "Case already closed")
        case.status = "CLOSED"
        case.outcome = request.outcome
        case.analyst_feedback = request.analyst_feedback
        case.updated_at = datetime.now(timezone.utc)
        case.trace.append(TraceEvent(
            state="CASE_MEMORY_UPDATE", reason="Analyst resolved the investigation",
            result=f"Outcome {request.outcome} written to case memory",
        ))
        return persist(case)

    ui = Path(__file__).parents[1] / "frontend" / "index.html"

    @api.get("/", include_in_schema=False)
    def index():
        return FileResponse(ui)

    return api
