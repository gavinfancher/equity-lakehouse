#!/usr/bin/env bash
# Provision the finpipe S3 -> GCS ingest Cloud Run Job.
# Builds cloud_run/ingest/ via Cloud Build, pushes to Artifact Registry,
# then creates or updates the job. Per-execution config (manifest URI,
# task count) is supplied at runtime by cloud_run/control.py.
set -euo pipefail
source "$(dirname "$0")/config.env"

if ! gcloud secrets describe massive-access-key --project="$PROJECT_ID" >/dev/null 2>&1 \
   || ! gcloud secrets describe massive-secret-key --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "ERROR: missing secrets. Run:" >&2
  echo "  ./80_secrets.sh massive-access-key" >&2
  echo "  ./80_secrets.sh massive-secret-key" >&2
  exit 1
fi

# --- Artifact Registry -------------------------------------------------------
if gcloud artifacts repositories describe "$AR_REPO" \
     --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "Artifact Registry repo $AR_REPO exists."
else
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT_ID"
fi

# --- Build -------------------------------------------------------------------
SRC_DIR="$(dirname "$0")/../cloud_run/ingest"
gcloud builds submit "$SRC_DIR" \
  --tag="$CLOUD_RUN_IMAGE" \
  --project="$PROJECT_ID"

# --- Create or update job ----------------------------------------------------
# Defaults below are baseline; control.py overrides task_count + env per run.
COMMON_FLAGS=(
  --image="$CLOUD_RUN_IMAGE"
  --region="$REGION"
  --project="$PROJECT_ID"
  --service-account="$SA_EMAIL"
  --tasks=10
  --parallelism=10
  --cpu=2
  --memory=2Gi
  --task-timeout=30m
  --max-retries=2
  --set-secrets=MASSIVE_ACCESS_KEY=massive-access-key:latest,MASSIVE_SECRET_KEY=massive-secret-key:latest
  --set-env-vars=GOOGLE_CLOUD_PROJECT="$PROJECT_ID",WORKERS=8
)

if gcloud run jobs describe "$CLOUD_RUN_JOB" \
     --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud run jobs update "$CLOUD_RUN_JOB" "${COMMON_FLAGS[@]}"
  echo "Updated Cloud Run job $CLOUD_RUN_JOB."
else
  gcloud run jobs create "$CLOUD_RUN_JOB" "${COMMON_FLAGS[@]}"
  echo "Created Cloud Run job $CLOUD_RUN_JOB."
fi

# --- IAM: SA needs to read source/manifest, write dest, invoke the job -------
# (idempotent; safe to re-run)
for ROLE in roles/storage.objectUser roles/run.invoker; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$ROLE" \
    --quiet >/dev/null
done

cat <<EOF

Provisioned. Trigger a run with:

  uv run python cloud_run/control.py --year 2025

EOF
