#!/bin/bash

set -euo pipefail

source "$(dirname "$0")/gcloud-config.env"

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1

APIS=(
  artifactregistry.googleapis.com
  biglake.googleapis.com
  bigquery.googleapis.com
  cloudbuild.googleapis.com
  compute.googleapis.com
  dataproc.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  run.googleapis.com
  secretmanager.googleapis.com
  storage.googleapis.com
  storageinsights.googleapis.com
)

N=${#APIS[@]}
echo
echo "enabling APIs"
echo

# Print initial pending lines
for api in "${APIS[@]}"; do
  printf "  [ \033[33mactivating\033[0m ] %s\n" "$api"
done

# Launch all; each writes its exit code to $tmpdir/<index> when done
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
for ((i=0; i<N; i++)); do
  (
    gcloud services enable "${APIS[i]}" --project="$PROJECT_ID" --quiet >/dev/null 2>&1
    echo $? > "$tmpdir/$i"
  ) &
done

# Redraw the block in place — only when state changes, so no flicker
printf "\033[?25l"   # hide cursor
trap 'printf "\033[?25h"; rm -rf "$tmpdir"' EXIT

prev_finished=-1
finished=0
while [[ $finished -lt $N ]]; do
  finished=0
  for ((i=0; i<N; i++)); do
    [[ -f "$tmpdir/$i" ]] && finished=$((finished + 1))
  done

  if [[ $finished -ne $prev_finished ]]; then
    printf "\033[%dA" "$N"   # cursor up N lines, back to top of block
    for ((i=0; i<N; i++)); do
      if [[ -f "$tmpdir/$i" ]]; then
        if [[ "$(cat "$tmpdir/$i")" == "0" ]]; then
          printf "\r\033[2K  [ \033[32m    ok    \033[0m ] %s\n" "${APIS[i]}"
        else
          printf "\r\033[2K  [ \033[31m  FAILED  \033[0m ] %s\n" "${APIS[i]}"
        fi
      else
        printf "\r\033[2K  [ \033[33mactivating\033[0m ] %s\n" "${APIS[i]}"
      fi
    done
    prev_finished=$finished
  fi

  [[ $finished -lt $N ]] && sleep 0.2
done

printf "\033[?25h"   # show cursor

# Aggregate exit codes
fail=0
for ((i=0; i<N; i++)); do
  [[ "$(cat "$tmpdir/$i")" != "0" ]] && fail=1
done
[[ $fail -ne 0 ]] && { echo "one or more APIs failed"; exit 1; }

echo
echo "script complete!"
echo