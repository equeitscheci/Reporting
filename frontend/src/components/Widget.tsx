import type { WidgetResult } from "../types";
import { BarChart, DataTable, KpiTile, LineChart } from "./Charts";

export function Widget({ w }: { w: WidgetResult }) {
  if (w.error) {
    return (
      <div className="widget widget-error">
        <div className="widget-title">{w.title}</div>
        <div className="empty">⚠ {w.error}</div>
      </div>
    );
  }

  if (w.type === "kpi") {
    const value = Number(w.data?.[0]?.value ?? 0);
    return (
      <div className="widget widget-kpi">
        <KpiTile value={value} unit={w.unit} label={w.title} />
      </div>
    );
  }

  const body =
    w.type === "line" ? (
      <LineChart rows={w.data} dimensions={w.dimensions} unit={w.unit} />
    ) : w.type === "bar" ? (
      <BarChart rows={w.data} dimensions={w.dimensions} unit={w.unit} />
    ) : (
      <DataTable rows={w.data} dimensions={w.dimensions} unit={w.unit} />
    );

  return (
    <div className="widget">
      <div className="widget-title">{w.title}</div>
      {body}
    </div>
  );
}
