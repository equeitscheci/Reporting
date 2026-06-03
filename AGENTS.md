# AGENTS.md

Guidance for cloud agents working in this repository.

## Cursor Cloud specific instructions

### Product overview

**Insightforge** is an ERP-agnostic reporting platform (FastAPI backend + React/Vite frontend). The MVP uses an **in-memory store** with bundled sample connector data — Postgres, dbt, and Airflow are optional and not required for UI/API development.

### Services

| Service | Port | Required for dev? |
|---------|------|-------------------|
| Backend (FastAPI / Uvicorn) | 8000 | Yes |
| Frontend (Vite dev server) | 5173 | Yes (proxies `/api` → backend) |
| Postgres warehouse | 5432 | No (only for warehouse/dbt ELT path) |
| Docker Compose stack | — | No (Docker optional in cloud VMs) |

### Starting dev servers

Run backend and frontend in **separate tmux sessions** (they are long-running):

```bash
# Backend (from repo root)
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal/tmux session)
cd frontend
npm run dev -- --host 0.0.0.0
```

- Frontend dev server proxies `/api/*` to `http://localhost:8000` (see `frontend/vite.config.ts`).
- Auth is disabled by default (`INSIGHTFORGE_AUTH_DISABLED=true`). Dev requests use headers `X-Tenant-Id: acme-mfg` and `X-Roles: owner` (the frontend sets these automatically).
- Open the UI at http://localhost:5173 and API docs at http://localhost:8000/docs.

### Lint, test, and build

See `README.md` for the canonical commands. Quick reference:

| Task | Command | Directory |
|------|---------|-----------|
| Backend lint | `ruff check .` | `backend/` (venv active) |
| Backend tests | `pytest -q` | `backend/` (venv active) |
| CLI demo | `python -m app.cli demo --tenant acme-mfg` | `backend/` (venv active) |
| Frontend typecheck | `npm run typecheck` | `frontend/` |
| Frontend build | `npm run build` | `frontend/` |

**Note:** `ruff check` may report pre-existing unused-import warnings; tests should still pass.

### Python virtualenv

The backend expects a venv at `backend/.venv`. If `python3 -m venv .venv` fails with "ensurepip is not available", install the system package once (not in the update script):

```bash
sudo apt-get install -y python3.12-venv
```

### Docker Compose (optional)

`docker compose up --build` starts Postgres + backend + frontend. Docker is **not** pre-installed in all cloud VMs; prefer the native dev-server workflow above unless Docker is explicitly needed.

### Hello-world verification

After both servers are running:

1. `curl http://localhost:8000/health` → `{"status":"ok"}`
2. `curl -X POST http://localhost:8000/sync -H "X-Tenant-Id: acme-mfg" -H "X-Roles: owner"` → sync report JSON
3. Open http://localhost:5173, click **Sync ERP**, then browse **Dashboards** / **Insights**

Or run the CLI demo (no servers required): `python -m app.cli demo --tenant acme-mfg`
