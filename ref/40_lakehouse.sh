#!/usr/bin/env bash
# Create the BigLake Iceberg catalog and bind its managed SA to the bucket.
# Gotchas (per finpipe-gcp-lakehouse-setup.md):
#   - command group is `gcloud biglake iceberg catalogs`
#   - --credential-mode=vended-credentials (not "vending")
#   - no --primary-location flag (catalog is global)
#   - describe JSON field is `biglake-service-account`
set -euo pipefail
source "$(dirname "$0")/config.env"

if gcloud biglake iceberg catalogs describe "$CATALOG_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "Catalog $CATALOG_NAME already exists; skipping create."
else
  gcloud biglake iceberg catalogs create "$CATALOG_NAME" \
    --project="$PROJECT_ID" \
    --catalog-type=gcs-bucket \
    --credential-mode=vended-credentials
  echo "Created Iceberg catalog $CATALOG_NAME."
fi

CATALOG_SA=$(gcloud biglake iceberg catalogs describe "$CATALOG_NAME" \
  --project="$PROJECT_ID" --format=json | jq -r '."biglake-service-account"')

if [[ -z "$CATALOG_SA" || "$CATALOG_SA" == "null" ]]; then
  echo "ERROR: could not parse biglake-service-account from describe output." >&2
  exit 1
fi
echo "Catalog managed SA: $CATALOG_SA"

gcloud storage buckets add-iam-policy-binding "gs://${LAKEHOUSE_BUCKET}" \
  --member="serviceAccount:${CATALOG_SA}" \
  --role="roles/storage.objectUser" >/dev/null
echo "Bound catalog SA to gs://${LAKEHOUSE_BUCKET}."
