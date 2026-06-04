#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-gcloud-config.env}"
TABLE_NAME="${2:-}"
NAMESPACE_OVERRIDE="${NAMESPACE:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

if ! command -v bq >/dev/null 2>&1; then
  echo "ERROR: bq CLI is required but not found in PATH." >&2
  exit 1
fi

PROJECT_ID="${PROJECT_ID:-}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: PROJECT_ID is required in $ENV_FILE." >&2
  exit 1
fi

# BigQuery table path is 4-part: project.catalog.namespace.table
# INFORMATION_SCHEMA is catalog-scoped, then filtered by table_schema.
CATALOG_NAME="${CATALOG_NAME:-${LAKEHOUSE_BUCKET:-}}"
if [[ -z "$CATALOG_NAME" ]]; then
  if command -v gcloud >/dev/null 2>&1; then
    CATALOG_NAME="$(gcloud biglake iceberg catalogs list \
      --project="$PROJECT_ID" \
      --format='value(name)' 2>/dev/null | head -n 1 || true)"
  fi
fi
if [[ -z "$CATALOG_NAME" ]]; then
  echo "ERROR: set CATALOG_NAME (or LAKEHOUSE_BUCKET) in $ENV_FILE, or create a BigLake Iceberg catalog." >&2
  exit 1
fi

NAMESPACE="${NAMESPACE_OVERRIDE:-${LAKEHOUSE_NAMESPACE:-market_data}}"

TABLES_FQN="${PROJECT_ID}.${CATALOG_NAME}.INFORMATION_SCHEMA.TABLES"
COLUMNS_FQN="${PROJECT_ID}.${CATALOG_NAME}.INFORMATION_SCHEMA.COLUMNS"

echo "Project:   $PROJECT_ID"
echo "Catalog:   $CATALOG_NAME"
echo "Namespace: $NAMESPACE"
echo

echo "== Tables =="
bq query --nouse_legacy_sql "
SELECT table_name
FROM \`${TABLES_FQN}\`
WHERE table_schema = '${NAMESPACE}'
ORDER BY table_name
"
echo

echo "== Schema =="
if [[ -n "$TABLE_NAME" ]]; then
  bq query --nouse_legacy_sql "
SELECT
  table_name,
  ordinal_position,
  column_name,
  data_type,
  is_nullable
FROM \`${COLUMNS_FQN}\`
WHERE table_schema = '${NAMESPACE}'
  AND table_name = '${TABLE_NAME}'
ORDER BY ordinal_position
"
else
  bq query --nouse_legacy_sql "
SELECT
  table_name,
  ordinal_position,
  column_name,
  data_type,
  is_nullable
FROM \`${COLUMNS_FQN}\`
WHERE table_schema = '${NAMESPACE}'
ORDER BY table_name, ordinal_position
"
fi
