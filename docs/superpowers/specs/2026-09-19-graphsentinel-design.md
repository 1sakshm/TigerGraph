# GraphSentinel design

## Intent and constraints

Build an analyst facing, evidence first fraud investigator for the TigerGraph trial. An investigation must traverse connected financial entities, distinguish risk from confidence, seek valuable missing evidence, change its recommendation after new evidence, enforce approval, and write reusable case memory. The HHGOA IEEE dataset and a TigerGraph instance are absent from the provided workspace; no field mapping or benchmark result may be asserted until their actual contents are inspected.

## Architecture

The backend exposes a typed API and an explicit investigation state machine. A graph port provides transaction context, bounded relationships, prior cases, and case writeback. The production adapter calls a fixed allowlist of installed GSQL queries through TigerGraph RESTPP. A separate local adapter reads a labeled synthetic fixture for offline development and tests. The same port backs an MCP tool server; arbitrary GSQL is never accepted.

The investigator plans graph calls from the trigger, emits trace events, converts graph results to attributable evidence, detects explicit motifs, retrieves related prior cases, and computes a transparent risk estimate. Confidence is based on evidence coverage and contradiction; it is never conflated with model score. A value of information calculation chooses the next evidence request. A deterministic policy gate controls execution and approval. Case snapshots and decisions persist to TigerGraph in production and to SQLite in offline mode. Text synthesis may use an optional LLM on a structured evidence package; failure falls back to a cited deterministic summary. Retrieved documents are data, never instructions.

## Data contract

Canonical entities are Transaction, Account, Customer, Device, Merchant, Case and Evidence. Optional IP, Card, Address and identity vertices will be added only when the dataset README proves those relationships exist. Each imported column will have an explicit source mapping and validation report. A missing field remains unknown, never silently inferred. Benchmark inputs remain private and are not bundled.

## Interaction

The command center shows cases, risk, confidence, evidence, graph, similar cases, policy, and trace. The analyst can submit a transaction, provide evidence, approve or reject a proposed action, and close a case with an outcome. The interface labels offline synthetic mode clearly.

## Reliability and acceptance

Graph requests have limits, timeouts, and error states. No irreversible action executes automatically. A missing transaction returns a clear error. Case history captures before and after recommendations. The benchmark runner requires the real manifest and produces one artifact per case. The final integration test requires live TigerGraph and the actual dataset; until supplied, the repo can demonstrate only the synthetic path.
