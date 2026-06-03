import type { Unit } from "./types";

export function formatValue(value: number, unit: Unit): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  switch (unit) {
    case "currency":
      return value.toLocaleString(undefined, {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      });
    case "percent":
      return `${value.toFixed(1)}%`;
    case "days":
      return `${value.toFixed(0)} d`;
    default:
      return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
  }
}

export function dimLabel(row: Record<string, unknown>, dims: string[]): string {
  return dims.map((d) => String(row[d] ?? "—")).join(" / ");
}
