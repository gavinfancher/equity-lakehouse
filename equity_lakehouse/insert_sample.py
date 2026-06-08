"""Append sample rows to a Lakehouse Iceberg REST catalog table."""

from __future__ import annotations

import argparse
import os

import google.auth
import google.auth.transport.requests
import pyarrow as pa
from pyiceberg.catalog import load_catalog


DEFAULT_PROJECT_ID = "equity-lakehouse"
DEFAULT_BUCKET = "equity-lakehouse-catalog"
DEFAULT_NAMESPACE = "test"
DEFAULT_TABLE = "tabletest"
REST_URI = "https://biglake.googleapis.com/iceberg/v1/restcatalog"


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
    table = catalog.load_table(identifier)

    rows = pa.table(
        {
            "name": ["alpha", "beta", "gamma"],
            "id": ["1", "2", "3"],
        }
    )
    table.append(rows)

    print(f"Inserted 3 rows into {args.project_id}.{args.bucket}.{identifier}")
    print("Query from BigQuery with:")
    print(
        f"  SELECT * FROM `{args.project_id}.{args.bucket}.{args.namespace}.{args.table}`"
    )


if __name__ == "__main__":
    main()
