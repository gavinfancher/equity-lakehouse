# Data model

## Massive flatfiles (source)

Historical equity minute aggregates arrive as `.csv.gz` under keys like:

```
us_stocks_sip/minute_aggs_v1/2021/05/2021-05-01.csv.gz
```

Listed by `cloud_run/get_keys.py` from the Massive S3-compatible endpoint (`files.massive.com`).

## GCS staging (dest)

`cloud_run/ingest/main.py` remaps keys to Hive-style paths:

```
lakehouse-staging/equity_min_aggs/year=2021/2021-05-01.csv.gz
```

Defaults in `cloud_run/control.py` (override via CLI/Dagster config):

| Setting | Default |
|---------|---------|
| `DEST_BUCKET` | `finpipe-bucket-01` |
| `DEST_PREFIX` | `lakehouse-staging/equity_min_aggs/` |
| `MANIFEST_BUCKET` | same as dest |
| `MANIFEST_PREFIX` | `_manifests/` |

Manifest JSON shape (written by `control.py`):

```json
{
  "run_id": "uuid",
  "source_bucket": "…",
  "dest_bucket": "…",
  "dest_prefix": "…",
  "task_count": 10,
  "tasks": { "0": ["key1", "…"], "1": ["…"] }
}
```

## Minute bar schema (Spark jobs)

`gcp-spark/finpipe_ohlc_job.py` expects CSV columns:

| Column | Role |
|--------|------|
| `ticker` | Symbol |
| `volume`, `open`, `close`, `high`, `low` | OHLCV |
| `window_start` | Bar timestamp |
| `transactions` | Trade count |

## Iceberg / lakehouse

- **Catalog**: BigLake Iceberg; catalog name **must equal** the GCS bucket name (immutable after create).
- **Credential mode**: `vended-credentials` (not `vending`).
- **Query**: BigQuery via Lakehouse runtime catalog binding.

Operational setup steps: [finpipe-gcp-lakehouse-setup.md](../finpipe-gcp-lakehouse-setup.md).

Partition strategy for committed tables (from learn docs, target design): `(date, ticker)` for partition pruning on symbol + date range queries.

## Streaming cache (external API)

Not stored in this repo. Documented convention in learn content:

- One Redis hash per ticker (~20 fields): last price, daily change, performance windows (5d, 1m, 3m, 6m, 1y, YTD, 3y), reference closes for live recomputation.

Frontend types in `frontend/src/types.ts` reflect the WebSocket payload shape.
