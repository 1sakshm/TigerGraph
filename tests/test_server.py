import pytest

from graphsentinel.server import create_from_env


def test_demo_mode_must_be_explicit(monkeypatch, tmp_path):
    monkeypatch.delenv("GRAPHSENTINEL_MODE", raising=False)
    monkeypatch.delenv("TIGERGRAPH_URL", raising=False)
    monkeypatch.delenv("TIGERGRAPH_TOKEN", raising=False)
    monkeypatch.setenv("GRAPHSENTINEL_DB", str(tmp_path / "cases.sqlite"))
    with pytest.raises(RuntimeError, match="TIGERGRAPH_URL"):
        create_from_env()
    monkeypatch.setenv("GRAPHSENTINEL_MODE", "demo")
    app = create_from_env()
    assert app.title == "GraphSentinel"
