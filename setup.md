# Lakehouse on GCP

Initial setup using `gcloud` to create a lakehouse for US equity data.


insert blerb here 


## 1. Setting environment's variables for your GCP environment

Create a project with a billing account on `console.cloud.google.com`


```bash
export PROJECT_ID="project-id"
export REGION="us-central1"
export BUCKET_NAME="your-lakehouse-bucket"
export CATALOG_NAME="${BUCKET_NAME}"
```

`REGION` should be set to your preferred region and it will be where all your storage and compute physically takes place

`BUCKET_NAME` must be globally unique amungst all GCP users

`CATALOG_NAME` the GCP docs call for catalog names to match bucket names

## 2. Enable the required APIs
```bash
gcloud config set project "${PROJECT_ID}"

gcloud services enable \
  biglake.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com
```

## 2. Create the GCS warehouse bucket

```bash
gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention
```

## 3. Create the Lakehouse Iceberg REST catalog

```bash
gcloud biglake iceberg catalogs create "${CATALOG_NAME}" \
  --project="${PROJECT_ID}" \
  --catalog-type=gcs-bucket \
  --credential-mode=vended-credentials \
  --primary-location="${REGION}"
```
The `gcloud` cli still uses the older `biglake` nomeclature

## 4. Grant the catalog service account bucket access

```bash
CATALOG_SA="$(
  gcloud biglake iceberg catalogs describe "${CATALOG_NAME}" \
    --project="${PROJECT_ID}" \
    --format="value(biglakeServiceAccount)"
)"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${CATALOG_SA}" \
  --role="roles/storage.objectUser"
```

Without this, vended-credentials writes fail.

## 5. Create a namespace (Iceberg “schema”)

```bash
gcloud biglake iceberg namespaces create analytics \
  --catalog="${CATALOG_NAME}" \
  --project="${PROJECT_ID}"
```

## 6. Local auth for PyIceberg / scripts

```bash
gcloud auth application-default login
```

## 7. Insert data (not via BigQuery DML)

REST catalog tables are **write via Iceberg clients**, **read via BigQuery**:

```bash
cd /path/to/equity-lakehouse
uv sync

ICEBERG_BUCKET="${BUCKET_NAME}" \
ICEBERG_NAMESPACE="analytics" \
ICEBERG_TABLE="events" \
GCP_PROJECT_ID="${PROJECT_ID}" \
uv run python -m equity_lakehouse.insert_sample
```

Adjust the script if the table does not exist yet — create it first via PyIceberg `create_table` or Spark.

## 8. Query from BigQuery (read-only analytics)

```sql
SELECT * FROM `PROJECT_ID.CATALOG_NAME.analytics.events`;
```

Example:

```sql
SELECT * FROM `your-new-project.your-lakehouse-bucket.analytics.events`;
```

---

## IAM

Whoever runs setup needs roughly:

- `roles/biglake.admin`
- `roles/storage.admin`
- `roles/bigquery.admin` (if using BigQuery)

---

## Optional: BigQuery-native read and write

If you want `INSERT` / `CREATE VIEW` in BigQuery (not just PCNT reads on REST catalog tables):

```bash
# BigQuery connection to GCS
bq mk --connection --location=US --project_id="${PROJECT_ID}" \
  --connection_type=CLOUD_RESOURCE lakehouse-conn

CONN_SA="$(
  bq show --format=prettyjson --connection "${PROJECT_ID}.US.lakehouse-conn" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['cloudResource']['serviceAccountId'])"
)"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${CONN_SA}" \
  --role="roles/storage.objectUser"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${CONN_SA}" \
  --role="roles/storage.legacyBucketReader"

bq query --use_legacy_sql=false "
CREATE SCHEMA IF NOT EXISTS \`${PROJECT_ID}.equity\`;

CREATE TABLE \`${PROJECT_ID}.equity.transactions\` (
  id INT64,
  symbol STRING,
  amount FLOAT64
)
WITH CONNECTION \`${PROJECT_ID}.US.lakehouse-conn\`
OPTIONS (
  file_format = 'PARQUET',
  table_format = 'ICEBERG',
  storage_uri = 'gs://${BUCKET_NAME}/equity/transactions/'
);
"
```

Then normal BigQuery SQL works:

```sql
INSERT INTO `your-new-project.equity.transactions` VALUES (1, 'AAPL', 100.5);
SELECT * FROM `your-new-project.equity.transactions`;
```

---

## Verify

```bash
gcloud biglake iceberg catalogs list --project="${PROJECT_ID}"
gcloud biglake iceberg catalogs describe "${CATALOG_NAME}" --project="${PROJECT_ID}"
gcloud biglake iceberg namespaces list --catalog="${CATALOG_NAME}" --project="${PROJECT_ID}"
```

```bash
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${PROJECT_ID}.${CATALOG_NAME}.analytics.events\`"
```
