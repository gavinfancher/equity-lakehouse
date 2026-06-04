#!/bin/bash

source "$(dirname "$0")/gcloud-config.env"

# --- Artifact Registry repo --------------------------------------------------
gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT_ID"

# --- Build & push image ------------------------------------------------------
gcloud builds submit cloud_run/ingest \
    --tag="$IMAGE" \
    --project="$PROJECT_ID"

# --- Create or update job ----------------------------------------------------
gcloud run jobs update "$JOB_NAME" \
    --image="$IMAGE" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --service-account="$SA_EMAIL" \
    --tasks=20 \
    --parallelism=20 \
    --cpu=2 \
    --memory=2Gi \
    --task-timeout=30m \
    --max-retries=2 \
    --set-secrets=MASSIVE_ACCESS_KEY=$MASSIVE_ACCESS_KEY_NAME:latest,MASSIVE_SECRET_KEY=$MASSIVE_SECRET_KEY_NAME:latest \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},WORKERS=8"
