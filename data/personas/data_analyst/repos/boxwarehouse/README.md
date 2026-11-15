# boxwarehouse

## Overview
`boxwarehouse` is a SQL‑based data warehouse that consolidates subscription‑box ecommerce events into a single source of truth. The model captures customer lifecycle, order fulfillment, payment, and marketing interaction data, enabling reliable churn analysis and cross‑functional reporting for finance and marketing teams.

## Architecture
- **Source Layer**: Raw event tables are ingested via an ETL pipeline (e.g., Cloud Storage → staging tables). Each source retains its original schema for auditability.
- **Staging Layer**: Minimal transformations (type casting, deduplication) are applied. Tables are partitioned by event date for efficient pruning.
- **Core Layer**: Dimensional model built with conformed dimensions (`dim_customer`, `dim_product`, `dim_date`) and fact tables (`fact_subscription`, `fact_payment`, `fact_marketing`). Slowly changing dimensions are handled as Type‑2.
- **Presentation Layer**: Materialized views expose KPI‑ready aggregates such as monthly churn rate, LTV, and CAC. Views are refreshed nightly.

## How to Run
1. Clone the repo:
   ```
   git clone https://github.com/yourusername/boxwarehouse.git
   cd boxwarehouse
   ```
2. Set up the SQL environment (e.g., a compatible data warehouse instance) and configure connection credentials in `config.yaml`.
3. Execute the ETL bootstrap script to create schemas and load initial data:
   ```
   ./scripts/bootstrap.sh
   ```
4. Run incremental loads daily via the provided scheduler command:
   ```
   ./scripts/run_etl.sh --date $(date +%Y-%m-%d)
   ```
5. Validate the model by querying the `view_churn_summary` view:
   ```sql
   SELECT * FROM analytics.view_churn_summary LIMIT 10;
   ```

## Development
- All SQL objects are version‑controlled under the `sql/` directory.
- Use `sqlfmt` for linting and `dbt test` (or equivalent) to run schema tests.
- Add new dimensions or facts by extending the appropriate `*_dim.sql` or `*_fact.sql` files and updating the DAG in `scripts/run_etl.sh`.

## License
MIT
