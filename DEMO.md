# Five-minute demo guide

## Before recording

Run the setup in [README.md](README.md). Start the API in synthetic mode for the live interaction. Open `/benchmark` in a second tab. If a TigerGraph instance is connected and imported, rerun `scripts.run_hhgoa_benchmark --tigergraph` first so the benchmark view reports verified graph writes. A live-instance recording should also show a query call or graph explorer result; never imply the offline answers came from TigerGraph.

## 0:00–0:45 — The trigger

Open `/benchmark`, select HHG-019. Explain: the existing model scored the flagged transaction 0.90, but a score is a trigger, not an investigation. Show the transaction ID, its amount, and its documented identity attributes.

## 0:45–1:45 — Relationships and evidence

Open **Evidence** and **Citation map**. Point to the detailed profile shared across customer groups and the similar amount/product/email-domain motif. Mention that a profile match alone is weak; the corroborating fields drive the undocumented-pattern finding. Open the real IDs in the evidence ledger. The benchmark file does not assert a merchant because none exists in the supplied data.

## 1:45–2:30 — Risk and uncertainty

Show the separate fraud-probability and evidence-confidence tiles. Explain the limits of a heuristic probability and the missing customer response. Open **Agent trace** for the bounded retrieval steps, then **Action progression** for what was recommended before and after the explicitly simulated 24-hour nonresponse.

## 2:30–3:15 — Policy and report

Show the final `CREATE_CASE`, `MONITOR_CONNECTED_CARDS`, `FILE_REPORT`, and `ESCALATE_TO_ANALYST` recommendations. The report is a draft behind L2 approval. Open **SAR** and show its who/what/when/where/how/why narrative and the absence of an invented merchant.

## 3:15–4:30 — A real changing decision

Switch to `/`, start synthetic transaction `T100`, and show its **SYNTHETIC DEMO** badge. In **Graph**, inspect the connected device path. The first recommendation asks for customer confirmation because risk is elevated but confidence is lower. Click **Customer denied transaction**. The case reassesses and proposes `BLOCK_CARD`, pending a named analyst. Enter an analyst ID, approve, and close the case with feedback. Explain that the bank action is simulated, while the decision and case progression are persisted. Start the same transaction again and show the prior case in **Similar cases** to demonstrate memory.

## 4:30–5:00 — Proof of building and limits

Show the repository's 20 JSON answers, [benchmark audit](BENCHMARK_RESULTS.md), GSQL files, importer, tests, and screenshot. State clearly whether TigerGraph was actually connected during this recording. The intended closing line: **“The model flags transactions. GraphSentinel investigates the story around them.”**

## Recording status

This file is a production script, not a recorded video. A 3–5 minute video still needs to be captured and uploaded as a submission artifact.
