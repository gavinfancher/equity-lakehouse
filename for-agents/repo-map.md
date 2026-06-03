# Repository map

```
equity-lakehouse/
├── AGENTS.md                 # Agent entry point
├── README.md                 # Human entry point
├── for-agents/               # Deep technical docs
├── ref/                      # GCP bootstrap scripts
├── cloud_run/                # S3→GCS ingest job + control script
├── gcp-spark/                # Dataproc Serverless jobs
├── finpipe/                  # Dagster package (ingest asset)
└── .github/workflows/        # deploy-ingest CI
```

## Sibling repos

| Repo | Contents |
|------|----------|
| [finpipe](https://github.com/gavinfancher/finpipe) | Streaming API, ingest, relay, control, EC2 deploy |
| [finpipe-website](https://github.com/gavinfancher/finpipe-website) | React dashboard, learn/blog markdown |

## By concern

| Concern | Location |
|---------|----------|
| Ingest job | `cloud_run/ingest/` |
| Trigger backfill | `cloud_run/control.py` |
| Dagster asset | `finpipe/assets.py` |
| Spark jobs | `gcp-spark/` |
| Infra scripts | `ref/*.sh` |
| Ingest CI | `.github/workflows/deploy-ingest.yml` |

## Key commands

```bash
uv sync
uv run python cloud_run/control.py --year 2025
```

See [common-tasks.md](common-tasks.md).
