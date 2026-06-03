# For recruiters & hiring managers

**Equity Lakehouse** — batch GCP pipeline for US equity minute bars into Apache Iceberg.

Built by [Gavin Fancher](https://gavinfancher.com). Companion repos: [finpipe](https://github.com/gavinfancher/finpipe) (streaming API), [finpipe-website](https://github.com/gavinfancher/finpipe-website) (dashboard UI).

## Elevator pitch

Historical market data from Massive S3 flatfiles lands in an **Iceberg lakehouse on GCP** via a staged two-phase pipeline: parallel Cloud Run copy, then Dataproc Serverless Spark commits with a BigLake catalog.

## Skills demonstrated

| Area | Evidence |
|------|----------|
| Lakehouse / Iceberg | BigLake setup, staged writes, Spark jobs in `gcp-spark/` |
| Cloud data engineering | Cloud Run Jobs, GCS, Dataproc Serverless |
| Pipeline design | Manifest sharding, ingest → commit separation |
| Orchestration | Dagster (`finpipe/assets.py`) |
| IaC | Idempotent `ref/*.sh` scripts |
| DevOps | Dockerized ingest, GHA + WIF deploy |

## 15-minute review path

1. [README.md](../README.md)
2. [architecture.md](architecture.md)
3. `cloud_run/control.py` + `cloud_run/ingest/main.py`
4. `ref/40_lakehouse.sh`
5. `.github/workflows/deploy-ingest.yml`

## FAQ

**Is streaming in this repo?** No — see [finpipe](https://github.com/gavinfancher/finpipe).

**Is the UI in this repo?** No — see [finpipe-website](https://github.com/gavinfancher/finpipe-website).
