#!/usr/bin/env bash
# Create the finpipe VM with the config from gcp_run.sh:
#   Ubuntu 24.04 minimal, pd-balanced 10GB, default subnet, shielded VM (no secure boot),
#   project-wide SSH key, OS Login disabled at project level.
# Bugs fixed from the original: real `\` line continuations and $(cat "$SSH_KEY_PATH").
set -euo pipefail
source "$(dirname "$0")/config.env"

if [[ ! -f "$SSH_PUBKEY_PATH" ]]; then
  echo "ERROR: SSH public key not found at $SSH_PUBKEY_PATH" >&2
  echo "Generate one: ssh-keygen -t ed25519 -f ${SSH_PUBKEY_PATH%.pub}" >&2
  exit 1
fi

gcloud config set project "$PROJECT_ID"
gcloud config set compute/zone "$ZONE"
gcloud config set compute/region "$REGION"

# Project-wide SSH key + OS Login off (so metadata SSH keys are honored)
echo "Setting project-wide SSH key..."
gcloud compute project-info add-metadata \
  --metadata "ssh-keys=${SSH_USER}:$(cat "$SSH_PUBKEY_PATH")"

echo "Disabling OS Login..."
gcloud compute project-info add-metadata \
  --metadata enable-oslogin=FALSE

if gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "VM $VM_NAME already exists; skipping create."
else
  echo "Creating VM..."
  gcloud compute instances create "$VM_NAME" \
    --zone="$ZONE" \
    --machine-type="$VM_MACHINE_TYPE" \
    --subnet=default \
    --image="$VM_IMAGE" \
    --image-project="$VM_IMAGE_PROJECT" \
    --boot-disk-size="$VM_DISK_SIZE" \
    --boot-disk-type="$VM_DISK_TYPE" \
    --service-account="$SA_EMAIL" \
    --maintenance-policy=MIGRATE \
    --no-restart-on-failure \
    --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/trace.append \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --no-shielded-secure-boot
fi

PUBLIC_IP=$(gcloud compute instances describe "$VM_NAME" \
  --zone="$ZONE" --project="$PROJECT_ID" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo
echo "VM READY"
echo "  ssh ${SSH_USER}@${PUBLIC_IP}"
echo "  gcloud compute ssh ${VM_NAME} --zone=${ZONE} --project=${PROJECT_ID}"
