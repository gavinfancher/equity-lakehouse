# Agent guide — equity-lakehouse

Start here before making architectural or cross-cutting changes.

## What this repo is

**Equity Lakehouse** is the GCP batch pipeline for finpipe: historical Massive flatfiles → Cloud Run ingest → GCS → Dataproc Serverless → Apache Iceberg (BigLake).

**Not in this repo:** streaming API ([finpipe](https://github.com/gavinfancher/finpipe)), React UI ([finpipe-website](https://github.com/gavinfancher/finpipe-website)).

## Read order

| Priority | Doc | When |
|----------|-----|------|
| 1 | [for-agents/architecture.md](for-agents/architecture.md) | System design, data flows |
| 2 | [for-agents/repo-map.md](for-agents/repo-map.md) | Where code and scripts live |
| 3 | [for-agents/gotchas.md](for-agents/gotchas.md) | GCP quirks, doc drift |
| 4 | [for-agents/conventions.md](for-agents/conventions.md) | Code style, tooling |
| 5 | [for-agents/common-tasks.md](for-agents/common-tasks.md) | Runbooks |

## Current stack

```
Massive S3 flatfiles → Cloud Run Job (S3→GCS copy) → GCS staging
  → Dataproc Serverless (PySpark) → Iceberg tables (BigLake catalog on GCS)
```

Orchestration: Dagster asset in `finpipe/assets.py` wraps `cloud_run/control.py`.

## Rules for agents

1. **Minimize scope** — match existing patterns.
2. **GCP batch only** — streaming changes belong in the finpipe repo.
3. **Update `for-agents/`** when architecture or deployment changes.
4. **Don't commit secrets** — `sa-key.json`, `massive.env`, `ref/config.env`.
5. **Python**: `uv` at repo root; `requires-python >= 3.12`.

## Human audiences

- **Recruiters**: [for-agents/for-recruiters.md](for-agents/for-recruiters.md)
- **GCP bootstrap**: [ref/README.md](ref/README.md)
