"""
Control script: lists S3 keys (via get_keys), writes a manifest to GCS,
triggers the Cloud Run job. Run locally for now; Dagster will call run() later.

  uv run python cloud_run/control.py

Auth:
  - GCP: ADC (gcloud auth application-default login).
  - AWS: MASSIVE_ACCESS_KEY / MASSIVE_SECRET_KEY exported as
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.
"""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass, asdict

import pendulum

from google.cloud import run_v2, storage

from get_keys import list_keys, SOURCE_BUCKET


# ---- defaults; override via CLI ----------------------------------------------
PROJECT_ID = "finpipe-test"
REGION = "us-central1"
JOB_NAME = "finpipe-backfill"

DEST_BUCKET = "finpipe-bucket-01"
DEST_PREFIX = "lakehouse-staging/equity_min_aggs/"

MANIFEST_BUCKET = "finpipe-bucket-01"
MANIFEST_PREFIX = "_manifests/"

DEFAULT_TASKS = 10
DEFAULT_WORKERS = 8


@dataclass
class Manifest:
    run_id: str
    source_bucket: str
    dest_bucket: str
    dest_prefix: str
    task_count: int
    tasks: dict[str, list[str]]   # str index ("0".."N-1") -> keys for that task


def shard_keys(keys: list[str], task_count: int) -> dict[str, list[str]]:
    """Round-robin assign keys to tasks; balanced if keys are sorted by size/date."""
    buckets: dict[str, list[str]] = {str(i): [] for i in range(task_count)}
    for i, k in enumerate(keys):
        buckets[str(i % task_count)].append(k)
    return buckets


def write_manifest(manifest: Manifest, bucket: str, prefix: str) -> str:
    blob_path = f"{prefix}{manifest.run_id}.json"
    blob = storage.Client().bucket(bucket).blob(blob_path)
    blob.upload_from_string(
        json.dumps(asdict(manifest), indent=2),
        content_type="application/json",
    )
    return f"gs://{bucket}/{blob_path}"


def run_job(
    project: str,
    region: str,
    job: str,
    manifest_uri: str,
    tasks: int,
    workers: int,
    run_id: str,
) -> str:
    client = run_v2.JobsClient()
    name = f"projects/{project}/locations/{region}/jobs/{job}"

    overrides = run_v2.RunJobRequest.Overrides(
        task_count=tasks,
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                env=[
                    run_v2.EnvVar(name="MANIFEST_URI", value=manifest_uri),
                    run_v2.EnvVar(name="WORKERS", value=str(workers)),
                    run_v2.EnvVar(name="RUN_ID", value=run_id),
                ],
            ),
        ],
    )

    op = client.run_job(request=run_v2.RunJobRequest(name=name, overrides=overrides))
    execution_name = op.metadata.name
    print(f"  execution: {execution_name} (waiting...)")
    result = op.result()
    status = "succeeded" if result.succeeded_count > 0 else "failed"
    print(f"  execution {status}: succeeded={result.succeeded_count} failed={result.failed_count}")
    return execution_name


def run(
    project: str = PROJECT_ID,
    region: str = REGION,
    job: str = JOB_NAME,
    dest_bucket: str = DEST_BUCKET,
    dest_prefix: str = DEST_PREFIX,
    manifest_bucket: str = MANIFEST_BUCKET,
    manifest_prefix: str = MANIFEST_PREFIX,
    tasks: int = DEFAULT_TASKS,
    workers: int = DEFAULT_WORKERS,
) -> dict:
    """Public entrypoint — Dagster will import and call this."""
    run_id = f"{pendulum.now('UTC').format('YYYYMMDD-HHmmss')}-{uuid.uuid4().hex[:6]}"
    print(f"[{run_id}] listing keys from massive")

    keys = list_keys()
    if not keys:
        raise RuntimeError(f"no keys found in s3://{SOURCE_BUCKET}")
    print(f"[{run_id}] {len(keys)} keys")

    manifest = Manifest(
        run_id=run_id,
        source_bucket=SOURCE_BUCKET,
        dest_bucket=dest_bucket,
        dest_prefix=dest_prefix,
        task_count=tasks,
        tasks=shard_keys(keys, tasks),
    )
    manifest_uri = write_manifest(manifest, manifest_bucket, manifest_prefix)
    print(f"[{run_id}] manifest: {manifest_uri}")

    execution = run_job(project, region, job, manifest_uri, tasks, workers, run_id)
    print(f"[{run_id}] done: {execution}")

    return {
        "run_id": run_id,
        "manifest_uri": manifest_uri,
        "execution": execution,
        "key_count": len(keys),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", default=PROJECT_ID)
    p.add_argument("--region", default=REGION)
    p.add_argument("--job", default=JOB_NAME)
    p.add_argument("--dest-bucket", default=DEST_BUCKET)
    p.add_argument("--dest-prefix", default=DEST_PREFIX)
    p.add_argument("--tasks", type=int, default=DEFAULT_TASKS)
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = p.parse_args()

    run(
        project=args.project,
        region=args.region,
        job=args.job,
        dest_bucket=args.dest_bucket,
        dest_prefix=args.dest_prefix,
        tasks=args.tasks,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
