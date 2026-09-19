from pathlib import Path

import pytest

from graphsentinel.graph import FixtureGraph


FIXTURE = Path(__file__).parents[1] / "data" / "demo.json"


def test_transaction_neighborhood_finds_shared_device_accounts():
    graph = FixtureGraph.from_file(FIXTURE)
    context = graph.neighborhood("T100", limit=10)
    assert context.transaction.id == "T100"
    assert {p.account_id for p in context.device_peers} == {"A2", "A3"}
    assert {t.id for t in context.account_history} == {"T102"}
    assert context.device_peers[0].transaction_id == "T101"


def test_neighborhood_respects_limit_and_excludes_seed():
    graph = FixtureGraph.from_file(FIXTURE)
    context = graph.neighborhood("T100", limit=1)
    assert len(context.device_peers) + len(context.account_history) <= 1
    assert all(t.id != "T100" for t in context.account_history)


def test_missing_transaction_is_explicit():
    graph = FixtureGraph.from_file(FIXTURE)
    with pytest.raises(KeyError, match="T999"):
        graph.neighborhood("T999", limit=10)


def test_prior_case_search_uses_entity_overlap():
    graph = FixtureGraph.from_file(FIXTURE)
    cases = graph.prior_cases("A1", "D_NEW")
    assert [case.id for case in cases] == ["HIST-1"]
