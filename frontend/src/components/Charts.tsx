import type { MetricRow, Unit } from "../types";
import { dimLabel, formatValue } from "../format";

const PALETTE = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6"];

interface ChartProps {
  rows: MetricRow[];
  dimensions: string[];
  unit: Unit;
}

export function LineChart({ rows, dimensions, unit }: ChartProps) {
  const w = 520;
  const h = 240;
  const pad = { l: 56, r: 16, t: 16, b: 36 };
  const data = [...rows].sort((a, b) =>
    String(a[dimensions[0]]).localeCompare(String(b[dimensions[0]]))
  );
  if (data.length === 0) return <Empty />;
  const values = data.map((r) => Number(r.value));
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const x = (i: number) => pad.l + (data.length === 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
  const y = (v: number) => pad.t + innerH - ((v - min) / span) * innerH;

  const path = data.map((r, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(Number(r.value))}`).join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart" role="img">
      {[0, 0.5, 1].map((t) => {
        const v = min + t * span;
        const yy = y(v);
        return (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={yy} y2={yy} stroke="#1e293b" strokeDasharray="3 3" />
            <text x={8} y={yy + 4} className="axis">{formatValue(v, unit)}</text>
          </g>
        );
      })}
      <path d={path} fill="none" stroke={PALETTE[0]} strokeWidth={2.5} />
      {data.map((r, i) => (
        <circle key={i} cx={x(i)} cy={y(Number(r.value))} r={3.5} fill={PALETTE[0]}>
          <title>{`${dimLabel(r, dimensions)}: ${formatValue(Number(r.value), unit)}`}</title>
        </circle>
      ))}
      {data.map((r, i) =>
        i % Math.ceil(data.length / 6 || 1) === 0 ? (
          <text key={i} x={x(i)} y={h - 12} textAnchor="middle" className="axis">
            {String(r[dimensions[0]]).slice(-7)}
          </text>
        ) : null
      )}
    </svg>
  );
}

export function BarChart({ rows, dimensions, unit }: ChartProps) {
  const w = 520;
  const h = 240;
  const pad = { l: 56, r: 16, t: 16, b: 56 };
  const data = rows.slice(0, 12);
  if (data.length === 0) return <Empty />;
  const values = data.map((r) => Number(r.value));
  const max = Math.max(...values, 0) || 1;
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const bw = (innerW / data.length) * 0.7;
  const gap = (innerW / data.length) * 0.3;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart" role="img">
      {[0, 0.5, 1].map((t) => {
        const yy = pad.t + innerH - t * innerH;
        return (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={yy} y2={yy} stroke="#1e293b" strokeDasharray="3 3" />
            <text x={8} y={yy + 4} className="axis">{formatValue(t * max, unit)}</text>
          </g>
        );
      })}
      {data.map((r, i) => {
        const bh = (Number(r.value) / max) * innerH;
        const xx = pad.l + i * (bw + gap) + gap / 2;
        const yy = pad.t + innerH - bh;
        return (
          <g key={i}>
            <rect x={xx} y={yy} width={bw} height={Math.max(bh, 0)} rx={3} fill={PALETTE[i % PALETTE.length]}>
              <title>{`${dimLabel(r, dimensions)}: ${formatValue(Number(r.value), unit)}`}</title>
            </rect>
            <text x={xx + bw / 2} y={h - 36} textAnchor="end" transform={`rotate(-35 ${xx + bw / 2} ${h - 36})`} className="axis">
              {String(r[dimensions[0]] ?? "—").slice(0, 14)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function KpiTile({ value, unit, label }: { value: number; unit: Unit; label: string }) {
  return (
    <div className="kpi">
      <div className="kpi-value">{formatValue(value, unit)}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

export function DataTable({ rows, dimensions, unit }: ChartProps) {
  if (rows.length === 0) return <Empty />;
  return (
    <table className="data-table">
      <thead>
        <tr>
          {dimensions.map((d) => (
            <th key={d}>{d}</th>
          ))}
          <th>value</th>
        </tr>
      </thead>
      <tbody>
        {rows.slice(0, 50).map((r, i) => (
          <tr key={i}>
            {dimensions.map((d) => (
              <td key={d}>{String(r[d] ?? "—")}</td>
            ))}
            <td className="num">{formatValue(Number(r.value), unit)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Empty() {
  return <div className="empty">No data</div>;
}
