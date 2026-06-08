#!/usr/bin/env bash
set -euo pipefail

# Create a Lakehouse runtime catalog (Iceberg REST) backed by a GCS bucket.
#
# Usage:
#   ./scripts/create-lakehouse-catalog.sh
#
# Override defaults with env vars:
#   PROJECT_ID=my-project BUCKET_NAME=my-bucket ./scripts/create-lakehouse-catalog.sh

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
BUCKET_NAME="${BUCKET_NAME:-}"
CATALOG_NAME="${CATALOG_NAME:-${BUCKET_NAME}}"
CREDENTIAL_MODE="${CREDENTIAL_MODE:-vended-credentials}"  # or end-user
PRIMARY_LOCATION="${PRIMARY_LOCATION:-}"                 # optional: US or EU

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Set PROJECT_ID or run: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

if [[ -z "${BUCKET_NAME}" ]]; then
  echo "Set BUCKET_NAME to your existing GCS bucket name." >&2
  exit 1
fi

echo "Project:         ${PROJECT_ID}"
echo "Bucket:          gs://${BUCKET_NAME}"
echo "Catalog:         ${CATALOG_NAME}"
echo "Credential mode: ${CREDENTIAL_MODE}"
echo

echo "==> Enabling BigLake API..."
gcloud services enable biglake.googleapis.com --project="${PROJECT_ID}"

echo "==> Creating Iceberg REST catalog..."
CREATE_ARGS=(
  "${CATALOG_NAME}"
  --project="${PROJECT_ID}"
  --catalog-type=gcs-bucket
  --credential-mode="${CREDENTIAL_MODE}"
)

if [[ -n "${PRIMARY_LOCATION}" ]]; then
  CREATE_ARGS+=(--primary-location="${PRIMARY_LOCATION}")
fi

gcloud biglake iceberg catalogs create "${CREATE_ARGS[@]}"

echo "==> Catalog details..."
gcloud biglake iceberg catalogs describe "${CATALOG_NAME}" --project="${PROJECT_ID}"

if [[ "${CREDENTIAL_MODE}" == "vended-credentials" ]]; then
  SERVICE_ACCOUNT_EMAIL="$(
    gcloud biglake iceberg catalogs describe "${CATALOG_NAME}" \
      --project="${PROJECT_ID}" \
      --format="value(biglakeServiceAccount)"
  )"

  if [[ -z "${SERVICE_ACCOUNT_EMAIL}" ]]; then
    echo "Warning: no biglakeServiceAccount returned; skip IAM binding." >&2
    exit 0
  fi

  echo "==> Granting storage.objectUser to ${SERVICE_ACCOUNT_EMAIL}..."
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/storage.objectUser"
fi

echo
echo "Done."
echo "REST endpoint: https://biglake.googleapis.com/iceberg/v1/restcatalog"
echo "Warehouse:     gs://${BUCKET_NAME}"
