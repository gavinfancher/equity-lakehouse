# Lakehouse on GCP

Initial setup using `gcloud` CLI to create a lakehouse for US equity data.


insert blurb here 


## 1. Setting environment's variables for your GCP environment

Create a project with a billing account at `console.cloud.google.com`


```bash
export PROJECT_ID="project-id"
export REGION="us-central1"
export BUCKET_NAME="your-lakehouse-bucket"
export CATALOG_NAME="${BUCKET_NAME}"
```

`REGION` should be set to your preferred region and it will be where all your storage and compute physically takes place

`BUCKET_NAME` must be globally unique among all GCP buckets

`CATALOG_NAME` the GCP docs call for catalog names to match bucket names

## 2. Enable the required APIs

```bash
gcloud config set project "${PROJECT_ID}"

gcloud services enable \
  biglake.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com
```

## 3. Create the GCS warehouse bucket

```bash
gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention
```

## 4. Create the Lakehouse Iceberg REST catalog

```bash
gcloud biglake iceberg catalogs create "${CATALOG_NAME}" \
  --project="${PROJECT_ID}" \
  --catalog-type=gcs-bucket \
  --credential-mode=vended-credentials
```

The `gcloud` CLI still uses the older `biglake` nomenclature. Do not pass `--primary-location` for a regional bucket in `us-central1`.

## 5. Grant the catalog service account bucket access

```bash
CATALOG_SA="$(
  gcloud biglake iceberg catalogs describe "${CATALOG_NAME}" \
    --project="${PROJECT_ID}" \
    --format="value(biglake-service-account)"
)"

echo "Catalog SA: ${CATALOG_SA}"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${CATALOG_SA}" \
  --role="roles/storage.objectUser"
```

The describe JSON field is `biglake-service-account`, not `biglakeServiceAccount`. If `CATALOG_SA` is empty, confirm the catalog was created with `--credential-mode=vended-credentials`.

Without this binding, vended-credentials writes fail.

## 6. Create a test namespace

```bash
NAMESPACE="test"

gcloud biglake iceberg namespaces create "${NAMESPACE}" \
  --catalog="${CATALOG_NAME}" \
  --project="${PROJECT_ID}"
```

## 7. Local auth for PyIceberg test insert script

```bash
gcloud auth application-default login
```

## 8. Insert data with PyIceberg

Tables are written via Iceberg clients (Spark, Trino, PyIceberg), read via BigQuery:

```bash
ICEBERG_BUCKET="${BUCKET_NAME}" \
ICEBERG_NAMESPACE="${NAMESPACE}" \
ICEBERG_TABLE="testingtable" \
GCP_PROJECT_ID="${PROJECT_ID}" 


uv sync
cd scripts/
uv run test_insert.py
```
