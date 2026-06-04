#!/usr/bin/env bash
# Reverse-order teardown. Each step trails `|| true` so partial state still cleans up.
# Destructive and irreversible — buckets and their contents go away.
set -uo pipefail
source "$(dirname "$0")/config.env"

read -rp "Tear down $PROJECT_ID resources? type the project id to confirm: " CONFIRM
if [[ "$CONFIRM" != "$PROJECT_ID" ]]; then
  echo "Aborted."
  exit 1
fi

# Cloud Run job + Artifact Registry
gcloud run jobs delete "$CLOUD_RUN_JOB" --region="$REGION" --project="$PROJECT_ID" --quiet || true
gcloud artifacts repositories delete "$AR_REPO" --location="$REGION" --project="$PROJECT_ID" --quiet || true

# Secrets (only the two created by the cloud_run flow; add more by hand if needed)
gcloud secrets delete massive-access-key --project="$PROJECT_ID" --quiet || true
gcloud secrets delete massive-secret-key --project="$PROJECT_ID" --quiet || true

# VM
gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --quiet || true

# Lakehouse: tables/namespaces survive only as Iceberg metadata in the bucket; deleting the bucket nukes them
gcloud biglake iceberg catalogs delete "$CATALOG_NAME" --project="$PROJECT_ID" --quiet || true

# Buckets
gcloud storage rm -r "gs://${LAKEHOUSE_BUCKET}" --project="$PROJECT_ID" || true
gcloud storage rm -r "gs://${DATA_BUCKET}" --project="$PROJECT_ID" || true

# Auto-created Dataproc staging bucket
for b in $(gcloud storage ls --project="$PROJECT_ID" 2>/dev/null | grep dataproc-staging || true); do
  gcloud storage rm -r "$b" --project="$PROJECT_ID" || true
done

# Firewall
gcloud compute firewall-rules delete allow-ssh-anywhere --project="$PROJECT_ID" --quiet || true

# Service account (last — other deletes may have been authed by it)
gcloud iam service-accounts delete "$SA_EMAIL" --project="$PROJECT_ID" --quiet || true
rm -f "$SA_KEY_PATH"

echo "Teardown complete."
