# Conventions

## Tooling

| Area | Tool | Notes |
|------|------|-------|
| Python (root) | [uv](https://docs.astral.sh/uv/) | `uv sync`, `uv run …` |
| Python (ingest image) | pip in Dockerfile | Separate `cloud_run/ingest/pyproject.toml` |
| Frontend | npm + Vite | Node for `frontend/` only |
| IaC (GCP) | bash + gcloud | No Terraform in repo today |
| Orchestration | Dagster | Module `finpipe` per root `pyproject.toml` |

Python version: **>= 3.12** (root `pyproject.toml`).

## Code style

- **Python**: Prefer stdlib + existing deps; use type hints on new public functions. Follow patterns in `cloud_run/control.py` (dataclasses, explicit defaults).
- **TypeScript/React**: Functional components, hooks for side effects (`frontend/src/hooks/`). Colocate page-specific logic in pages.
- **Shell**: `set -euo pipefail`; idempotent checks before create; source `config.env`.
- **Comments**: Only for non-obvious business logic or GCP CLI gotchas — not for obvious code.

## Naming

- `finpipe` — project name (lowercase in prose/code).
- Massive API — data vendor (formerly Polygon); S3 endpoint `files.massive.com`.
- Secrets in GCP: `massive-access-key`, `massive-secret-key` (kebab-case).

## Git hygiene

- Do not commit: `sa-key.json`, `*-key.json`, `massive.env`, `ref/config.env`, `.venv/`.
- Prefer focused PRs; update `for-agents/` when behavior changes.

## Frontend deployment

- Build: `npm run build` in `frontend/`.
- Hosting: Cloudflare Pages (`frontend/wrangler.json`).
- API URL: `VITE_API_URL` (see `frontend/.env.example`).

## Agent / doc updates

When changing architecture or deployment:

1. Update the relevant `for-agents/*.md` file.
2. If recruiter-facing summary changes, update root `README.md` or `for-agents/for-recruiters.md`.
3. Keep `AGENTS.md` short — link here for detail.

## Testing

No unified test suite today. Manual checks:

- `cloud_run/test_download.py` — ingest smoke tests.
- `gcp-spark/test.py` — Spark job helpers.
- Frontend: `npm run build` for typecheck + bundle.

Add tests when touching critical paths if the change is non-trivial.
