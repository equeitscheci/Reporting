import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { MetricDef, WidgetResult, WidgetType } from "../types";
import { Widget } from "../components/Widget";

const DIMENSIONS = ["month", "customer_name", "region", "segment", "product_group"];
const CHART_TYPES: WidgetType[] = ["line", "bar", "kpi", "table"];

// Drag-and-drop report builder: drag a metric onto the canvas, pick dimensions/viz, run.
export function ReportBuilder() {
  const [metrics, setMetrics] = useState<MetricDef[]>([]);
  const [metric, setMetric] = useState<string | null>(null);
  const [dims, setDims] = useState<string[]>(["month"]);
  const [type, setType] = useState<WidgetType>("line");
  const [result, setResult] = useState<WidgetResult | null>(null);
  const [savedSpec, setSavedSpec] = useState<string>("");

  useEffect(() => {
    api.listMetrics().then(setMetrics).catch(() => setMetrics([]));
  }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.getData("metric");
    if (dropped) setMetric(dropped);
  };

  const toggleDim = (d: string) =>
    setDims((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]));

  const spec = useMemo(
    () =>
      metric
        ? {
            id: "builder",
            type,
            title: metrics.find((m) => m.name === metric)?.label ?? metric,
            metric,
            dimensions: type === "kpi" ? [] : dims,
            order_by: type === "bar" ? "value" : undefined,
            limit: type === "bar" ? 12 : undefined,
          }
        : null,
    [metric, dims, type, metrics]
  );

  const run = async () => {
    if (!spec) return;
    const res = await api.runReport({ title: "Ad-hoc report", widgets: [spec] });
    setResult(res.widgets[0]);
    setSavedSpec(JSON.stringify({ title: "Ad-hoc report", widgets: [spec] }, null, 2));
  };

  return (
    <div className="builder">
      <aside className="palette">
        <h3>Metrics</h3>
        <p className="hint">Drag a metric to the canvas →</p>
        {metrics.map((m) => (
          <div
            key={m.name}
            className="chip"
            draggable
            onDragStart={(e) => e.dataTransfer.setData("metric", m.name)}
            title={m.description}
          >
            {m.label}
            <span className="chip-unit">{m.unit}</span>
          </div>
        ))}
      </aside>

      <section className="canvas" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
        {!metric ? (
          <div className="dropzone">Drop a metric here to start building</div>
        ) : (
          <>
            <div className="controls">
              <div>
                <label>Metric</label>
                <select value={metric} onChange={(e) => setMetric(e.target.value)}>
                  {metrics.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Visualization</label>
                <select value={type} onChange={(e) => setType(e.target.value as WidgetType)}>
                  {CHART_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div className="dims">
                <label>Dimensions</label>
                <div>
                  {DIMENSIONS.map((d) => (
                    <button
                      key={d}
                      className={`pill ${dims.includes(d) ? "on" : ""}`}
                      disabled={type === "kpi"}
                      onClick={() => toggleDim(d)}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
              <button className="run" onClick={run}>
                Run
              </button>
            </div>

            {result && (
              <div className="result">
                <Widget w={result} />
              </div>
            )}

            {savedSpec && (
              <details className="spec">
                <summary>Report spec JSON (saved per tenant)</summary>
                <pre>{savedSpec}</pre>
              </details>
            )}
          </>
        )}
      </section>
    </div>
  );
}
