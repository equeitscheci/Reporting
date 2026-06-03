# AGENTS.md

Guidance for cloud agents working in this repository.

## Cursor Cloud environment

Insightforge is a FastAPI backend plus a React/Vite frontend. The app code lives on the
Insightforge app branch that contains `backend/` and `frontend/`; the initial `main` branch may
only contain the repository skeleton.

Use this install command in Cursor Cloud:

```bash
bash scripts/cursor-cloud-install.sh
```

The install script is branch-safe:

- It starts from `/workspace`.
- If `backend/` or `frontend/` is missing, it prints a message and exits successfully.
- If both directories exist, it creates `backend/.venv`, runs `pip install -e ".[dev]"`, and runs
  `npm ci` in `frontend/`.

Do not rely on Docker for the default cloud workflow. Docker Compose is optional and should only be
used if the base image is updated to include Docker and Compose.

## Native dev servers

Run backend and frontend in separate long-running sessions:

```bash
cd /workspace/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd /workspace/frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

- UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

The Vite dev server proxies `/api/*` to `http://localhost:8000`.

## Verification

```bash
cd /workspace/backend
.venv/bin/pytest -q

cd /workspace/frontend
npm run build
```

Seed the demo tenant when you need dashboard/insight data:

```bash
curl -X POST http://localhost:8000/sync \
  -H "X-Tenant-Id: acme-mfg" \
  -H "X-Roles: owner"
```
