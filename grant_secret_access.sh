#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/gcloud-config.env"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor"
