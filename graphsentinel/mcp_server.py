"""MCP facade over the fixed TigerGraph tool allowlist.

Launch with `python -m graphsentinel.mcp_server` after configuring TIGERGRAPH_*.
The service uses stdio transport so clients do not receive a raw GSQL shell.
"""

import os

from mcp.server.fastmcp import FastMCP

from graphsentinel.tigergraph import TigerGraphGraph


def configured_graph() -> TigerGraphGraph:
    return TigerGraphGraph(
        os.environ["TIGERGRAPH_URL"],
        os.environ.get("TIGERGRAPH_GRAPH", "GraphSentinel"),
        os.environ["TIGERGRAPH_TOKEN"],
    )


mcp = FastMCP("GraphSentinel TigerGraph tools")


@mcp.tool()
def get_transaction_neighborhood(transaction_id: str, limit: int = 50) -> dict:
    """Retrieve one transaction, account history and bounded shared-device paths."""
    return configured_graph().neighborhood(transaction_id, limit).model_dump(mode="json")


@mcp.tool()
def find_prior_cases(account_id: str, device_id: str = "") -> list[dict]:
    """Retrieve resolved cases linked to an account or device through graph edges."""
    return [case.model_dump(mode="json") for case in configured_graph().prior_cases(account_id, device_id or None)]


if __name__ == "__main__":
    mcp.run()
