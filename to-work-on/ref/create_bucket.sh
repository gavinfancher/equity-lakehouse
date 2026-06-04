#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/gcloud-config.env"

gcloud storage buckets create gs://"$BUCKET_NAME" \
    --project="$PROJECT_ID" \
    --default-storage-class=STANDARD \
    --location="$REGION" \
    --uniform-bucket-level-access \
    --public-access-prevention
