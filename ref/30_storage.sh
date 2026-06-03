#!/usr/bin/env bash
# Create the lakehouse and data buckets. Both regional, uniform access.
# LAKEHOUSE_BUCKET name is permanent — it becomes the catalog ID in step 40.
set -euo pipefail
source "$(dirname "$0")/config.env"

create_bucket() {
  local name="$1"
  if gcloud storage buckets describe "gs://${name}" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Bucket gs://${name} already exists; skipping."
  else
    gcloud storage buckets create "gs://${name}" \
      --project="$PROJECT_ID" \
      --location="$REGION" \
      --uniform-bucket-level-access
    echo "Created gs://${name}."
  fi
}

create_bucket "$LAKEHOUSE_BUCKET"
create_bucket "$DATA_BUCKET"
