# Benchmark results

This report checks answer format, provenance, cited IDs, approval routes, and case coverage. The challenge does not provide current-case outcome labels, so classification accuracy and confidence calibration cannot be measured locally.

- Cases: **20/20**
- Contract or evidence validation failures: **0**
- Evidence items: **99**
- Cases with changed next-best-action lists: **10**
- SAR drafts recommended for L2 approval: **3**
- Verified TigerGraph case writes: **0**
- Average recorded retrieval calls: **5.0**
- Average recorded latency: **0.099s**

## Historical closed-case diagnostic

These are selected closed cases, not a representative transaction sample. The table explains why the engine gives the upstream score and `New` identity flag little weight; it is not used as a direct probability lookup or a hidden benchmark label.

| Closed outcome | Cases | Mean upstream score | New identity fraction |
| --- | ---: | ---: | ---: |
| cleared | 900 | 0.881 | 0.832 |
| confirmed_fraud | 4665 | 0.475 | 0.181 |

## Verdicts

- fraud: 6
- uncertain: 14

## Patterns

- card_not_present_fraud: 1
- card_not_present_new_device: 4
- none: 13
- undocumented: 2

## Case matrix

| Case | Verdict | Probability | Pattern | Initial actions | Final actions | Graph write |
| --- | --- | ---: | --- | --- | --- | --- |
| HHG-001 | uncertain | 0.309 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-002 | uncertain | 0.353 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-003 | uncertain | 0.532 | none | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-004 | uncertain | 0.757 | card_not_present_new_device | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-005 | uncertain | 0.343 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-006 | fraud | 0.910 | card_not_present_new_device | CREATE_CASE, BLOCK_CARD, FILE_REPORT | CREATE_CASE, BLOCK_CARD, FILE_REPORT | no |
| HHG-007 | uncertain | 0.170 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-008 | fraud | 0.850 | card_not_present_fraud | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-009 | uncertain | 0.682 | none | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-010 | uncertain | 0.352 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER, ESCALATE_TO_ANALYST | CREATE_CASE, ESCALATE_TO_ANALYST, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-011 | fraud | 0.911 | card_not_present_new_device | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-012 | uncertain | 0.304 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-013 | uncertain | 0.361 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-014 | fraud | 0.954 | undocumented | CREATE_CASE, MONITOR_CONNECTED_CARDS, FILE_REPORT, ESCALATE_TO_ANALYST | CREATE_CASE, MONITOR_CONNECTED_CARDS, FILE_REPORT, ESCALATE_TO_ANALYST | no |
| HHG-015 | uncertain | 0.362 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER, ESCALATE_TO_ANALYST | CREATE_CASE, ESCALATE_TO_ANALYST, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-016 | fraud | 0.880 | card_not_present_new_device | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-017 | uncertain | 0.416 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-018 | uncertain | 0.538 | none | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-019 | fraud | 0.922 | undocumented | CREATE_CASE, MONITOR_CONNECTED_CARDS, FILE_REPORT, ESCALATE_TO_ANALYST | CREATE_CASE, MONITOR_CONNECTED_CARDS, FILE_REPORT, ESCALATE_TO_ANALYST | no |
| HHG-020 | uncertain | 0.182 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |

## Known measurement limits

- Offline answers cite the supplied CSV index as `external` evidence; they do not claim TigerGraph traversal.
- `customer_id` groups transactions, but the transaction CSV has no explicit `card_id` or merchant ID. The engine does not infer a specific physical card or merchant from issuer attributes.
- Fraud probabilities and confidence are transparent heuristics; no hidden labels are used for tuning.
- Customer nonresponse in risk-score cases is simulated and labeled in each evidence request.
- The installed GSQL and REST import paths need a live TigerGraph instance for compile and integration verification.
