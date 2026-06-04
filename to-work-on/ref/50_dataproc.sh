#!/usr/bin/env bash
# Upload a sample PySpark script and submit a Dataproc Serverless batch
# that creates a namespace + table and reads back rows. Verifies end-to-end:
# Spark -> BigLake REST catalog -> GCS Iceberg -> back through Spark.
set -euo pipefail
source "$(dirname "$0")/config.env"

SCRIPT=/tmp/quickstart.py
cat > "$SCRIPT" <<EOF
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("finpipe-lakehouse-init").getOrCreate()

CATALOG = "${SPARK_CATALOG}"
NS = "market_data"

spark.sql(f"CREATE NAMESPACE IF NOT EXISTS \`{CATALOG}\`.{NS}")
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS \`{CATALOG}\`.{NS}.trades (
        ts TIMESTAMP, symbol STRING, price DOUBLE, size BIGINT, conditions STRING
    ) USING iceberg PARTITIONED BY (symbol, days(ts))
""")
spark.sql(f"""
    INSERT INTO \`{CATALOG}\`.{NS}.trades VALUES
        (TIMESTAMP '2024-01-15 09:30:00', 'AAPL', 185.50, 100, 'O'),
        (TIMESTAMP '2024-01-15 09:30:01', 'AAPL', 185.55, 250, ''),
        (TIMESTAMP '2024-01-15 09:30:02', 'NVDA', 495.10, 50,  'O')
""")

# .show() triggers NotSerializableException with vended credentials — use .collect()
for row in spark.sql(f"SELECT * FROM \`{CATALOG}\`.{NS}.trades").collect():
    print(row)
EOF

gcloud storage cp "$SCRIPT" "gs://${LAKEHOUSE_BUCKET}/scripts/quickstart.py"

PROPS="\
spark.sql.defaultCatalog=${SPARK_CATALOG},\
spark.sql.catalog.${SPARK_CATALOG}=org.apache.iceberg.spark.SparkCatalog,\
spark.sql.catalog.${SPARK_CATALOG}.type=rest,\
spark.sql.catalog.${SPARK_CATALOG}.uri=https://biglake.googleapis.com/iceberg/v1/restcatalog,\
spark.sql.catalog.${SPARK_CATALOG}.warehouse=gs://${LAKEHOUSE_BUCKET},\
spark.sql.catalog.${SPARK_CATALOG}.io-impl=org.apache.iceberg.gcp.gcs.GCSFileIO,\
spark.sql.catalog.${SPARK_CATALOG}.header.x-goog-user-project=${PROJECT_ID},\
spark.sql.catalog.${SPARK_CATALOG}.rest.auth.type=org.apache.iceberg.gcp.auth.GoogleAuthManager,\
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions,\
spark.sql.catalog.${SPARK_CATALOG}.header.X-Iceberg-Access-Delegation=vended-credentials,\
spark.sql.catalog.${SPARK_CATALOG}.gcs.oauth2.refresh-credentials-endpoint=https://oauth2.googleapis.com/token"

gcloud dataproc batches submit pyspark "gs://${LAKEHOUSE_BUCKET}/scripts/quickstart.py" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --version=2.2 \
  --service-account="$SA_EMAIL" \
  --properties="$PROPS"
