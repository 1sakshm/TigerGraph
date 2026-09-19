from pathlib import Path

import pytest

from graphsentinel.hhgoa.contracts import Answer, CasePart, EvidenceItem, NextActions, Sar
from graphsentinel.hhgoa.live import TigerGraphDatasetQueries
from graphsentinel.hhgoa.tigergraph import HHGOATigerGraph


INDEX = Path(__file__).resolve().parents[1] / "data/private/analysis.duckdb"


class FakeGraph:
    def __init__(self):
        self.calls = []

    def query(self, name, params):
        self.calls.append((name, params))
        if name == "hh_transaction_context":
            return [{"transaction": [{"v_id": "1", "attributes": {
                "customer_id": "C1", "ts": "2016-11-01 12:00:00", "amount": 20,
                "channel": "online", "product": "C", "risk": .3,
                "device_profile_id": "DP-X"}}],
                "device": [{"v_id": "DP-X", "attributes": {
                    "device_info": "Windows", "os": "Windows 10",
                    "browser": "edge", "screen": "1366x768"}}]}]
        if name == "hh_customer_window":
            return [{"window": [{"v_id": "0", "attributes": {
                "customer_id": "C1", "ts": "2016-10-30 12:00:00", "amount": 10,
                "billing_region": "264.0", "channel": "online", "product": "C"}}]}]
        return []


@pytest.mark.skipif(not INDEX.exists(), reason="Private case-pack index is unavailable")
def test_live_query_port_uses_installed_gsql_and_graph_provenance():
    fake = FakeGraph()
    data = TigerGraphDatasetQueries(INDEX, fake)
    tx = data.transaction("1")
    assert tx["device_info"] == "Windows"
    assert data.source == "graph"
    stats = data.history_stats("C1", "2016-11-01 12:00:00", "264.0")
    assert stats["count"] == 1
    assert [call[0] for call in fake.calls] == ["hh_transaction_context", "hh_customer_window"]


def test_query_allowlist_rejects_arbitrary_gsql():
    graph = HHGOATigerGraph("http://localhost:9000", "token")
    with pytest.raises(ValueError):
        graph.query("DROP_GRAPH", {})
