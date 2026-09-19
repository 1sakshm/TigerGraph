# Benchmark results

This report checks answer format, provenance, cited IDs, approval routes, and case coverage. The challenge does not provide current-case outcome labels, so classification accuracy and confidence calibration cannot be measured locally.

- Cases: **20/20**
- Contract or evidence validation failures: **0**
- Evidence items: **101**
- Cases with changed next-best-action lists: **11**
- SAR drafts recommended for L2 approval: **3**
- Verified TigerGraph case writes: **0**
- Average recorded retrieval calls: **5.0**
- Average recorded latency: **0.095s**

## Verdicts

- fraud: 2
- uncertain: 18

## Patterns

- card_not_present_fraud: 2
- card_not_present_new_device: 9
- none: 7
- undocumented: 2

## Case matrix

| Case | Verdict | Probability | Pattern | Initial actions | Final actions | Graph write |
| --- | --- | ---: | --- | --- | --- | --- |
| HHG-001 | uncertain | 0.423 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-002 | uncertain | 0.609 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-003 | uncertain | 0.512 | none | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-004 | uncertain | 0.790 | card_not_present_new_device | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-005 | uncertain | 0.486 | card_not_present_new_device | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-006 | fraud | 0.882 | card_not_present_new_device | CREATE_CASE, BLOCK_CARD, FILE_REPORT | CREATE_CASE, BLOCK_CARD, FILE_REPORT | no |
| HHG-007 | uncertain | 0.581 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-008 | uncertain | 0.761 | card_not_present_fraud | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-009 | uncertain | 0.568 | none | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-010 | uncertain | 0.717 | card_not_present_new_device | CREATE_CASE, VERIFY_WITH_CUSTOMER, ESCALATE_TO_ANALYST | CREATE_CASE, ESCALATE_TO_ANALYST, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-011 | uncertain | 0.817 | card_not_present_new_device | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-012 | uncertain | 0.392 | none | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-013 | uncertain | 0.603 | card_not_present_new_device | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-014 | uncertain | 0.827 | undocumented | CREATE_CASE, VERIFY_WITH_CUSTOMER, MONITOR_CONNECTED_CARDS, FILE_REPORT, ESCALATE_TO_ANALYST | CREATE_CASE, MONITOR_CONNECTED_CARDS, FILE_REPORT, ESCALATE_TO_ANALYST, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-015 | uncertain | 0.608 | card_not_present_new_device | CREATE_CASE, VERIFY_WITH_CUSTOMER, ESCALATE_TO_ANALYST | CREATE_CASE, ESCALATE_TO_ANALYST, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-016 | uncertain | 0.716 | card_not_present_new_device | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-017 | uncertain | 0.492 | card_not_present_fraud | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |
| HHG-018 | uncertain | 0.554 | none | CREATE_CASE, BLOCK_CARD | CREATE_CASE, BLOCK_CARD | no |
| HHG-019 | fraud | 0.960 | undocumented | CREATE_CASE, MONITOR_CONNECTED_CARDS, FILE_REPORT, ESCALATE_TO_ANALYST | CREATE_CASE, MONITOR_CONNECTED_CARDS, FILE_REPORT, ESCALATE_TO_ANALYST | no |
| HHG-020 | uncertain | 0.356 | card_not_present_new_device | CREATE_CASE, VERIFY_WITH_CUSTOMER | CREATE_CASE, MONITOR_CARD, DECLINE_TRANSACTION | no |

## Known measurement limits

- Offline answers cite the supplied CSV index as `external` evidence; they do not claim TigerGraph traversal.
- `customer_id` groups transactions, but the transaction CSV has no explicit `card_id` or merchant ID. The engine does not infer a specific physical card or merchant from issuer attributes.
- Fraud probabilities and confidence are transparent heuristics; no hidden labels are used for tuning.
- Customer nonresponse in risk-score cases is simulated and labeled in each evidence request.
- The installed GSQL and REST import paths need a live TigerGraph instance for compile and integration verification.
