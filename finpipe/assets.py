import sys
from pathlib import Path

from dagster import Config, asset

sys.path.insert(0, str(Path(__file__).parent.parent / "cloud_run"))
from control import (  # noqa: E402
    DEFAULT_TASKS,
    DEFAULT_WORKERS,
    DEST_BUCKET,
    DEST_PREFIX,
    JOB_NAME,
    MANIFEST_BUCKET,
    MANIFEST_PREFIX,
    PROJECT_ID,
    REGION,
    run,
)


class IngestConfig(Config):
    project: str = PROJECT_ID
    region: str = REGION
    job: str = JOB_NAME
    dest_bucket: str = DEST_BUCKET
    dest_prefix: str = DEST_PREFIX
    manifest_bucket: str = MANIFEST_BUCKET
    manifest_prefix: str = MANIFEST_PREFIX
    tasks: int = DEFAULT_TASKS
    workers: int = DEFAULT_WORKERS


@asset
def ingest(config: IngestConfig) -> dict:
    """Trigger the Cloud Run ingest job for the full subscription window."""
    return run(
        project=config.project,
        region=config.region,
        job=config.job,
        dest_bucket=config.dest_bucket,
        dest_prefix=config.dest_prefix,
        manifest_bucket=config.manifest_bucket,
        manifest_prefix=config.manifest_prefix,
        tasks=config.tasks,
        workers=config.workers,
    )
