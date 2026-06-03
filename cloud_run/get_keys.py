"""
List Massive S3 keys for the finpipe ingest job.

Prints all keys within the rolling 5-year subscription window to stdout.

CLI:
  uv run python cloud_run/get_keys.py
  uv run python cloud_run/get_keys.py > /tmp/keys.txt
"""

from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor

import boto3
import pendulum
from botocore.config import Config as BotoConfig

# ---- config ------------------------------------------------------------------
SUBSCRIPTION_YEARS = 5
DATASET_PREFIX = "us_stocks_sip/minute_aggs_v1/"
SOURCE_BUCKET = "flatfiles"
SUFFIX = ".csv.gz"
S3_ENDPOINT = "https://files.massive.com"
MARKET_TZ = "America/New_York"
MAX_WORKERS = 8

# Polygon flatfiles embed the date as "YYYY-MM-DD.csv.gz"
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\.csv\.gz$")


# ---- subscription window -----------------------------------------------------

def subscription_window() -> tuple[pendulum.Date, pendulum.Date]:
    """Rolling 5-year window ending today (NY time), inclusive on both ends.

    Massive's coverage starts the day *after* the 5-year mark — e.g. if today
    is 2026-04-30, the earliest accessible file is 2021-05-01, not 2021-04-30.
    """
    end = pendulum.now(MARKET_TZ).date()
    start = end.subtract(years=SUBSCRIPTION_YEARS).add(days=1)
    return start, end


# ---- S3 helpers --------------------------------------------------------------

def s3_client() -> "boto3.client":
    """boto3 S3 client pointed at the Massive endpoint with s3v4 signing."""
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )


def _key_date(key: str) -> pendulum.Date | None:
    """Parse the date embedded in a Polygon S3 key, or return None."""
    m = _DATE_RE.search(key)
    if not m:
        return None
    try:
        return pendulum.date(*map(int, m.groups()))
    except ValueError:
        return None


def _list_prefix(s3, prefix: str) -> list[str]:
    """Return all .csv.gz keys under prefix."""
    paginator = s3.get_paginator("list_objects_v2")
    return [
        obj["Key"]
        for page in paginator.paginate(Bucket=SOURCE_BUCKET, Prefix=prefix, PaginationConfig={"PageSize": 1000})
        for obj in page.get("Contents", [])
        if obj["Key"].endswith(SUFFIX)
    ]


# ---- public API --------------------------------------------------------------

def list_keys() -> list[str]:
    """Return sorted S3 keys for every file within the subscription window.

    Lists one prefix per year in parallel, then drops any keys whose embedded
    date falls outside the window (handles partial years at both ends).

    Auth: boto3 default credential chain. Map MASSIVE_ACCESS_KEY /
    MASSIVE_SECRET_KEY to AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in env.
    """
    start, end = subscription_window()
    years = range(start.year, end.year + 1)
    prefixes = [f"{DATASET_PREFIX}{y}/" for y in years]

    s3 = s3_client()
    keys: list[str] = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(prefixes))) as pool:
        for batch in pool.map(lambda p: _list_prefix(s3, p), prefixes):
            keys.extend(batch)

    in_window = [k for k in keys if (d := _key_date(k)) is None or start <= d <= end]
    return sorted(in_window)


# ---- CLI ---------------------------------------------------------------------

def main() -> None:
    start, end = subscription_window()
    print(f"window={start}..{end}  bucket={SOURCE_BUCKET}", file=sys.stderr)

    keys = list_keys()
    print(f"found {len(keys)} keys", file=sys.stderr)

    for k in keys:
        print(k)


if __name__ == "__main__":
    main()
