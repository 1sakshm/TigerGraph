from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from graphsentinel.graph import GraphPort
from graphsentinel.investigator import Investigator
from graphsentinel.models import CaseRecord, TraceEvent
from graphsentinel.policy import PolicyEngine
from graphsentinel.store import CaseStore
from graphsentinel.tigergraph import TigerGraphError
from graphsentinel.synthesis import OpenAISummarizer
from graphsentinel.hhgoa.contracts import Answer


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


def create_app(graph: GraphPort, store: CaseStore, mode: str, summarizer: OpenAISummarizer | None = None) -> FastAPI:
    api = FastAPI(title="GraphSentinel", version="0.1.0")
    investigator = Investigator(graph, PolicyEngine(), summarizer=summarizer)

    @api.exception_handler(TigerGraphError)
    def graph_unavailable(_request, error: TigerGraphError):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"detail": str(error)})
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

    benchmark_dir = Path(__file__).parents[1] / "cases"

    @api.get("/api/benchmark")
    def benchmark_cases():
        summaries = []
        for path in sorted(benchmark_dir.glob("HHG-???.json")):
            answer = Answer.model_validate_json(path.read_text(encoding="utf-8"))
            summaries.append({
                "case_id": answer.case_id, "verdict": answer.case.verdict,
                "pattern": answer.case.pattern, "fraud_probability": answer.case.fraud_probability,
                "status": answer.case.status, "written_to_graph": answer.case.written_to_graph,
                "initial_action": answer.next_best_actions.initial[0].action,
                "final_action": answer.next_best_actions.final[0].action,
            })
        return summaries

    @api.get("/api/benchmark/{case_id}", response_model=Answer)
    def benchmark_case(case_id: str):
        if not re.fullmatch(r"HHG-\d{3}", case_id):
            raise HTTPException(400, "Invalid benchmark case ID")
        path = benchmark_dir / f"{case_id}.json"
        if not path.exists():
            raise HTTPException(404, "Benchmark answer not found")
        return Answer.model_validate_json(path.read_text(encoding="utf-8"))

    @api.get("/api/benchmark/{case_id}/trace")
    def benchmark_trace(case_id: str):
        if not re.fullmatch(r"HHG-\d{3}", case_id):
            raise HTTPException(400, "Invalid benchmark case ID")
        path = benchmark_dir / "investigations" / f"{case_id}.json"
        if not path.exists():
            raise HTTPException(404, "Benchmark trace not found")
        import json
        return json.loads(path.read_text(encoding="utf-8"))

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
    api.mount("/static", StaticFiles(directory=ui.parent), name="static")

    @api.get("/", include_in_schema=False)
    def index():
        return FileResponse(ui)

    @api.get("/benchmark", include_in_schema=False)
    def benchmark_page():
        return FileResponse(ui.parent / "benchmark.html")

    return api
