# dbt project — transforms + semantic metrics

Builds Gold marts from Silver canonical tables and defines the governed metrics layer.

```bash
cd warehouse/dbt
cp profiles.example.yml ~/.dbt/profiles.yml      # or set DBT_PROFILES_DIR
dbt deps
dbt run   --vars '{tenant: acme_mfg}'
dbt test  --vars '{tenant: acme_mfg}'
```

- `models/staging/` — light enrichment (view) over canonical sources.
- `models/marts/` — conformed dims + facts (table), the star schema BI queries.
- `metrics/` — dbt Semantic Layer definitions. A metric like `gross_margin_pct` is defined **once**
  here and reused by the API, dashboards, NLQ, and insights so it always means the same thing.

Swap the `profiles.yml` `type` to `snowflake`/`bigquery` to target a cloud warehouse — the model SQL
is portable. The backend Python metric registry (`backend/app/metrics/definitions.py`) mirrors these
definitions and is the runtime executor for the in-memory/dev path.
