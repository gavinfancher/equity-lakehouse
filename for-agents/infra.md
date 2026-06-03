# Infrastructure (GCP)

## Bootstrap model

Provisioning lives in `ref/` as numbered, **idempotent** bash scripts. All scripts `source ref/config.env` (copy from `ref/config.env.example`).

Run from **repository root**:

```bash
cp ref/config.env.example ref/config.env   # edit PROJECT_ID, buckets, SSH, etc.
./ref/10_network.sh
./ref/20_iam.sh
./ref/30_storage.sh
./ref/40_lakehouse.sh
./ref/50_dataproc.sh    # sample Spark batch — verifies lakehouse
./ref/80_secrets.sh massive-access-key   # before Cloud Run if using ingest
./ref/80_secrets.sh massive-secret-key
./ref/70_cloud_run.sh
./ref/60_vm.sh          # optional dev VM
```

Full details: [ref/README.md](../ref/README.md).

## Service account model

Single SA (`finpipe-sa` by default) with `roles/owner`:

- **Laptop deployer** — key written to `sa-key.json` (gitignored).
- **Runtime** — attached to Cloud Run Job, Dataproc batches, VM.

For production handoff, replace `roles/owner` with scoped roles (see [gcp-bootstrap-plan.md](../gcp-bootstrap-plan.md)).

## Core resources

| Resource | Purpose |
|----------|---------|
| GCS `LAKEHOUSE_BUCKET` | Iceberg data + catalog binding |
| GCS `DATA_BUCKET` | General data / staging |
| BigLake Iceberg catalog | Metadata for Iceberg tables |
| Artifact Registry | `cloud_run/ingest` container image |
| Cloud Run Job | Parallel S3→GCS copy |
| Secret Manager | `massive-access-key`, `massive-secret-key` |
| Dataproc Serverless | PySpark batch commits |

## CI/CD

`.github/workflows/deploy-ingest.yml`:

- Triggers on `cloud_run/ingest/**` changes to `main`.
- Uses **Workload Identity Federation** (no long-lived SA keys in GitHub).
- Cloud Build → update Cloud Run Job image.

Required GitHub Actions variables: `PROJECT_ID`, `REGION`, `AR_REPO`, `JOB_NAME`, `IMAGE_URI`, `DEPLOY_SA`, `WIF_PROVIDER`.

## Auth for local development

| System | Method |
|--------|--------|
| GCP | `gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS=sa-key.json` |
| Massive S3 | Export keys from `massive.env` (see `massive.env.example`) as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` |

## Teardown

```bash
./teardown.sh   # prompts for project ID confirmation
```

## Legacy / reference docs

| File | Use |
|------|-----|
| [finpipe-gcp-lakehouse-setup.md](../finpipe-gcp-lakehouse-setup.md) | Step-by-step lakehouse commands, CLI gotchas |
| [gcp-bootstrap-plan.md](../gcp-bootstrap-plan.md) | Original design doc; some items differ from current single-SA `ref/` scripts |
