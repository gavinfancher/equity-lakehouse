# GCP bootstrap — finpipe

Numbered scripts that provision a finpipe environment on a fresh GCP project: networking, a single service account, GCS buckets, a BigLake Iceberg catalog, Dataproc Serverless verification, optional VM, Secret Manager, and the Cloud Run ingest job.

Run all commands from the **repository root**.

## Prereqs

- A GCP project with billing linked
- `gcloud` CLI authenticated: `gcloud auth login`
- `jq` installed (used by `40_lakehouse.sh`)
- SSH public key at the path in `SSH_PUBKEY_PATH`
- Massive API keys for ingest (stored via `80_secrets.sh`)

## Setup

1. Copy and edit config:

   ```bash
   cp ref/config.env.example ref/config.env
   ```

   At minimum set `PROJECT_ID`, `LAKEHOUSE_BUCKET`, `DATA_BUCKET`, `SSH_USER`, `SSH_PUBKEY_PATH`.

2. Run scripts in order:

   ```bash
   ./ref/10_network.sh         # firewall: tcp:22
   ./ref/20_iam.sh             # SA + owner + sa-key.json
   ./ref/30_storage.sh         # lakehouse + data buckets
   ./ref/40_lakehouse.sh       # Iceberg catalog + bucket binding
   ./ref/50_dataproc.sh        # sample Spark batch (verifies end-to-end)
   ./ref/80_secrets.sh massive-access-key   # before 70 if using Cloud Run
   ./ref/80_secrets.sh massive-secret-key
   ./ref/70_cloud_run.sh       # build image, deploy job
   ./ref/60_vm.sh              # optional VM with SSH
   ```

Each script is idempotent — re-running a completed step is a no-op.

## Service account model

One SA (`finpipe-sa` by default) with `roles/owner`:

- **Laptop deployer** — `20_iam.sh` writes `sa-key.json` (gitignored):

  ```bash
  export GOOGLE_APPLICATION_CREDENTIALS="$PWD/sa-key.json"
  gcloud auth activate-service-account --key-file="$PWD/sa-key.json"
  ```

- **Workload runtime** — attached to VM, Dataproc batches, and Cloud Run job.

For multi-user handoff, swap `roles/owner` for scoped roles (see [gcp-bootstrap-plan.md](../gcp-bootstrap-plan.md)).

## SSH

`10_network.sh` opens `tcp:22` from `SSH_SOURCE_RANGES` (default `0.0.0.0/0`). Key auth is the primary control — restrict the CIDR in `config.env` when possible.

## Secrets

```bash
./ref/80_secrets.sh <name>   # silent prompt; creates or adds a new version
```

Cloud Run ingest expects `massive-access-key` and `massive-secret-key`.

## Trigger ingest

```bash
uv run python cloud_run/control.py --year 2025
```

## Teardown

```bash
./teardown.sh
```

Prompts for project ID before deleting resources.

## Related docs

- [finpipe-gcp-lakehouse-setup.md](../finpipe-gcp-lakehouse-setup.md) — hand-run lakehouse commands and CLI gotchas
- [for-agents/infra.md](../for-agents/infra.md) — architecture-level infra overview
