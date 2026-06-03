# Equity Lakehouse

Batch analytics lakehouse for US equity minute bars: Massive S3 flatfiles → Cloud Run ingest → GCS staging → Dataproc Serverless → **Apache Iceberg** on GCP (BigLake catalog).

**Related repos:** [finpipe](https://github.com/gavinfancher/finpipe) (real-time streaming API) · [finpipe-website](https://github.com/gavinfancher/finpipe-website) (React dashboard)

**[Architecture docs →](for-agents/architecture.md)** · **[For recruiters →](for-agents/for-recruiters.md)**

---

## What it does

| Stage | Service |
|-------|---------|
| S3 → GCS copy | Cloud Run Job (manifest-sharded) |
| Staging → Iceberg | Dataproc Serverless (PySpark) |
| Catalog | BigLake Iceberg on GCS |
| Orchestration | Dagster (`finpipe/assets.py`) |

---

## Tech stack

Python 3.12 · Apache Iceberg · GCP (Cloud Run, GCS, Dataproc Serverless, BigLake, Secret Manager) · Dagster · GitHub Actions (WIF)

---

## Repository layout

```
equity-lakehouse/
├── cloud_run/          # S3→GCS ingest job + control script
├── finpipe/            # Dagster orchestration
├── gcp-spark/          # Dataproc Serverless Spark jobs
├── ref/                # Idempotent GCP bootstrap scripts
├── for-agents/         # Architecture reference
└── AGENTS.md           # Entry point for AI coding tools
```

---

## Quick start

### Batch ingest

```bash
uv sync
cp massive.env.example massive.env   # Massive S3 credentials
source massive.env
uv run python cloud_run/control.py --year 2025
```

### GCP bootstrap

```bash
cp ref/config.env.example ref/config.env
./ref/10_network.sh
./ref/20_iam.sh
# … see ref/README.md
```

---

## Documentation

| Audience | Start here |
|----------|------------|
| AI agents | [AGENTS.md](AGENTS.md) |
| Recruiters | [for-agents/for-recruiters.md](for-agents/for-recruiters.md) |
| GCP provisioning | [ref/README.md](ref/README.md) |

Built by [Gavin Fancher](https://gavinfancher.com).
