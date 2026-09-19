from pathlib import Path

import pytest

from graphsentinel.hhgoa.contracts import Answer
from graphsentinel.hhgoa.tigergraph import GraphPayload, HHGOATigerGraph, device_profile_id


def test_transaction_payload_uses_only_observed_relationships():
    tx = {
        "id": "3514030", "customer_id": "C12382", "ts": "2016-12-04 19:55:28",
        "amount": 77.07, "product": "W", "channel": "in_person", "risk": 0.61,
        "card1": "21139", "card2": "242.0", "card3": "150.0", "card4": "visa",
        "card5": "166.0", "card6": "debit", "addr1": "444.0", "addr2": "87.0",
        "email": None, "recipient_email": None,
    }
    payload = GraphPayload()
    payload.add_transaction(tx)
    body = payload.body()
    assert "3514030" in body["vertices"]["Transaction"]
    assert "C12382" in body["vertices"]["Customer"]
    assert "MADE" in body["edges"]["Customer"]["C12382"]
    assert "CARD_TX" not in str(body)
    assert "Merchant" not in str(body)


def test_identity_profile_is_stable_and_case_anchor_is_explicit():
    row = {"id": "3514030", "device_info": "Windows", "os": "Windows 10",
           "browser": "edge 16.0", "screen": "1366x768", "identity_status": "New",
           "proxy_status": None}
    assert device_profile_id(row) == device_profile_id(dict(row))
    payload = GraphPayload()
    payload.add_identity(row)
    assert device_profile_id(row) in payload.body()["vertices"]["DeviceProfile"]
    payload.add_anchor({"case_id": "HHG-001", "customer_id": "C12382",
                        "card_id": "C12382-K1", "flagged_txn_id": "3514030"})
    assert "CARD_TX" in payload.body()["edges"]["Card"]["C12382-K1"]


def test_case_writeback_requires_all_evidence_edges(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "cases/HHG-019.json"
    answer = Answer.model_validate_json(path.read_text(encoding="utf-8"))
    trigger = {"customer_id": "C07987", "card_id": "C07987-K2",
               "flagged_txn_id": "3503878"}
    graph = HHGOATigerGraph("http://localhost:9000", "token")
    calls = []

    def missing_edge(payload, require_existing=False):
        calls.append((payload.body(), require_existing))
        return {"results": [{"accepted_vertices": payload.vertex_count(),
                             "accepted_edges": max(0, payload.edge_count() - 1)}]}

    monkeypatch.setattr(graph, "upsert", missing_edge)
    with pytest.raises(RuntimeError, match="incomplete"):
        graph.write_answer(answer, trigger)
    assert len(calls) == 2
    assert calls[0][1] is False
    assert calls[0][0]["edges"] == {}
    assert '"written_to_graph":false' in calls[0][0]["vertices"]["InvestigationCase"]["HHG-019"]["answer_json"]["value"]
    assert calls[1][1] is True
    assert calls[1][0]["vertices"] == {}

    calls.clear()

    def accepted(payload, require_existing=False):
        calls.append((payload.body(), require_existing))
        return {"results": [{"accepted_vertices": payload.vertex_count(),
                             "accepted_edges": payload.edge_count()}]}

    monkeypatch.setattr(graph, "upsert", accepted)
    written = graph.write_answer(answer, trigger)
    assert len(calls) == 3
    assert calls[2][0]["edges"] == {}
    assert '"written_to_graph":true' in calls[2][0]["vertices"]["InvestigationCase"]["HHG-019"]["answer_json"]["value"]
    assert written.case.written_to_graph is True
    assert written.case.graph_case_id == "HHG-019"
