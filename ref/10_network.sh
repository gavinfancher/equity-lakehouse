#!/usr/bin/env bash
# Open tcp:22 on the default VPC for SSH from anywhere.
# Key auth is your only line of defense — never put a password on the VM account.
set -euo pipefail
source "$(dirname "$0")/config.env"

RULE="allow-ssh-anywhere"

if gcloud compute firewall-rules describe "$RULE" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "Firewall rule $RULE already exists; skipping."
else
  gcloud compute firewall-rules create "$RULE" \
    --project="$PROJECT_ID" \
    --network=default \
    --direction=INGRESS \
    --action=ALLOW \
    --rules=tcp:22 \
    --source-ranges="$SSH_SOURCE_RANGES"
  echo "Created firewall rule $RULE (tcp:22 from $SSH_SOURCE_RANGES)."
fi
