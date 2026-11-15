#!/usr/bin/env python3
"""ETL Pipeline for Subscription Box Company

This script extracts raw data from BigQuery, transforms it into a clean warehouse
structure, and loads it back into BigQuery.  The pipeline uses the
`google-cloud-bigquery` client library.

Author: Data Engineering Team
Year: 2024
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List

from google.cloud import bigquery

# Configuration --------------------------------------------------------------
PROJECT_ID = "ecommerce"
RAW_DATASET = "raw"
WAREHOUSE_DATASET = "warehouse"

# BigQuery client ------------------------------------------------------------
client = bigquery.Client(project=PROJECT_ID)

# Helper functions -----------------------------------------------------------

def run_query(query: str, job_id: str | None = None) -> bigquery.table.RowIterator:
    """Run a BigQuery query and return the result iterator."""
    job_config = bigquery.QueryJobConfig()
    if job_id:
        job_config.job_id = job_id
    query_job = client.query(query, job_config=job_config)
    return query_job.result()


def load_table_from_query(query: str, table_id: str, write_disposition: str = "WRITE_TRUNCATE") -> None:
    """Execute a query and load its result into the specified table."""
    job_config = bigquery.QueryJobConfig(
        destination=table_id,
        write_disposition=write_disposition,
    )
    client.query(query, job_config=job_config).result()

# ETL steps ---------------------------------------------------------------

def extract_subscriptions() -> List[bigquery.table.Row]:
    """Extract subscription records from raw dataset."""
    query = f"SELECT * FROM `{PROJECT_ID}.{RAW_DATASET}.subscriptions`"
    return list(run_query(query))


def transform_churn(subscriptions: List[bigquery.table.Row]) -> List[dict]:
    """Add churn flag and calculate days since last update."""
    transformed = []
    now = datetime.utcnow()
    for row in subscriptions:
        days_since = (now - row.updated_at).days
        is_churned = row.status.lower() == "canceled"
        transformed.append(
            {
                "subscription_id": row.subscription_id,
                "customer_id": row.customer_id,
                "plan_id": row.plan_id,
                "start_date": row.start_date,
                "end_date": row.end_date,
                "status": row.status,
                "days_since_last_update": days_since,
                "is_churned": is_churned,
            }
        )
    return transformed


def load_churn_table(transformed: List[dict]) -> None:
    """Load the churn fact table into BigQuery."""
    table_id = f"{PROJECT_ID}.{WAREHOUSE_DATASET}.churn_fact"
    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("subscription_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("plan_id", "STRING"),
            bigquery.SchemaField("start_date", "DATE"),
            bigquery.SchemaField("end_date", "DATE"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("days_since_last_update", "INTEGER"),
            bigquery.SchemaField("is_churned", "BOOLEAN"),
        ],
        write_disposition="WRITE_TRUNCATE",
    )
    client.load_table_from_json(transformed, table_id, job_config=job_config).result()

# Main pipeline ------------------------------------------------------------

def main() -> None:
    subscriptions = extract_subscriptions()
    churn_data = transform_churn(subscriptions)
    load_churn_table(churn_data)
    print("ETL completed: churn fact table refreshed.")


if __name__ == "__main__":
    main()
