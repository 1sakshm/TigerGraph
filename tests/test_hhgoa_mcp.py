import pytest

from graphsentinel.hhgoa_mcp import _limit


def test_mcp_limits_reject_unbounded_expansion():
    assert _limit(50) == 50
    with pytest.raises(ValueError):
        _limit(0)
    with pytest.raises(ValueError):
        _limit(201)
