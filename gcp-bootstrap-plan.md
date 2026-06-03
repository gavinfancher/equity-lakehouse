# GCP Project Bootstrap — Reproducible Setup Plan

End-to-end plan for spinning up a fresh GCP project with: lakehouse (Iceberg on GCS + BigLake REST catalog), Dataproc Serverless (managed Spark), a VM with automatic SSH, GCS buckets for general data, plus the networking, IAM, and Cloud Run downloader job from `finpipe/deploy/cloud_run/`.

---

## Source material reviewed

| File | Covers | State |
|---|---|---|
| `~/finpipe-gcp-lakehouse-setup.md` | Lakehouse catalog + Dataproc Serverless batch | Correct, hand-runnable |
| `~/setup.sh` | Same as above, scripted | **Stale** — uses `--credential-mode=vending` and `--primary-location`, both wrong per the md's "gotchas" |
| `~/gcp_run.sh` | VM with project SSH key | **Broken** — missing `\` line-continuations (newlines split commands), and `$(SSH_KEY_PATH)` should be `$(cat "$SSH_KEY_PATH")` |
| `finpipe/deploy/cloud_run/REPRODUCE.md` | Cloud Run job for S3→GCS | Correct |

---

## Proposed layout

One repo (e.g. `~/projects/gcp-bootstrap/`) with a single config file and small composable scripts. Everything keys off env vars so a new project ID is a one-line change.

```
gcp-bootstrap/
  config.env                 # PROJECT_ID, REGION, ZONE, BUCKET names, SA names
  00_project.sh              # set project, link billing, enable APIs
  10_network.sh              # VPC + subnet + firewall (SSH from your IP, IAP, egress)
  20_iam.sh                  # service accounts + role bindings
  30_storage.sh              # GCS buckets (lakehouse + general data + staging)
  40_lakehouse.sh            # BigLake Iceberg catalog + bucket binding
  50_dataproc.sh             # Dataproc Serverless prereqs + sample submit
  60_vm.sh                   # VM w/ project-wide SSH key, OS Login disabled
  70_cloud_run.sh            # Artifact Registry + secrets + build + deploy job
  teardown.sh                # reverse order, idempotent
  README.md                  # "run in order, takes ~10 min"
```

---

## Step plan

### 1. `config.env` — single source of truth
`PROJECT_ID`, `REGION=us-central1`, `ZONE=us-central1-a`, `LAKEHOUSE_BUCKET`, `DATA_BUCKET`, `SA_RUNNER`, `SA_DATAPROC`, `SA_VM`, `VM_NAME`, `SSH_USER`, `SSH_KEY_PATH`. Every script does `source config.env`.

### 2. `00_project.sh` — project + APIs
- `gcloud projects create` (optional)
- `gcloud beta billing projects link`
- `gcloud config set project`
- Enable union of APIs in one call: `compute`, `storage`, `iam`, `biglake`, `dataproc`, `bigquery`, `run`, `cloudbuild`, `artifactregistry`, `secretmanager`, `logging`, `iap`
- Idempotent — `services enable` is safe to re-run

### 3. `10_network.sh` — VPC + firewall
- Create custom VPC + regional subnet (don't rely on `default`, which auto-creates a global mesh you don't want)
- Firewall rules: allow SSH (tcp:22) from `35.235.240.0/20` (IAP range) so port 22 is never exposed to the internet
- Allow internal traffic within the subnet
- Egress is open by default

### 4. `20_iam.sh` — three dedicated service accounts
- `sa-runner` (Cloud Run Job): `roles/storage.objectAdmin`, `roles/secretmanager.secretAccessor`
- `sa-dataproc` (Spark batches): `roles/dataproc.worker`, `roles/biglake.editor`, `roles/bigquery.dataEditor`, `roles/storage.objectUser`, `roles/serviceusage.serviceUsageConsumer`
- `sa-vm` (compute): `roles/storage.objectViewer`, `roles/logging.logWriter`

Use a dedicated SA per workload instead of the default compute SA. The current setup grants 5 broad roles to the default SA, which leaks to every future VM in the project.

### 5. `30_storage.sh` — buckets
- `LAKEHOUSE_BUCKET` (catalog ID == bucket name, immutable)
- `DATA_BUCKET` (raw downloads)
- Both `--uniform-bucket-level-access`, regional in `$REGION`

### 6. `40_lakehouse.sh` — BigLake Iceberg catalog
Port from the **md, not setup.sh**:
- `--credential-mode=vended-credentials`
- No `--primary-location`
- `describe --format=json`, parse `biglake-service-account` with `jq`, bind to bucket
- Avoid the bug in `setup.sh` line 51 where it parses `value(serviceAccount)` (wrong field name)

### 7. `50_dataproc.sh` — sample Spark batch
- Upload `quickstart.py` to `gs://$LAKEHOUSE_BUCKET/scripts/`
- Submit batch with `--service-account=$SA_DATAPROC --subnet=<your-subnet>`
- Move the long `--properties` blob into a `spark_props.conf` file passed via `--properties-file` so it's readable

### 8. `60_vm.sh` — VM with auto SSH
Fix the bugs in `gcp_run.sh`:
- Use real `\` line continuations
- `--metadata "ssh-keys=${SSH_USER}:$(cat "$SSH_KEY_PATH")"`
- Attach `--service-account=$SA_VM`, `--subnet=<your-subnet>`
- Either `--no-address` (IAP-only SSH via `gcloud compute ssh --tunnel-through-iap`) or keep external IP firewalled to your IP
- Print both the `gcloud compute ssh` command and the raw `ssh user@ip` command

### 9. `70_cloud_run.sh` — Massive S3 → GCS downloader
Lift directly from `REPRODUCE.md` steps 4–8:
- Create Artifact Registry repo
- Prompt for + store the two Massive secrets
- `gcloud builds submit` from `finpipe/deploy/cloud_run/`
- `gcloud run jobs create` bound to `sa-runner` with secret env mounts
- Parameterize image tag so re-runs replace `:latest`

### 10. `teardown.sh`
- Reverse order, each step `|| true` so partial state still tears down
- Includes the auto-created `dataproc-staging-*` bucket grep from the md

---

## Tradeoffs to decide before building

### Default VPC vs custom VPC
Custom is cleaner and lets you use IAP-only SSH (no public IP), but adds ~30 lines and means you must pass `--subnet` everywhere. If keeping `default` for now, `10_network.sh` becomes just firewall rule edits.

### Bash scripts vs Terraform
Scripts match what you have today and read top-to-bottom. Terraform would give real idempotence and a state file but is a bigger lift. Recommend starting with bash and only porting to TF if running in CI.
