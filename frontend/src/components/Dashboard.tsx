import { useEffect, useState } from "react";
import { api, loadDashboard } from "../api";
import type { DashboardSpec, ReportResult } from "../types";
import { Widget } from "./Widget";

const DASHBOARDS = [
  { key: "manufacturing", label: "Manufacturing" },
  { key: "distribution", label: "Distribution" },
  { key: "construction", label: "Construction" },
  { key: "executive", label: "Executive" },
];

export function Dashboard() {
  const [selected, setSelected] = useState("manufacturing");
  const [spec, setSpec] = useState<DashboardSpec | null>(null);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const dashboard = await loadDashboard(selected);
        const res = await api.runReport({
          title: dashboard.title,
          filters: dashboard.filters,
          widgets: dashboard.widgets,
        });
        if (active) {
          setSpec(dashboard);
          setResult(res);
        }
      } catch (e) {
        if (active) setError(String(e));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [selected]);

  return (
    <div>
      <div className="tabs">
        {DASHBOARDS.map((d) => (
          <button
            key={d.key}
            className={`tab ${selected === d.key ? "active" : ""}`}
            onClick={() => setSelected(d.key)}
          >
            {d.label}
          </button>
        ))}
      </div>

      {spec?.note && <div className="note">ℹ {spec.note}</div>}
      {loading && <div className="loading">Loading dashboard…</div>}
      {error && <div className="empty">⚠ {error}</div>}

      {result && (
        <>
          <h2 className="dash-title">{result.title}</h2>
          <div className="grid">
            {result.widgets.map((w) => {
              const widget = spec?.widgets.find((x) => x.id === w.id);
              const span = widget?.grid?.w ?? 4;
              return (
                <div key={w.id} style={{ gridColumn: `span ${span}` }}>
                  <Widget w={w} />
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
