#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/gcloud-config.env"

read -rp "secret name: " SECRET_NAME
read -rsp "secret value: " SECRET_VALUE
echo

echo -n "$SECRET_VALUE" | gcloud secrets create "$SECRET_NAME" \
    --project="$PROJECT_ID" \
    --data-file=-
