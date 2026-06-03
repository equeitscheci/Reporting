"""Command-line interface.

`insightforge demo --tenant acme-mfg` runs the entire platform offline:
extract (sample ERP) → map → validate → load → metrics → insights, printing a readable summary.
This is the fastest way to see the system work without a database or external ERP.
"""

from __future__ import annotations

import json

import typer

app = typer.Typer(help="Insightforge platform CLI", no_args_is_help=True)


@app.command()
def demo(tenant: str = typer.Option("acme-mfg", help="Tenant id to run the demo for")) -> None:
    """Run the full extract → map → validate → load → metrics → insights pipeline offline."""

    from app.insights.engine import InsightsEngine
    from app.insights.nlq import NLQueryEngine
    from app.metrics.engine import MetricQuery
    from app.services import metric_engine, seed_tenant, store

    typer.secho(f"\n== Insightforge demo: tenant '{tenant}' ==\n", fg="cyan", bold=True)

    cfg, reports = seed_tenant(tenant)
    typer.secho("Pipeline (extract → map → validate → load):", fg="green", bold=True)
    for r in reports:
        for s in r.streams:
            typer.echo(
                f"  {s.stream:>20} → {s.entity:<16} "
                f"extracted={s.extracted:<5} loaded={s.loaded:<5} quarantined={s.quarantined}"
            )

    typer.secho("\nCanonical store contents:", fg="green", bold=True)
    for entity in store.entities(tenant):
        typer.echo(f"  {entity:>20}: {store.count(tenant, entity)} rows")

    typer.secho("\nKey metrics (by month):", fg="green", bold=True)
    for metric in ("revenue", "gross_margin_pct"):
        res = metric_engine.query(tenant, MetricQuery(metric=metric, dimensions=["month"]))
        rows = sorted(res.rows, key=lambda r: r["month"])
        series = ", ".join(f"{r['month']}={r['value']:,.1f}" for r in rows[-4:])
        typer.echo(f"  {res.label}: {series}")

    typer.secho("\nInsights:", fg="green", bold=True)
    insights = InsightsEngine(metric_engine).scan(tenant, industry=cfg.profile.primary_vertical)
    for i in insights[:6]:
        color = {"critical": "red", "warning": "yellow"}.get(i.severity, "white")
        typer.secho(f"  [{i.severity.upper()}] {i.title}", fg=color, bold=True)
        typer.echo(f"      {i.explanation}")
        for a in i.recommended_actions[:3]:
            typer.echo(f"        - {a}")

    typer.secho("\nNatural-language query:", fg="green", bold=True)
    nlq = NLQueryEngine(metric_engine)
    ans = nlq.answer(tenant, "Why did margins drop last month?")
    typer.echo(f"  Q: {ans.question}")
    typer.echo(f"  A: {ans.answer}")

    typer.secho("\nDone.\n", fg="cyan", bold=True)


@app.command()
def query(
    tenant: str = typer.Option("acme-mfg"),
    metric: str = typer.Option(...),
    by: str = typer.Option("", help="comma-separated dimensions"),
) -> None:
    """Run a single metric query and print JSON."""

    from app.metrics.engine import MetricQuery
    from app.services import metric_engine, seed_tenant

    seed_tenant(tenant)
    dims = [d for d in by.split(",") if d]
    res = metric_engine.query(tenant, MetricQuery(metric=metric, dimensions=dims))
    typer.echo(json.dumps(res.as_dict(), indent=2, default=str))


@app.command()
def connectors() -> None:
    """List available connector types."""

    from app.connectors.registry import load_builtin_connectors, registry

    load_builtin_connectors()
    typer.echo("Available connector types: " + ", ".join(registry.available()))


if __name__ == "__main__":
    app()
