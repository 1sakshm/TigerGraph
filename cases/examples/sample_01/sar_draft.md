# Draft suspicious activity report — CASE-8E9DFA832636

Draft for analyst review only. No report was filed.

Transaction: T100
Risk estimate: 95%; evidence confidence heuristic: 95%

## Supported observations

- [E-001] Upstream fraud model score is 0.58 (source: transaction model score)
- [E-002] This device is absent from the account's available transaction history (source: TigerGraph account history)
- [E-003] Device D_NEW is used by 2 other accounts in the retrieved graph (source: TigerGraph device traversal)
- [E-004] Amount 920.00 is at least three times the available account median 42.00 (source: TigerGraph account history)
- [E-005] Related resolved case HIST-1 was confirmed fraud; this is supporting context, not a label for this transaction (source: TigerGraph case memory)
- [E-006] Analyst recorded customer response: transaction denied (source: analyst_recorded_customer_response)

## Proposed action

BLOCK_CARD

Analyst authorization is required before filing or any card block.
