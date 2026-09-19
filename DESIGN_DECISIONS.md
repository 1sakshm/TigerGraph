# Design decisions

| Decision | Reason | Tradeoff |
| --- | --- | --- |
| Keep HHGOA and synthetic schemas separate | The supplied transaction CSV has no account, merchant, or per-transaction card key. A universal model would invent edges. | Two adapters and UI modes to maintain. |
| Make TigerGraph the live investigation substrate | Fraud motifs require multi-hop entity and historical-case traversal. Installed GSQL bounds fan-out and makes the retrieval inspectable. | The live path cannot be verified without an endpoint and token. |
| Preserve a read-only local CSV index | It lets all 20 cases and rules be audited before Savanna access exists. | Offline evidence is marked `external`; graph judging requirements remain unmet until live rerun. |
| Separate risk from evidence confidence | Suspicious activity can be dangerous even when the explanation is uncertain. It changes whether verification, escalation, or a human-gated intervention is appropriate. | Both numbers are heuristics until outcomes become available for calibration. |
| Keep policy deterministic | An LLM can misread R1–R10 or propose an unauthorized block. Routes, report consistency, and R10 checks belong in code. | Rules must be updated when policy changes. |
| Cite every claim | Analysts need to inspect IDs and query sources; reports must not contain invented merchants or devices. | Evidence prose is less fluent than unconstrained generation. |
| Treat historical cases as context | Prior confirmed fraud on a customer group is relevant but does not prove a later transaction fraudulent. | Memory has less immediate scoring effect than a leaked label would. |
| Require corroboration for profile clusters | Shared OS/browser/device strings can be common. Coordinated abuse requires aligned amounts/email context or a documented analyst trigger plus an unusual proxy/New-device cluster. | Some true rings with weak attributes may remain uncertain. |
| Simulate only declared evidence | The benchmark provides no customer replies. Risk-score cases assume a 24-hour nonresponse and say so in `evidence_requests`. | This demonstrates R4 action progression but cannot stand in for observed testimony. |
| Stop at an approval or evidence boundary | Extra graph expansion can add noise, latency, and false positives after the next action is clear. | An analyst may choose to reopen a case for deeper review. |
| Avoid broad graph algorithms by default | A bounded two-hop motif answers the provided device and case questions directly. | Community detection and risk propagation remain future experiments, not claimed capabilities. |

## Judging alignment

- **Investigation accuracy (25%)**: bounded customer/profile/case retrieval, exact source fields, conservative episode IDs, and cited evidence.
- **Next best action (25%)**: separate initial/final lists, R2/R4/R6/R9 policy, approval routes, and explicit assumptions.
- **Case summary (10%)**: exact answer contract, concise summary, evidence ledger, and standalone SAR drafts.
- **Agentic engineering (15%)**: inspectable state progression, tool trace, MCP facade, case memory, failure boundaries, and optional cited LLM synthesis.
- **Innovation (15%)**: evidence confidence separate from risk, corroborated profile-cluster discovery, and bounded investigation decisions.
- **Demo (10%)**: analyst command center, working customer-response and approval flow, and a dataset-backed 20-case browser.

The major remaining judging risk is that the currently committed answers were generated offline. The TigerGraph build becomes judge-ready only after a live import, GSQL compile, query audit, and verified case writeback.
