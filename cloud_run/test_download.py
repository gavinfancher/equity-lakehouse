"""
Sanity-check that Massive credentials + endpoint can actually GET an object.

Defaults to downloading the oldest key in the subscription window. Verifies
the file is real gzip and prints the first few CSV rows.

  set -a; source massive.env; set +a
  uv run python cloud_run/test_download.py
  uv run python cloud_run/test_download.py --key us_stocks_sip/day_aggs_v1/2025/01/2025-01-02.csv.gz
"""

from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

from get_keys import SOURCE_BUCKET, list_keys, s3_client


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--key", default=None, help="specific S3 key; default = oldest in window")
    p.add_argument("--bucket", default=SOURCE_BUCKET)
    p.add_argument("--out", default="/tmp/test_download.csv.gz")
    p.add_argument("--rows", type=int, default=3, help="rows of CSV to print after decompress")
    args = p.parse_args()

    if args.key:
        key = args.key
    else:
        print("listing window to find oldest key...", file=sys.stderr)
        keys = list_keys(years="all")
        if not keys:
            print("no keys returned", file=sys.stderr)
            return 1
        key = keys[0]

    print(f"bucket={args.bucket}")
    print(f"key={key}")
    print(f"out={args.out}")

    s3 = s3_client()
    s3.download_file(args.bucket, key, args.out)

    size = Path(args.out).stat().st_size
    print(f"downloaded {size:,} bytes ({size / 1024 / 1024:.2f} MiB)")

    # Verify gzip magic + decompress a few rows.
    with open(args.out, "rb") as f:
        magic = f.read(2)
    if magic != b"\x1f\x8b":
        print(f"ERROR: not a gzip file (magic={magic!r})", file=sys.stderr)
        return 1
    print("gzip magic ok")

    with gzip.open(args.out, "rt") as f:
        for i, line in enumerate(f):
            if i >= args.rows + 1:   # header + N rows
                break
            print(line.rstrip())

    return 0


if __name__ == "__main__":
    sys.exit(main())
