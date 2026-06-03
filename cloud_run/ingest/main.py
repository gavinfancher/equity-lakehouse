"""
Cloud Run Job task: copy a shard of S3 .csv.gz files into GCS, byte-for-byte.

Each task reads MANIFEST_URI (a JSON object on GCS), takes its slice
keys[CLOUD_RUN_TASK_INDEX::CLOUD_RUN_TASK_COUNT], and streams each object
from S3 to GCS with a thread pool.
"""

import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import boto3
from botocore.config import Config as BotoConfig
from google.cloud import storage

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("ingest")

TASK_INDEX = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
TASK_COUNT = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))
MANIFEST_URI = os.environ["MANIFEST_URI"]
WORKERS = int(os.environ.get("WORKERS", "8"))
AWS_ACCESS_KEY_ID = os.environ["MASSIVE_ACCESS_KEY"]
AWS_SECRET_ACCESS_KEY = os.environ["MASSIVE_SECRET_KEY"]
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "https://files.massive.com")


def load_manifest(uri: str) -> dict:
    p = urlparse(uri)
    if p.scheme != "gs":
        raise ValueError(f"manifest URI must be gs://, got {uri}")
    blob = storage.Client().bucket(p.netloc).blob(p.path.lstrip("/"))
    return json.loads(blob.download_as_bytes())


def remap_key(src_key: str, dest_prefix: str) -> str:
    """Transform S3 key into a Hive-partitioned GCS path.

    us_stocks_sip/minute_aggs_v1/2021/05/2021-05-01.csv.gz
      -> lakehouse-staging/equity_min_aggs/year=2021/2021-05-01.csv.gz
    """
    filename = src_key.rsplit("/", 1)[-1]       # 2021-05-01.csv.gz
    year = filename[:4]                          # 2021
    return f"{dest_prefix}year={year}/{filename}"


def copy_one(s3, gcs_bucket, src_bucket: str, src_key: str, dest_key: str) -> str:
    obj = s3.get_object(Bucket=src_bucket, Key=src_key)
    blob = gcs_bucket.blob(dest_key)
    blob.upload_from_file(
        obj["Body"],
        size=obj["ContentLength"],
        content_type="application/gzip",
    )
    return src_key


def main() -> int:
    manifest = load_manifest(MANIFEST_URI)
    src_bucket = manifest["source_bucket"]
    dest_bucket_name = manifest["dest_bucket"]
    dest_prefix = manifest.get("dest_prefix", "")
    shard = manifest["tasks"][str(TASK_INDEX)]
    total = sum(len(v) for v in manifest["tasks"].values())

    log.info(
        "run=%s task %d/%d: %d keys (of %d total)",
        manifest.get("run_id", "?"), TASK_INDEX, TASK_COUNT, len(shard), total,
    )

    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    s3 = session.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )
    gcs_bucket = storage.Client().bucket(dest_bucket_name)

    failures: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {
            ex.submit(
                copy_one, s3, gcs_bucket, src_bucket, k,
                remap_key(k, dest_prefix),
            ): k
            for k in shard
        }
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                fut.result()
                log.info("ok %s", key)
            except Exception as e:
                failures.append((key, str(e)))
                log.error("fail %s: %s", key, e)

    log.info("task %d done: %d ok, %d failed", TASK_INDEX, len(shard) - len(failures), len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
