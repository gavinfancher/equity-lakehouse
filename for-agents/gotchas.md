# Gotchas

## Doc drift: AWS vs GCP

`frontend/content/learn/`, `frontend/content/blog/`, and parts of `Home.tsx` describe an **AWS** batch stack (EC2 spot, S3 staging, EMR Serverless, Glue catalog).

**This repo's implemented batch path is GCP** (Cloud Run, GCS, Dataproc Serverless, BigLake Iceberg).

When implementing or documenting batch work, use [architecture.md](architecture.md) and `cloud_run/`, not the learn pages alone.

## BigLake Iceberg CLI

From [finpipe-gcp-lakehouse-setup.md](../finpipe-gcp-lakehouse-setup.md):

- Command group: `gcloud biglake iceberg catalogs` (not legacy `biglake catalogs`).
- Use `--credential-mode=vended-credentials` (not `vending`).
- No `--primary-location` on create — catalog is global.
- `describe` JSON field is `biglake-service-account` (hyphenated).

## Catalog name = bucket name

The Iceberg catalog ID must match the GCS bucket name and **cannot be changed** after creation. Plan bucket names accordingly.

## Single Massive WebSocket connection

Production streaming uses **one** upstream WebSocket per API key. Don't design multi-connection ingest without a key-per-connection strategy.

## `ref/70_cloud_run.sh` paths

Scripts live under `ref/` but reference repo-root paths like `cloud_run/ingest`. Always run bootstrap scripts from the **repository root** (`./ref/70_cloud_run.sh`).

## `ref/config.env` is local-only

Not committed. Copy `ref/config.env.example` and fill in project-specific values before running scripts.

## Service account scope on VM

`ref/60_vm.sh` attaches narrow OAuth scopes to the VM. The SA may have `roles/owner` in IAM, but scopes can limit effective permissions on the instance. Use `--scopes=cloud-platform` only if you intentionally need full SA power on the VM.

## SSH firewall

`ref/10_network.sh` opens `tcp:22` from `SSH_SOURCE_RANGES` (default `0.0.0.0/0`). Restrict in `config.env` for non-demo environments.

## Dagster path hack

`finpipe/assets.py` adds `cloud_run/` to `sys.path` to import `control`. Prefer keeping ingest logic in `cloud_run/` when extending.

## Hardcoded project defaults

`cloud_run/control.py` defaults (`PROJECT_ID`, bucket names) are development values. Override via CLI flags or Dagster `IngestConfig` for other environments.

## Streaming backend not in repo

Don't search this repo for FastAPI, Redis, or Redpanda server code — the live API is external. Frontend hooks (`useStockWebSocket`, `useDemoWebSocket`) are the integration surface.
