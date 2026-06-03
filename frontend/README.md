# Insightforge Frontend

React + TypeScript + Vite UI: prebuilt industry dashboards, a drag-and-drop report builder, and an
insights/NLQ panel. Charts are dependency-light inline SVG components.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api → http://localhost:8000)
npm run build      # type-check + production build
```

Run the backend (`uvicorn app.main:app` in `../backend`) first, then click **Sync ERP** in the UI to
load the sample tenant.

## Structure
- `dashboards/*.json` — prebuilt dashboard configs (the same report-spec shape the backend executes).
- `src/components/Dashboard.tsx` — loads a dashboard config and renders it via `/reports/run`.
- `src/builder/ReportBuilder.tsx` — drag a metric → choose dims/viz → run; emits a report-spec JSON.
- `src/components/Insights.tsx` — automated insights + natural-language query box.
- `src/components/Charts.tsx` — line/bar/KPI/table SVG renderers.
- `src/api.ts` — typed API client (tenant-scoped headers).
