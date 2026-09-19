"""MCP facade for the five allowlisted HHGOA TigerGraph GSQL tools.

The investigation engine uses the same query port in process. MCP allows an
external agent client to inspect bounded graph evidence without a GSQL shell.
"""

import os

from mcp.server.fastmcp import FastMCP

from graphsentinel.hhgoa.tigergraph import HHGOATigerGraph


def graph() -> HHGOATigerGraph:
    return HHGOATigerGraph(os.environ["TIGERGRAPH_URL"],
                           os.environ["TIGERGRAPH_TOKEN"],
                           os.environ.get("TIGERGRAPH_GRAPH", "HHGOA"))


def _limit(value: int, maximum: int = 200) -> int:
    if value < 1 or value > maximum:
        raise ValueError(f"limit must be 1–{maximum}")
    return value


mcp = FastMCP("GraphSentinel HHGOA graph tools")


@mcp.tool()
def get_transaction_context(transaction_id: str, limit: int = 50) -> list[dict]:
    """Transaction, customer, prior customer activity and shared profile paths."""
    return graph().query("hh_transaction_context", {"tx": transaction_id, "max_results": _limit(limit)})


@mcp.tool()
def get_customer_window(customer_id: str, start_ts: str, end_ts: str,
                        limit: int = 200) -> list[dict]:
    """Bounded customer transaction window for velocity and amount comparison."""
    return graph().query("hh_customer_window", {"customer": customer_id,
                    "start_ts": start_ts, "end_ts": end_ts, "max_results": _limit(limit, 10000)})


@mcp.tool()
def get_profile_neighbors(profile_id: str, start_ts: str, end_ts: str,
                          limit: int = 120) -> list[dict]:
    """Find transactions and customers sharing a detailed device profile."""
    return graph().query("hh_profile_neighbors", {"profile": profile_id,
                    "start_ts": start_ts, "end_ts": end_ts, "max_results": _limit(limit)})


@mcp.tool()
def find_prior_cases(customer_id: str, before_ts: str, limit: int = 10) -> list[dict]:
    """Retrieve closed-case and investigation memory available before a trigger."""
    return graph().query("hh_prior_cases", {"customer": customer_id,
                    "before_ts": before_ts, "max_results": _limit(limit, 30)})


@mcp.tool()
def get_case_transactions(case_id: str, limit: int = 100) -> list[dict]:
    """Retrieve transaction anchors of a historical closed case."""
    return graph().query("hh_case_transactions", {"prior": case_id,
                    "max_results": _limit(limit)})


if __name__ == "__main__":
    mcp.run()
