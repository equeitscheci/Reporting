import type {
  DashboardSpec,
  Insight,
  MetricDef,
  MetricResult,
  NLAnswer,
  ReportResult,
  WidgetSpec,
} from "./types";

// All requests are tenant-scoped via headers. In production these come from the auth session;
// in dev the backend accepts X-Tenant-Id / X-Roles directly.
const TENANT = localStorage.getItem("tenant") ?? "acme-mfg";

function headers(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Tenant-Id": TENANT,
    "X-Roles": "owner",
  };
}

const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: headers(), ...init });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  return (await res.json()) as T;
}

export const api = {
  tenant: TENANT,

  runSync: () => req<{ reports: unknown[] }>("/sync", { method: "POST" }),

  listMetrics: () => req<{ metrics: MetricDef[] }>("/metrics").then((r) => r.metrics),

  queryMetric: (body: {
    metric: string;
    dimensions?: string[];
    filters?: Record<string, unknown>;
    order_by?: string;
    limit?: number;
  }) =>
    req<MetricResult>("/metrics/query", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  runReport: (spec: { title: string; filters?: Record<string, unknown>; widgets: WidgetSpec[] }) =>
    req<ReportResult>("/reports/run", {
      method: "POST",
      body: JSON.stringify({ spec }),
    }),

  insights: () => req<{ insights: Insight[] }>("/insights").then((r) => r.insights),

  ask: (question: string) =>
    req<NLAnswer>("/insights/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
};

// Prebuilt dashboards are bundled JSON (the same shape the backend report runner executes).
export async function loadDashboard(name: string): Promise<DashboardSpec> {
  const mod = await import(`../dashboards/${name}.json`);
  return mod.default as DashboardSpec;
}
