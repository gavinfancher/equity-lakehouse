#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/gcloud-config.env"

SA_NAME="finpipe-backfill-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# --- Create service account --------------------------------------------------
gcloud iam service-accounts create "$SA_NAME" \
    --project="$PROJECT_ID" \
    --display-name="finpipe backfill Cloud Run job" || true

sleep 10

# --- Grant access to secrets -------------------------------------------------
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

# --- Grant write access to GCS bucket ----------------------------------------
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectUser"

echo "service account: ${SA_EMAIL}"
