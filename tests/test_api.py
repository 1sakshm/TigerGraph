from pathlib import Path

from fastapi.testclient import TestClient

from graphsentinel.api import create_app
from graphsentinel.graph import FixtureGraph
from graphsentinel.store import CaseStore
from graphsentinel.tigergraph import TigerGraphError


def client(tmp_path):
    graph = FixtureGraph.from_file(Path(__file__).parents[1] / "data" / "demo.json")
    return TestClient(create_app(graph, CaseStore(tmp_path / "cases.sqlite"), mode="synthetic_demo"))


def test_api_preserves_before_and_after_recommendations(tmp_path):
    api = client(tmp_path)
    opened = api.post("/api/investigations", json={"transaction_id": "T100", "trigger": "risk_model"})
    assert opened.status_code == 201
    case_id = opened.json()["id"]
    assert opened.json()["recommendations"][0]["action"] == "REQUEST_CUSTOMER_CONFIRMATION"
    updated = api.post(f"/api/cases/{case_id}/evidence", json={"kind": "customer_confirmation", "value": "denied"})
    assert updated.status_code == 200
    assert [r["action"] for r in updated.json()["recommendations"]] == ["REQUEST_CUSTOMER_CONFIRMATION", "BLOCK_CARD"]
    assert updated.json()["actions_taken"] == []
    approved = api.post(f"/api/cases/{case_id}/decision", json={"decision": "approve", "analyst_id": "analyst-7"})
    assert approved.status_code == 200
    assert approved.json()["actions_taken"] == ["BLOCK_CARD"]
    assert api.get(f"/api/cases/{case_id}").json()["status"] == "ACTION_SIMULATED"


def test_missing_transaction_does_not_create_case(tmp_path):
    api = client(tmp_path)
    response = api.post("/api/investigations", json={"transaction_id": "MISSING", "trigger": "risk_model"})
    assert response.status_code == 404
    assert api.get("/api/cases").json() == []


def test_close_case_feeds_future_memory(tmp_path):
    api = client(tmp_path)
    case_id = api.post("/api/investigations", json={"transaction_id": "T100", "trigger": "risk_model"}).json()["id"]
    closed = api.post(f"/api/cases/{case_id}/close", json={"outcome": "confirmed_fraud", "analyst_feedback": "Customer denied charge"})
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
    future = api.post("/api/investigations", json={"transaction_id": "T101", "trigger": "analyst_request"}).json()
    assert case_id in {case["id"] for case in future["related_cases"]}


def test_unknown_case_and_unnamed_approval_are_rejected(tmp_path):
    api = client(tmp_path)
    assert api.get("/api/cases/UNKNOWN").status_code == 404
    case_id = api.post("/api/investigations", json={"transaction_id": "T100", "trigger": "risk_model"}).json()["id"]
    api.post(f"/api/cases/{case_id}/evidence", json={"kind": "customer_confirmation", "value": "denied"})
    bad = api.post(f"/api/cases/{case_id}/decision", json={"decision": "approve", "analyst_id": ""})
    assert bad.status_code == 403
    assert api.get(f"/api/cases/{case_id}").json()["actions_taken"] == []


def test_graph_outage_is_reported_as_service_unavailable(tmp_path):
    class OfflineGraph:
        def neighborhood(self, transaction_id, limit=50):
            raise TigerGraphError("connection unavailable")

        def save_case(self, case):
            pass

    api = TestClient(create_app(OfflineGraph(), CaseStore(tmp_path / "cases.sqlite"), mode="tigergraph"))
    response = api.post("/api/investigations", json={"transaction_id": "T100", "trigger": "risk_model"})
    assert response.status_code == 503
    assert "connection unavailable" in response.json()["detail"]
