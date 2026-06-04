#!/usr/bin/env bash
# Create one service account that does double duty:
#   - laptop deployer (downloaded JSON key for local gcloud / SDKs)
#   - workload runtime (attached to VM, Dataproc batches, Cloud Run job)
# Granted roles/owner. For a multi-user handoff, swap owner for the targeted role list.
set -euo pipefail
source "$(dirname "$0")/config.env"

if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "Service account $SA_EMAIL already exists; skipping create."
else
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="finpipe single SA (deployer + runtime)" \
    --project="$PROJECT_ID"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/owner" \
  --condition=None \
  --quiet >/dev/null
echo "Granted roles/owner to $SA_EMAIL."

if [[ -f "$SA_KEY_PATH" ]]; then
  echo "Key already at $SA_KEY_PATH; not regenerating. Delete it first to rotate."
else
  gcloud iam service-accounts keys create "$SA_KEY_PATH" \
    --iam-account="$SA_EMAIL" \
    --project="$PROJECT_ID"
  chmod 600 "$SA_KEY_PATH"
  echo "Wrote SA key to $SA_KEY_PATH (chmod 600)."
fi

cat <<EOF

To use this key locally, add to your shell profile:
  export GOOGLE_APPLICATION_CREDENTIALS="$SA_KEY_PATH"
  gcloud auth activate-service-account --key-file="$SA_KEY_PATH"

EOF
