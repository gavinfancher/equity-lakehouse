# cloud_run/ingest — S3 → GCS copier

A Cloud Run **Job** that copies `.csv.gz` files from a Massive S3 bucket
into a GCS bucket, byte-for-byte (no decompression).

## How it works

```
control.py (local / Dagster)
   │  1. list S3 keys
   │  2. write manifest JSON to gs://.../_manifests/<run-id>.json
   │  3. run_job(MANIFEST_URI=..., task_count=N)
   ▼
Cloud Run Job execution
   ├── task 0   reads manifest, takes keys[0::N], copies its shard
   ├── task 1   reads manifest, takes keys[1::N], ...
   └── ...
```

Each task uses a thread pool (`WORKERS`) for in-task parallelism, so total
concurrency is `tasks × workers`.

## One-time provision

```bash
./80_secrets.sh massive-access-key
./80_secrets.sh massive-secret-key
./70_cloud_run.sh
```

## Trigger a run

```bash
uv run python cloud_run/control.py --year 2025
```

## CI/CD

`.github/workflows/deploy-ingest.yml` rebuilds the image and updates the
job on push to `main` when `cloud_run/ingest/**` changes.
