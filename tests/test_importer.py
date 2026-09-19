import json

import httpx

from scripts.import_canonical import import_canonical
from scripts.import_canonical import build_transaction_payload, import_historical_cases
from graphsentinel.models import Transaction


def test_canonical_import_creates_real_graph_edges(tmp_path):
    source = tmp_path / "transactions.jsonl"
    source.write_text(json.dumps({"id":"T1","account_id":"A1","customer_id":"C1","device_id":"D1","merchant_id":"M1","occurred_at":"2026-09-19T10:00:00Z","amount":50,"currency":"USD","model_score":0.4}) + "\n", encoding="utf-8")
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"error": False, "results": [{"accepted_vertices": 5, "accepted_edges": 4}]})

    from graphsentinel.tigergraph import TigerGraphGraph
    graph = TigerGraphGraph("http://tg", "GraphSentinel", "secret", client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = import_canonical(source, graph, batch_size=1)
    body = requests[0]
    assert result["transactions"] == 1
    assert "T1" in body["vertices"]["Transaction"]
    assert "PERFORMED" in body["edges"]["Account"]["A1"]
    assert "USED_DEVICE" in body["edges"]["Transaction"]["T1"]
    assert "OWNS" in body["edges"]["Customer"]["C1"]


def test_import_rejects_unmapped_fields_before_write(tmp_path):
    source = tmp_path / "transactions.jsonl"
    source.write_text('{"TransactionID":"T1","TransactionAmt":12}\n', encoding="utf-8")
    class NeverWrite:
        def upsert_payload(self, payload, expected_edges):
            raise AssertionError("should not write")
    import pytest
    with pytest.raises(ValueError, match="canonical"):
        import_canonical(source, NeverWrite())


def test_shared_customer_account_edge_is_counted_once():
    first = Transaction(id="T1", account_id="A1", customer_id="C1", occurred_at="2026-09-19T10:00:00Z", amount=50)
    second = Transaction(id="T2", account_id="A1", customer_id="C1", occurred_at="2026-09-19T10:01:00Z", amount=60)
    _, count = build_transaction_payload([first, second])
    assert count == 3


def test_historical_case_import_links_typed_entities(tmp_path):
    source = tmp_path / "history.jsonl"
    source.write_text(json.dumps({"id":"HIST-1","account_ids":["A2"],"device_ids":["D1"],"transaction_ids":["T101"],"pattern":"shared_device_cluster","outcome":"confirmed_fraud","action":"BLOCK_CARD","summary":"Customer denial"}) + "\n", encoding="utf-8")
    writes = []
    class CaptureGraph:
        def upsert_payload(self, payload, expected_edges):
            writes.append((payload, expected_edges))
    result = import_historical_cases(source, CaptureGraph())
    payload, edges = writes[0]
    assert result["historical_cases"] == 1
    assert edges == 3
    assert "HIST-1" in payload["vertices"]["FraudCase"]
    assert "CASE_DEVICE" in payload["edges"]["FraudCase"]["HIST-1"]
