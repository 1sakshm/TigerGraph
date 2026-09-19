import os
from pathlib import Path

import uvicorn

from graphsentinel.api import create_app
from graphsentinel.graph import FixtureGraph
from graphsentinel.store import CaseStore
from graphsentinel.tigergraph import TigerGraphGraph
from graphsentinel.synthesis import OpenAISummarizer


def create_from_env():
    mode = os.environ.get("GRAPHSENTINEL_MODE", "tigergraph").lower()
    if mode == "demo":
        graph = FixtureGraph.from_file(Path(__file__).parents[1] / "data" / "demo.json")
        public_mode = "synthetic_demo"
    elif mode == "tigergraph":
        url = os.environ.get("TIGERGRAPH_URL")
        token = os.environ.get("TIGERGRAPH_TOKEN")
        if not url or not token:
            raise RuntimeError("TIGERGRAPH_URL and TIGERGRAPH_TOKEN are required; set GRAPHSENTINEL_MODE=demo only for synthetic mode")
        graph = TigerGraphGraph(url, os.environ.get("TIGERGRAPH_GRAPH", "GraphSentinel"), token)
        public_mode = "tigergraph"
    else:
        raise RuntimeError(f"Unknown GRAPHSENTINEL_MODE: {mode}")
    db = Path(os.environ.get("GRAPHSENTINEL_DB", "data/cases.sqlite"))
    key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL")
    summarizer = OpenAISummarizer(key, model) if key and model else None
    return create_app(graph, CaseStore(db), public_mode, summarizer=summarizer)


if __name__ == "__main__":
    uvicorn.run(create_from_env(), host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
