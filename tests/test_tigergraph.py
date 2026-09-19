import json

import httpx
import pytest

from graphsentinel.models import CaseRecord, Evidence
from graphsentinel.tigergraph import TigerGraphError, TigerGraphGraph


def vertex(kind, identifier, **attributes):
    return {"v_type": kind, "v_id": identifier, "attributes": attributes}


def test_installed_query_parses_graph_traversal_and_case_memory():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer secret"
        body = json.loads(request.content)
        if request.url.path.endswith("gs_transaction_neighborhood"):
            assert body == {"tx": "T100", "max_results": 10}
            return httpx.Response(200, json={"error": False, "results": [{
                "transaction": [vertex("Transaction", "T100", account_id="A1", customer_id="C1", device_id="D1", merchant_id="M1", occurred_at="2026-09-19T10:31:00Z", amount=920, currency="USD", model_score=0.58)],
                "account_history": [vertex("Transaction", "T102", account_id="A1", customer_id="C1", device_id="D0", merchant_id="M2", occurred_at="2026-09-18T12:00:00Z", amount=42, currency="USD", model_score=0.04)],
                "device_peers": [vertex("Transaction", "T101", account_id="A2", customer_id="C2", device_id="D1", merchant_id="M1", occurred_at="2026-09-19T10:24:00Z", amount=870, currency="USD", model_score=0.81)]
            }]})
        assert body["max_results"] == 10
        return httpx.Response(200, json={"error": False, "results": [{"cases": [
            vertex("FraudCase", "HIST-1", entity_ids_json='["D1","A2"]', pattern="shared_device_cluster", outcome="confirmed_fraud", action="BLOCK_CARD", summary="Customer denial")
        ]}]})

    graph = TigerGraphGraph("http://tg", "GraphSentinel", "secret", client=httpx.Client(transport=httpx.MockTransport(handler)))
    context = graph.neighborhood("T100", limit=10)
    assert context.transaction.id == "T100"
    assert context.device_peers[0].account_id == "A2"
    assert context.account_history[0].amount == 42
    assert graph.prior_cases("A1", "D1")[0].id == "HIST-1"
    assert len(calls) == 3


def test_case_writeback_creates_case_evidence_and_relationships():
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        assert request.url.path == "/graph/GraphSentinel"
        return httpx.Response(200, json={"error": False, "results": [{"accepted_vertices": 2, "accepted_edges": 4}]})

    graph = TigerGraphGraph("http://tg", "GraphSentinel", "secret", client=httpx.Client(transport=httpx.MockTransport(handler)))
    case = CaseRecord(id="CASE-1", transaction_id="T100", trigger="risk_model", status="CLOSED", outcome="confirmed_fraud", graph={"nodes": [{"id": "A1", "type": "Account"}, {"id": "D1", "type": "Device"}]}, evidence=[Evidence(id="E-001", kind="shared_device", claim="Linked accounts", entity_ids=["D1", "A1"], source="TigerGraph", strength=0.8)])
    graph.save_case(case)
    body = payloads[0]
    assert "CASE-1" in body["vertices"]["FraudCase"]
    assert "CASE-1:E-001" in body["vertices"]["Evidence"]
    assert "CASE_EVIDENCE" in body["edges"]["FraudCase"]["CASE-1"]
    assert "CASE_DEVICE" in body["edges"]["FraudCase"]["CASE-1"]


def test_graph_error_and_query_allowlist():
    def handler(request):
        return httpx.Response(200, json={"error": True, "message": "query not installed", "results": []})

    graph = TigerGraphGraph("http://tg", "GraphSentinel", "secret", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError):
        graph.run_query("DELETE_ALL", {})
    with pytest.raises(TigerGraphError, match="query not installed"):
        graph.neighborhood("T100")
