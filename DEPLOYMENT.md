# Deployment

## Public benchmark preview

The GitHub Pages workflow in `.github/workflows/pages.yml` builds a read-only
version of the benchmark UI from the committed 20 case answers and traces.
It serves the same evidence, action progression, SAR drafts, and provenance
shown by `/benchmark` in the Python app. The preview has no Python backend,
TigerGraph connection, or analyst action endpoints. Its mode badge reports
whether each answer was actually written to TigerGraph.

To reproduce the artifact locally:

```powershell
.venv\Scripts\python -m scripts.build_pages_preview
.venv\Scripts\python -m http.server 8765 --directory _site
```

Then open `http://127.0.0.1:8765/`. The Pages workflow rebuilds this artifact
on every push to `main`.

## Full investigator service

The root `Dockerfile` packages FastAPI, the interactive synthetic investigator,
the benchmark viewer, all 20 answer files, and traces. It defaults to
`GRAPHSENTINEL_MODE=demo`, where actions are simulated and the UI labels the
fixture as synthetic. The container listens on `$PORT` and exposes
`GET /api/health` for host health checks.

```bash
docker build -t graphsentinel .
docker run --rm -p 8000:8000 graphsentinel
```

The default SQLite file is `/data/cases.sqlite`. Mount a persistent volume at
`/data` on a Python container host if analyst decisions must survive restarts.
The benchmark answers are bundled as read-only files; the private raw HHGOA
dataset and DuckDB index are excluded from the image.

The container can be configured for the separate live TigerGraph interactive
workflow with `GRAPHSENTINEL_MODE=tigergraph`, `TIGERGRAPH_URL`,
`TIGERGRAPH_GRAPH`, and `TIGERGRAPH_TOKEN`. That mode enables case mutations;
put it behind host authentication before allowing public access. The HHGOA
benchmark's 20 graph writes are performed by `scripts.run_hhgoa_benchmark
--tigergraph` after the HHGOA schema, import, and queries are installed; they
are not performed by merely starting the web server.

No Python container host or TigerGraph endpoint is currently connected to this
workspace. The Pages deployment is the public preview; the full service needs
a Python host and, for graph-backed benchmark results, a TigerGraph connection.
