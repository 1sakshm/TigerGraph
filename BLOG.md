# Building GraphSentinel: from a fraud alert to an investigation

Published for the Hacker House Goa 2026 TigerGraph trial. Read the formatted
version at <https://1sakshm.github.io/TigerGraph/blog/>, inspect the
[20-case benchmark](https://1sakshm.github.io/TigerGraph/), or open the
[interactive investigator](https://graphsentinel-hhgoa-demo.onrender.com/).

A fraud model can say “look here.” It cannot tell an analyst whether a customer changed devices, several customers share an origin, a disputed charge resembles previous behavior, or a block would harm an innocent cardholder. GraphSentinel turns a trigger into a bounded investigation with evidence, uncertainty, and a policy-routed next action.

## The dataset forced the design

The supplied HHGOA IEEE data has 590,742 transactions, 144,432 identity records, 5,565 closed cases, and 20 benchmark triggers. It deliberately omits a direct fraud label on the transactions to investigate. It also has no merchant ID or per-transaction card ID. That last point matters: I could not honestly build a `Transaction -> Merchant` edge or assign every transaction to `C12345-K2` by guessing from issuer attributes. The HHGOA graph therefore connects customers to transactions through the supplied `customer_id`, and connects cards to transactions only where the case pack or closed cases explicitly name that link.

## The graph is the evidence substrate

The TigerGraph schema models customers, cards, transactions, device profiles, email domains, billing regions, closed cases, investigation cases, and evidence. Five installed GSQL queries cover transaction neighborhoods, bounded customer windows, shared device-profile neighborhoods, previous cases, and historical case transactions. The query names and result limits are fixed in the application and exposed through MCP; analysts cannot send arbitrary GSQL from the UI.

The most useful motif is not “two rows have the same browser.” Common devices and browsers produce false positives. GraphSentinel looks for corroboration: similar amount, product, and email-domain context across customer groups, or a documented analyst trigger combined with repeated New-device and anonymous-proxy context. In HHG-019, three customer groups appear in a short sequence with closely matching near-$100 online purchases and the same detailed profile and email-domain combination. In HHG-017, a broader profile match lacks the same corroboration, so it is not treated as a confirmed coordinated ring.

## The agent knows when evidence is weak

GraphSentinel tracks a heuristic fraud probability and a separate evidence-confidence estimate. High suspected harm with medium confidence can call for verification or escalation before a customer-impacting action. A case trace records what was retrieved, why, and where investigation stopped. Every conclusion becomes an evidence item with source, query reference, and real entity IDs. Similar closed cases are context; they do not label new activity.

The benchmark does not provide customer replies. For risk-score cases that require validation, the current answers explicitly simulate a 24-hour nonresponse. The initial recommendation is `VERIFY_WITH_CUSTOMER`; the updated recommendation follows policy R4 with monitoring and a proposed decline of pending authorizations. The response is written as an assumption, never as observed testimony. In the interactive synthetic demo, an analyst can enter actual confirmation or denial and watch the recommendation change immediately.

## Policy is code, not a prompt

The supplied rules R1–R10 determine action routes. `BLOCK_CARD` and `FILE_REPORT` are human-gated; `BLOCK_ALL_CARDS` is forbidden without evidence of a wider compromise. The optional LLM can write a cited summary, but it cannot change graph retrieval, probabilities, policy routes, or execution. If the LLM output cites an unknown evidence ID, the deterministic summary remains.

## What worked and what is still open

The repository produces all 20 required answer files and validates their shape, cited IDs, approval routes, and SAR consistency. The audit currently records 99 evidence items, 10 cases with changed action lists, and three report drafts. The polished benchmark browser and interactive analyst UI are working locally. The full import payload builder has processed all supplied rows in dry-run mode.

The historical closed cases gave a useful warning about model-score dependence: the 900 cleared cases had a mean upstream score of 0.881, while 4,665 confirmed fraud cases averaged 0.475. `New` identity status also appeared in 83.2% of cleared cases. This is a selected closed-case sample, so those rates are not probabilities for a new transaction. They justify giving the score and New flag little weight unless graph evidence or customer testimony corroborates them.

The committed answers are **offline results**, marked `source: external` with `written_to_graph: false`. The GSQL schema, importer, live query adapter, and case writeback path are implemented, but they still need a TigerGraph endpoint to compile and verify. The current-case labels are hidden, so I cannot claim pattern accuracy or statistical calibration. With more time and live outcomes, I would test calibration, compare false-positive cost by action, and evaluate whether community detection or risk propagation adds value beyond the bounded motifs.

The core lesson: a good fraud assistant must explain relationships, uncertainty, and authorization—not merely repeat a model score.
