import google.auth
import google.auth.transport.requests
from google.auth import impersonated_credentials
from pyiceberg.catalog.rest import RestCatalog

source, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
credentials = impersonated_credentials.Credentials(
    source_credentials=source,
    target_principal="finpipe-iceberg-reader@finpipe-494623.iam.gserviceaccount.com",
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
credentials.refresh(google.auth.transport.requests.Request())

catalog = RestCatalog(
    name="finpipe_catalog",
    **{
        "uri": "https://biglake.googleapis.com/iceberg/v1/restcatalog",
        "warehouse": "gs://finpipe-lakehouse",
        "token": credentials.token,
        "header.x-goog-user-project": "finpipe-494623",
        "header.X-Iceberg-Access-Delegation": "vended-credentials",
    }
)

table = catalog.load_table("market_data.trades")

import pyarrow as pa
from datetime import datetime, timezone

new_rows = pa.table({
    "ts": pa.array(
        [datetime(2024, 1, 15, 9, 30, 3, tzinfo=timezone.utc),
         datetime(2024, 1, 15, 9, 30, 4, tzinfo=timezone.utc),
         datetime(2024, 1, 15, 9, 30, 5, tzinfo=timezone.utc)],
        type=pa.timestamp("us", tz="UTC"),
    ),
    "symbol": ["AAPL", "MSFT", "GOOG"],
    "price": [186.10, 410.25, 142.80],
    "size": [500, 150, 75],
    "conditions": ["", "O", ""],
}, schema=table.schema().as_arrow())

table.append(new_rows)

df = table.scan().to_pandas()
print(df)
