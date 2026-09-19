# GraphSentinel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax for tracking.

**Goal:** Ship a working, auditable fraud investigation vertical slice and real TigerGraph integration contract.

**Architecture:** A typed graph port feeds an explicit investigator and deterministic policy gate. A local synthetic adapter permits honest offline tests while fixed GSQL queries and RESTPP implement production graph access.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pytest, TigerGraph GSQL, SQLite, vanilla browser UI.

**Spec:** `docs/superpowers/specs/2026-09-19-graphsentinel-design.md`

## Global constraints

- Do not infer HHGOA dataset columns before reading its README.
- Do not claim live TigerGraph or benchmark validation without real access.
- Never execute high impact actions without human approval.
- Every material claim must cite evidence IDs.

## Review focus

- Missing transaction must return a typed 404 without creating a case.
- Missing graph connection must be explicit, never silently switch to synthetic mode.
- Customer confirmation should change the next action without erasing the initial decision.
- Analyst approval must be required before a card or account block is recorded as executed.
- Reopening a resolved case must preserve prior events and evidence.

---

### Task 1: Domain and offline graph

**Files:** `graphsentinel/models.py`, `graphsentinel/graph.py`, `data/demo.json`, `tests/test_graph.py`

**Interfaces:** `GraphPort.get_transaction(id)`, `GraphPort.neighborhood(id, limit)`, `GraphPort.prior_cases(entity_ids)` and canonical Pydantic models.

- [ ] Write tests for valid retrieval, bounded traversal and absent transaction; run and observe failure.
- [ ] Implement types and fixture adapter; run tests to green.
- [ ] Commit the coherent task.

### Task 2: Investigation and policy

**Files:** `graphsentinel/investigator.py`, `graphsentinel/policy.py`, `tests/test_investigation.py`

**Interfaces:** `Investigator.investigate`, `Investigator.add_evidence`, `PolicyEngine.evaluate`.

- [ ] Write tests for shared device evidence, risk/confidence distinction, evidence request, changed recommendation and approval gate; run and observe failure.
- [ ] Implement state transitions, scoring, evidence value and policy; run tests to green.
- [ ] Commit the coherent task.

### Task 3: Persistence and API

**Files:** `graphsentinel/store.py`, `graphsentinel/api.py`, `tests/test_api.py`

**Interfaces:** case CRUD, `/api/investigations`, `/api/cases/{id}/evidence`, `/api/cases/{id}/decision`.

- [ ] Write API tests for create, review, feedback and missing data; run and observe failure.
- [ ] Implement SQLite storage, API and trace; run tests to green.
- [ ] Commit the coherent task.

### Task 4: TigerGraph and MCP

**Files:** `graph/schema.gsql`, `graph/queries.gsql`, `graphsentinel/tigergraph.py`, `graphsentinel/mcp_server.py`, `tests/test_tigergraph.py`

**Interfaces:** fixed installed query names, RESTPP JSON contract, case upsert, MCP tool wrappers.

- [ ] Write HTTP contract tests with a local server and a query allowlist check; run and observe failure.
- [ ] Implement GSQL schema/queries, adapter, MCP server and setup script; run tests to green.
- [ ] Commit the coherent task.

### Task 5: Command center and benchmark harness

**Files:** `frontend/`, `scripts/run_benchmark.py`, `tests/test_benchmark.py`, docs.

**Interfaces:** existing API; manifest with case ID, transaction ID, optional additional evidence.

- [ ] Write benchmark format and API regression tests; run and observe failure.
- [ ] Build working UI and benchmark artifact generator; run tests to green.
- [ ] Document local versus live modes, limitations, demo and submission copy; commit.

### Task 6: Live dataset integration

- [ ] Read the supplied HHGOA dataset README completely and map only verified fields.
- [ ] Load data to TigerGraph, install GSQL, run representative graph traversals.
- [ ] Run all 20 benchmarks, inspect failures, publish measured report and artifacts.
- [ ] Record a 3–5 minute demo and create shareable repository/blog/social artifacts after the user supplies the required external access.
