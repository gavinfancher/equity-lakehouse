# Finpipe GCP Lakehouse Setup
### Iceberg on GCS + BigQuery via Lakehouse Runtime Catalog

---

## Prerequisites

- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- Billing enabled on `finpipe-494623`
- `gcloud components update` run to ensure latest CLI

---

## Step 1: Set Project & Enable APIs

```bash
gcloud config set project finpipe-494623

gcloud services enable \
  biglake.googleapis.com \
  dataproc.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com
```

---

## Step 2: Grant IAM Roles to Default Compute SA

```bash
PROJECT_NUMBER=$(gcloud projects describe finpipe-494623 --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "SA: $SA"

for ROLE in \
  roles/dataproc.worker \
  roles/serviceusage.serviceUsageConsumer \
  roles/biglake.editor \
  roles/bigquery.dataEditor \
  roles/storage.objectUser; do
  gcloud projects add-iam-policy-binding finpipe-494623 \
    --member="serviceAccount:$SA" \
    --role="$ROLE" \
    --quiet
  echo "granted $ROLE"
done
```

---

## Step 3: Create GCS Bucket

The bucket name becomes the catalog ID — they must match and cannot be changed later.

```bash
gcloud storage buckets create gs://finpipe-lakehouse \
  --location=us-central1 \
  --project=finpipe-494623 \
  --uniform-bucket-level-access
```

---

## Step 4: Create Lakehouse Runtime Catalog

> **Note:** The CLI command group is `gcloud biglake iceberg catalogs` (not `gcloud biglake catalogs`).  
> There is no `--location` or `--primary-location` flag — the catalog is global.  
> The correct `--credential-mode` value is `vended-credentials` (not `vending`).

```bash
gcloud biglake iceberg catalogs create finpipe-lakehouse \
  --project=finpipe-494623 \
  --catalog-type=gcs-bucket \
  --credential-mode=vended-credentials
```

---

## Step 5: Grant Catalog Service Account Access to Bucket

First, get the catalog's managed service account. The field is `biglake-service-account` in the JSON output:

```bash
gcloud biglake iceberg catalogs describe finpipe-lakehouse \
  --project=finpipe-494623 \
  --format=json
```

Then grant it access (substituting your actual SA value):

```bash
# From the describe output above, copy the biglake-service-account value
CATALOG_SA="blirc-1075318952714-cpd2@gcp-sa-biglakerestcatalog.iam.gserviceaccount.com"

gcloud storage buckets add-iam-policy-binding gs://finpipe-lakehouse \
  --member="serviceAccount:$CATALOG_SA" \
  --role="roles/storage.objectUser"
```

---

## Step 6: Create & Upload PySpark Script

> **Note:** Do not use `.show()` to verify data in Spark — it triggers a broadcast of the `GCSFileIO` object which fails with a `NotSerializableException` on `OAuth2RefreshCredentialsHandler`. Use `.collect()` instead.

```bash
cat > /tmp/quickstart.py << 'EOF'
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("finpipe-lakehouse-init").getOrCreate()

CATALOG = "finpipe_catalog"
NS      = "market_data"

spark.sql(f"CREATE NAMESPACE IF NOT EXISTS `{CATALOG}`.{NS}")
print(f"Created namespace: {NS}")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS `{CATALOG}`.{NS}.trades (
        ts         TIMESTAMP,
        symbol     STRING,
        price      DOUBLE,
        size       BIGINT,
        conditions STRING
    )
    USING iceberg
    PARTITIONED BY (symbol, days(ts))
""")
print("Created table: trades")

spark.sql(f"""
    INSERT INTO `{CATALOG}`.{NS}.trades VALUES
        (TIMESTAMP '2024-01-15 09:30:00', 'AAPL', 185.50, 100, 'O'),
        (TIMESTAMP '2024-01-15 09:30:01', 'AAPL', 185.55, 250, ''),
        (TIMESTAMP '2024-01-15 09:30:02', 'NVDA', 495.10, 50,  'O')
""")
print("Inserted sample rows")

# Use collect() not show() — show() causes NotSerializableException with vended credentials
rows = spark.sql(f"SELECT * FROM `{CATALOG}`.{NS}.trades").collect()
for row in rows:
    print(row)

print("Done.")
EOF

gcloud storage cp /tmp/quickstart.py gs://finpipe-lakehouse/scripts/quickstart.py
```

---

## Step 7: Submit Dataproc Serverless Batch Job

```bash
gcloud dataproc batches submit pyspark gs://finpipe-lakehouse/scripts/quickstart.py \
  --project=finpipe-494623 \
  --region=us-central1 \
  --version=2.2 \
  --properties="\
spark.sql.defaultCatalog=finpipe_catalog,\
spark.sql.catalog.finpipe_catalog=org.apache.iceberg.spark.SparkCatalog,\
spark.sql.catalog.finpipe_catalog.type=rest,\
spark.sql.catalog.finpipe_catalog.uri=https://biglake.googleapis.com/iceberg/v1/restcatalog,\
spark.sql.catalog.finpipe_catalog.warehouse=gs://finpipe-lakehouse,\
spark.sql.catalog.finpipe_catalog.io-impl=org.apache.iceberg.gcp.gcs.GCSFileIO,\
spark.sql.catalog.finpipe_catalog.header.x-goog-user-project=finpipe-494623,\
spark.sql.catalog.finpipe_catalog.rest.auth.type=org.apache.iceberg.gcp.auth.GoogleAuthManager,\
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions,\
spark.sql.catalog.finpipe_catalog.header.X-Iceberg-Access-Delegation=vended-credentials,\
spark.sql.catalog.finpipe_catalog.gcs.oauth2.refresh-credentials-endpoint=https://oauth2.googleapis.com/token"
```

