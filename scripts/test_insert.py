"""Append sample rows to a Lakehouse Iceberg REST catalog table.

Run from repo root:
  uv run scripts/test_insert.py
"""

from __future__ import annotations

import argparse
import os

import google.auth
import google.auth.transport.requests
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import load_catalog


DEFAULT_PROJECT_ID = "equity-lakehouse"
DEFAULT_BUCKET = "equity-lakehouse-catalog"
DEFAULT_NAMESPACE = "test"
DEFAULT_TABLE = "testingtable"
REST_URI = "https://biglake.googleapis.com/iceberg/v1/restcatalog"
SAMPLE_SCHEMA = pa.schema(
    [
        pa.field("name", pa.string(), nullable=False),
        pa.field("id", pa.string(), nullable=False),
    ]
)


def _gcp_access_token() -> str:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    if not credentials.token:
        raise RuntimeError(
            "No GCP access token found. Run: gcloud auth application-default login"
        )
    return credentials.token


def load_biglake_catalog(*, project_id: str, bucket: str):
    return load_catalog(
        bucket,
        **{
            "type": "rest",
            "uri": REST_URI,
            "warehouse": f"gs://{bucket}",
            "token": _gcp_access_token(),
            "header.x-goog-user-project": project_id,
            "header.X-Iceberg-Access-Delegation": "vended-credentials",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Insert sample rows into a Lakehouse Iceberg REST catalog table."
    )
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID", DEFAULT_PROJECT_ID))
    parser.add_argument("--bucket", default=os.getenv("ICEBERG_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--namespace", default=os.getenv("ICEBERG_NAMESPACE", DEFAULT_NAMESPACE))
    parser.add_argument("--table", default=os.getenv("ICEBERG_TABLE", DEFAULT_TABLE))
    args = parser.parse_args()

    identifier = f"{args.namespace}.{args.table}"
    catalog = load_biglake_catalog(project_id=args.project_id, bucket=args.bucket)
    df = pd.DataFrame(
        {
            "name": ["alpha", "beta", "gamma"],
            "id": ["1", "2", "3"],
        }
    )

    if catalog.table_exists(identifier):
        table = catalog.load_table(identifier)
    else:
        table = catalog.create_table(identifier, schema=SAMPLE_SCHEMA)
        print(f"Created table {identifier}")

    arrow_table = pa.Table.from_pandas(df, schema=table.schema().as_arrow())
    table.append(arrow_table)

    catalog_name = args.bucket

    print(f"Inserted 3 rows into {identifier}")
    print()
    print(f"  project_id:   {args.project_id}")
    print(f"  catalog_name: {catalog_name}")
    print(f"  namespace:    {args.namespace}")
    print(f"  table_name:   {args.table}")
    print()
    print("Query from BigQuery:")
    print(
        f"  SELECT * FROM `{args.project_id}.{catalog_name}.{args.namespace}.{args.table}`;"
    )


if __name__ == "__main__":
    main()
