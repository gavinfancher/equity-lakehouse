# Common tasks

## First-time GCP setup

1. Create a GCP project with billing enabled.
2. `cp ref/config.env.example ref/config.env` — set `PROJECT_ID`, buckets, SSH user/key path.
3. Run `ref/` scripts in order (see [infra.md](infra.md)).
4. Store Massive credentials: `./ref/80_secrets.sh massive-access-key` and `massive-secret-key`.

## Run a batch ingest

**Prerequisites:** GCP ADC, Massive AWS keys in env or Secret Manager on the job.

```bash
# From repo root
uv sync
export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=…   # or source massive.env
uv run python cloud_run/control.py --year 2025
```

Optional flags: `--tasks`, `--workers`, `--project`, `--job`, bucket/prefix overrides (see `control.py` argparse).

## Run via Dagster

```bash
uv sync
dagster dev   # module finpipe per pyproject.toml
```

Asset: `ingest` in `finpipe/assets.py`.

## Deploy ingest job (CI)

Push changes under `cloud_run/ingest/` to `main`. Workflow `.github/workflows/deploy-ingest.yml` rebuilds and updates the Cloud Run Job.

Manual image build (if not using CI):

```bash
./ref/70_cloud_run.sh
```

## Submit a Dataproc Spark job

See `gcp-spark/submit_finpipe_ohlc_batch.py` and `gcp-spark/dataproc_ohlc_batch.example.json`.

Verify lakehouse connectivity:

```bash
./ref/50_dataproc.sh
```

## Query lakehouse schema

```bash
./query_lakehouse_schema.sh
```

## Frontend local dev

```bash
cd frontend
cp .env.example .env    # set VITE_API_URL if not using production API
npm install
npm run dev
```

- `/demo` — public demo WebSocket (no auth).
- `/dashboard`, `/stream` — require auth against API.

## Update agent documentation

After an architectural change:

1. Edit the relevant file in `for-agents/`.
2. If the change affects how recruiters should understand the project, update `for-agents/for-recruiters.md` and root `README.md`.
3. Keep `AGENTS.md` as index-only unless entry-point rules change.

## Teardown a GCP environment

```bash
./teardown.sh
```

Confirms project ID interactively before deleting resources.