This takes a few minutes to spin up. When complete you'll see the 3 sample rows printed in the batch logs.

---

## Step 8: Query from BigQuery

BigQuery uses a 4-part `project.catalog.namespace.table` syntax — no table registration required.

```sql
SELECT *
FROM `finpipe-494623.finpipe-lakehouse.market_data.trades`
WHERE symbol = 'AAPL';
```

Run via CLI:

```bash
bq query --nouse_legacy_sql \
  "SELECT * FROM \`finpipe-494623.finpipe-lakehouse.market_data.trades\` LIMIT 10"
```

---

## Reference: Naming & Architecture

| Component | Value |
|---|---|
| GCP Project | `finpipe-494623` |
| GCS Bucket / Catalog ID | `finpipe-lakehouse` |
| Namespace | `market_data` |
| REST Catalog URI | `https://biglake.googleapis.com/iceberg/v1/restcatalog` |
| BigQuery query syntax | `finpipe-494623.finpipe-lakehouse.market_data.<table>` |

### How it fits together

```
PySpark (Dataproc Serverless)
        │  writes via REST catalog
        ▼
Lakehouse Runtime Catalog  ──────────────────────────────┐
(biglake.googleapis.com)                                  │ metadata
        │  manages metadata                               │
        ▼                                                 ▼
GCS gs://finpipe-lakehouse              BigQuery
(Parquet + Iceberg metadata)    queries via 4-part P.C.N.T syntax
```

---

## Common Gotchas

| Error | Fix |
|---|---|
| `Invalid choice: 'catalogs'` | Use `gcloud biglake iceberg catalogs`, not `gcloud biglake catalogs` |
| `Invalid choice: 'vending'` | Use `--credential-mode=vended-credentials` |
| `unrecognized arguments: --primary-location` | Drop the flag — catalog is global, no location needed |
| `Invalid service account ()` | The field is `biglake-service-account` in describe JSON, not `serviceAccount` |
| `NotSerializableException: OAuth2RefreshCredentialsHandler` | Use `.collect()` not `.show()` when reading back data in Spark |
| Only some partitions visible in BigQuery | Use `ORDER BY` with no `WHERE` clause to force a full scan |

---

## Teardown

Run these commands to delete all resources and stop incurring charges. **This is destructive and irreversible.**

### Step 1: Drop Iceberg tables and namespace via Spark

```bash
cat > /tmp/teardown.py << 'EOF'
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("finpipe-lakehouse-teardown").getOrCreate()

CATALOG = "finpipe_catalog"
NS      = "market_data"

spark.sql(f"DROP TABLE IF EXISTS `{CATALOG}`.{NS}.trades")
print("Dropped table: trades")

spark.sql(f"DROP NAMESPACE IF EXISTS `{CATALOG}`.{NS}")
print(f"Dropped namespace: {NS}")

print("Done.")
EOF

gcloud storage cp /tmp/teardown.py gs://finpipe-lakehouse/scripts/teardown.py

gcloud dataproc batches submit pyspark gs://finpipe-lakehouse/scripts/teardown.py \
  --project=finpipe-494623 \
  --region=us-central1 \
  --version=2.2 \
  --properties="\
spark.sql.defaultCatalog=finpipe_catalog,\
spark.sql.catalog.finpipe_catalog=org.apache.iceberg.spark.SparkCatalog,\
spark.sql.catalog.finpipe_catalog.type=rest,\
spark.sql.catalog.finpipe_catalog.uri=https://biglake.googleapis.com/iceberg/v1/restcatalog,\
spark.sql.catalog.finpipe_catalog.warehouse=gs://finpipe-lakehouse,\
spark.sql.catalog.finpipe_catalog.io-impl=org.apache.iceberg.gcp.gcs.GCSFileIO,\
spark.sql.catalog.finpipe_catalog.header.x-goog-user-project=finpipe-494623,\
spark.sql.catalog.finpipe_catalog.rest.auth.type=org.apache.iceberg.gcp.auth.GoogleAuthManager,\
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions,\
spark.sql.catalog.finpipe_catalog.header.X-Iceberg-Access-Delegation=vended-credentials,\
spark.sql.catalog.finpipe_catalog.gcs.oauth2.refresh-credentials-endpoint=https://oauth2.googleapis.com/token"
```

### Step 2: Delete the Lakehouse catalog

```bash
gcloud biglake iceberg catalogs delete finpipe-lakehouse \
  --project=finpipe-494623
```

### Step 3: Delete the GCS bucket and all contents

```bash
gcloud storage rm -r gs://finpipe-lakehouse
```

### Step 4: Delete the Dataproc staging bucket (auto-created)

```bash
# List staging buckets to find the one created by Dataproc
gcloud storage ls --project=finpipe-494623 | grep dataproc-staging

# Delete it (substitute the actual bucket name)
gcloud storage rm -r gs://dataproc-staging-us-central1-<PROJECT_NUMBER>-<SUFFIX>
```

### Step 5: Revoke IAM roles (optional)

Only needed if you want to fully clean up the compute SA permissions:

```bash
PROJECT_NUMBER=$(gcloud projects describe finpipe-494623 --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for ROLE in \
  roles/dataproc.worker \
  roles/serviceusage.serviceUsageConsumer \
  roles/biglake.editor \
  roles/bigquery.dataEditor \
  roles/storage.objectUser; do
  gcloud projects remove-iam-policy-binding finpipe-494623 \
    --member="serviceAccount:$SA" \
    --role="$ROLE" \
    --quiet
  echo "revoked $ROLE"
done
```
