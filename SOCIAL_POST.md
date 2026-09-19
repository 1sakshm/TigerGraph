# Social post draft

Built GraphSentinel for the Hacker House Goa 2026 TigerGraph trial: a fraud investigation system that follows customer, transaction, device-profile, and historical-case relationships, then recommends a policy-routed next action with cited evidence.

The supplied benchmark has no direct fraud labels, merchant IDs, or per-transaction card IDs, so the graph does not invent them. The repo includes 20 structured case answers, a benchmark auditor, GSQL traversals, an MCP tool facade, a case-memory path, and a working analyst UI. One useful finding: a shared browser profile is weak evidence until amount, timing, and email context corroborate it.

The current benchmark run is offline while TigerGraph connection details are pending; graph writeback is explicitly marked unverified in the files. The live TigerGraph import and query path is ready for integration testing.

Repository: https://github.com/1sakshm/TigerGraph
Demo video: [add video link after recording]

#TigerGraph #FraudDetection #GraphAI #HackerHouseGoa
