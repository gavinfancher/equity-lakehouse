# gcp-finpipe — reproducible GCP bootstrap

Numbered scripts that provision a finpipe environment on a fresh GCP project: APIs, a single service account, GCS buckets, a BigLake Iceberg catalog, Dataproc Serverless, a VM with public SSH, Secret Manager, and a Cloud Run downloader job.

## Prereqs

- A GCP project that already exists with billing linked (create in the console).
- `gcloud` CLI authenticated as a user with project owner: `gcloud auth login`.
- `jq` installed (used by `40_lakehouse.sh`).
- An SSH public key at the path in `SSH_PUBKEY_PATH` (default `~/.ssh/macbook-pro-key.pub`).
- For `70_cloud_run.sh`: a checkout of the `finpipe` repo at `~/projects/finpipe/` (override via `FINPIPE_CLOUD_RUN_DIR`).

## Usage

1. Edit `config.env` — at minimum `PROJECT_ID`, `LAKEHOUSE_BUCKET`, `DATA_BUCKET`, `SSH_USER`, `SSH_PUBKEY_PATH`.
2. Run scripts in numeric order:

```bash
./00_project.sh         # set project + enable APIs
./10_network.sh         # firewall: tcp:22 from 0.0.0.0/0
./20_iam.sh             # create SA, grant owner, write sa-key.json
./30_storage.sh         # lakehouse + data buckets
./40_lakehouse.sh       # Iceberg catalog + bucket binding
./50_dataproc.sh        # sample Spark batch (verifies end-to-end)
./60_vm.sh              # VM with your SSH key uploaded
./80_secrets.sh massive-access-key   # before 70 if you want Cloud Run
./80_secrets.sh massive-secret-key
./70_cloud_run.sh       # build image, deploy job
```

Each script is idempotent — re-running a step that already ran is a no-op.

## Service account model

One SA (`finpipe-sa`) with `roles/owner`, doing double duty:

- **Laptop deployer** — `20_iam.sh` writes `sa-key.json`. Activate locally:
  ```bash
  export GOOGLE_APPLICATION_CREDENTIALS="$PWD/sa-key.json"
  gcloud auth activate-service-account --key-file="$PWD/sa-key.json"
  ```
- **Workload runtime** — attached to the VM, Dataproc batches, and the Cloud Run job.

For a multi-user handoff, swap `roles/owner` for the targeted role list documented in `gcp-bootstrap-plan.md`.

Note: `60_vm.sh` attaches `finpipe-sa` to the VM but uses narrow OAuth scopes (`devstorage.read_only`, etc., ported from `gcp_run.sh`). Scopes cap the SA's effective permissions on the instance regardless of IAM roles. To let the VM use the SA's full owner powers, change `--scopes=...` to `--scopes=cloud-platform`.

## SSH

`10_network.sh` opens `tcp:22` from `0.0.0.0/0`. Anyone on the internet can reach port 22, so SSH key auth is the only line of defense — never set a password on the VM account. To restrict, edit `SSH_SOURCE_RANGES` in `config.env` to your IP/32.

The VM uses project-wide SSH keys (`60_vm.sh` calls `project-info add-metadata`) and disables OS Login at the project level so metadata SSH keys are honored.

## Secrets

```bash
./80_secrets.sh <name>   # silent prompt; creates or adds a new version
```

The Cloud Run flow expects `massive-access-key` and `massive-secret-key`.

## Layout

```
config.env              # all tunables
00_project.sh           # project + APIs
10_network.sh           # SSH firewall rule
20_iam.sh               # SA + owner + key
30_storage.sh           # buckets
40_lakehouse.sh         # BigLake Iceberg catalog
50_dataproc.sh          # sample Spark batch
60_vm.sh                # VM (config from gcp_run.sh, bugs fixed)
70_cloud_run.sh         # build + deploy Cloud Run job
80_secrets.sh           # generic: ./80_secrets.sh <name>
teardown.sh             # reverse order, idempotent
gcp-spark/              # legacy Spark/Dagster code (not part of bootstrap)
finpipe-gcp-lakehouse-setup.md   # source-of-truth docs for the lakehouse
gcp-bootstrap-plan.md            # design notes
```

## Teardown

```bash
./teardown.sh
```

Prompts for the project ID to confirm. Deletes everything the scripts created and the staging bucket Dataproc auto-created.
