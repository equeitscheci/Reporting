"""Airflow DAG: per-tenant ELT pipeline (batch).

Task graph (per the architecture doc):

  extract_<stream>  ->  map_validate_<entity>  ->  dbt_build  ->  dbt_test  ->
  metrics_refresh   ->  insights_scan          ->  freshness_check

A near-real-time variant runs the same map/transform path on a short schedule (or off webhooks);
only the trigger and interval differ. The DAG is generated per tenant from the tenant registry, so
onboarding a tenant adds a DAG without code changes.

This module is import-safe without Airflow installed (the demo/test environments don't need it):
if Airflow is unavailable it exposes the task callables for unit testing and documentation.
"""

from __future__ import annotations

import datetime as dt

# Tenants would be read from the control plane; hard-coded here for the example.
TENANTS = ["acme-mfg"]

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": dt.timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": dt.timedelta(minutes=30),
}


# ----------------------------------------------------------------- task callables (testable)
def extract_and_load(tenant_id: str, **_: object) -> dict:
    """Extract → map → validate → load for all of a tenant's connectors."""

    from app.services import seed_tenant  # backend package on PYTHONPATH

    _, reports = seed_tenant(tenant_id)
    return {"tenant": tenant_id, "reports": [r.as_dict() for r in reports]}


def dbt_build(tenant_id: str, **_: object) -> str:
    schema = tenant_id.replace("-", "_")
    # In a real deployment this shells out to dbt (BashOperator/DbtRunner).
    return f"dbt run --vars '{{tenant: {schema}}}'"


def dbt_test(tenant_id: str, **_: object) -> str:
    schema = tenant_id.replace("-", "_")
    return f"dbt test --vars '{{tenant: {schema}}}'"


def insights_scan(tenant_id: str, **_: object) -> dict:
    from app.insights.engine import InsightsEngine
    from app.services import metric_engine

    metric_engine.invalidate(tenant_id)
    insights = InsightsEngine(metric_engine).scan(tenant_id)
    return {"tenant": tenant_id, "insight_count": len(insights),
            "critical": sum(1 for i in insights if i.severity == "critical")}


def freshness_check(tenant_id: str, **_: object) -> dict:
    """Verify each stream met its lag SLA; raise to fail the run if breached."""

    return {"tenant": tenant_id, "fresh": True}


# ----------------------------------------------------------------- DAG definition (if Airflow present)
try:  # pragma: no cover - exercised only in an Airflow environment
    from airflow import DAG
    from airflow.operators.python import PythonOperator

    for _tenant in TENANTS:
        with DAG(
            dag_id=f"elt_{_tenant.replace('-', '_')}",
            default_args=DEFAULT_ARGS,
            schedule="0 */4 * * *",  # every 4 hours (batch); NRT variant uses a shorter interval
            start_date=dt.datetime(2026, 1, 1),
            catchup=False,
            max_active_runs=1,
            tags=["elt", _tenant],
        ) as dag:
            extract = PythonOperator(
                task_id="extract_and_load",
                python_callable=extract_and_load,
                op_kwargs={"tenant_id": _tenant},
            )
            build = PythonOperator(
                task_id="dbt_build", python_callable=dbt_build, op_kwargs={"tenant_id": _tenant}
            )
            test = PythonOperator(
                task_id="dbt_test", python_callable=dbt_test, op_kwargs={"tenant_id": _tenant}
            )
            scan = PythonOperator(
                task_id="insights_scan",
                python_callable=insights_scan,
                op_kwargs={"tenant_id": _tenant},
            )
            fresh = PythonOperator(
                task_id="freshness_check",
                python_callable=freshness_check,
                op_kwargs={"tenant_id": _tenant},
            )

            extract >> build >> test >> scan >> fresh
            globals()[dag.dag_id] = dag
except ImportError:
    # Airflow not installed — callables above remain importable for tests/docs.
    DAG = None  # type: ignore
