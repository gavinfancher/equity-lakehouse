#!/usr/bin/env bash
# Create or update a Secret Manager secret. Value is read from stdin (silent prompt).
#   ./80_secrets.sh <secret-name>
# Re-running adds a new version; the secret is created on first run.
set -euo pipefail
source "$(dirname "$0")/config.env"

NAME="${1:-}"
if [[ -z "$NAME" ]]; then
  echo "usage: $0 <secret-name>" >&2
  exit 1
fi

read -rsp "Value for ${NAME}: " VALUE; echo
if [[ -z "$VALUE" ]]; then
  echo "ERROR: empty value." >&2
  exit 1
fi

if gcloud secrets describe "$NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
  printf %s "$VALUE" | gcloud secrets versions add "$NAME" \
    --data-file=- --project="$PROJECT_ID"
  echo "Added new version to existing secret $NAME."
else
  printf %s "$VALUE" | gcloud secrets create "$NAME" \
    --data-file=- --project="$PROJECT_ID"
  echo "Created secret $NAME."
fi

unset VALUE
