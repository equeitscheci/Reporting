export type Unit = "currency" | "percent" | "number" | "days" | "ratio";

export interface MetricDef {
  name: string;
  label: string;
  description: string;
  fact: string;
  unit: Unit;
  agg: string;
  industry: string | null;
}

export interface MetricRow {
  value: number;
  [dimension: string]: number | string | null;
}

export interface MetricResult {
  metric: string;
  label: string;
  unit: Unit;
  dimensions: string[];
  rows: MetricRow[];
}

export type WidgetType = "kpi" | "line" | "bar" | "table";

export interface WidgetSpec {
  id: string;
  type: WidgetType;
  title?: string;
  metric: string;
  dimensions?: string[];
  filters?: Record<string, unknown>;
  order_by?: string;
  limit?: number;
  grid?: { x: number; y: number; w: number; h: number };
}

export interface DashboardSpec {
  id: string;
  title: string;
  industry?: string;
  note?: string;
  filters?: Record<string, unknown>;
  layout?: { columns: number };
  widgets: WidgetSpec[];
}

export interface WidgetResult {
  id: string;
  type: WidgetType;
  title: string;
  metric: string;
  unit: Unit;
  dimensions: string[];
  data: MetricRow[];
  error?: string;
}

export interface ReportResult {
  title: string;
  widgets: WidgetResult[];
}

export interface Insight {
  id: string;
  kind: "anomaly" | "forecast" | "trend";
  title: string;
  severity: "info" | "warning" | "critical";
  metric: string;
  explanation: string;
  evidence: Array<Record<string, unknown>>;
  recommended_actions: string[];
}

export interface NLAnswer {
  question: string;
  resolved_query: { metric: string; dimensions: string[]; filters: Record<string, unknown>; intent: string };
  answer: string;
  data: MetricRow[];
  explanation: string;
}
