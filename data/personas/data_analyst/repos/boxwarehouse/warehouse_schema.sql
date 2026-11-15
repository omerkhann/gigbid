-- warehouse_schema.sql
-- BigQuery schema for subscription box churn analysis
-- Author: Data Engineering Team
-- Year: 2024

-- 1. Raw source tables (in raw dataset)
CREATE OR REPLACE TABLE `ecommerce.raw.subscriptions` (
  subscription_id STRING NOT NULL,
  customer_id STRING NOT NULL,
  plan_id STRING,
  start_date DATE,
  end_date DATE,
  status STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) OPTIONS(
  description="Raw subscription events"
);

CREATE OR REPLACE TABLE `ecommerce.raw.payments` (
  payment_id STRING NOT NULL,
  subscription_id STRING,
  amount NUMERIC,
  currency STRING,
  payment_date DATE,
  status STRING,
  created_at TIMESTAMP
) OPTIONS(
  description="Raw payment transactions"
);

-- 2. Dimension tables
CREATE OR REPLACE TABLE `ecommerce.dim.customers` AS
SELECT DISTINCT
  customer_id,
  MIN(created_at) AS first_seen,
  MAX(updated_at) AS last_seen
FROM `ecommerce.raw.subscriptions`
GROUP BY customer_id;

CREATE OR REPLACE TABLE `ecommerce.dim.plans` AS
SELECT DISTINCT
  plan_id,
  STRING_AGG(DISTINCT status) AS statuses
FROM `ecommerce.raw.subscriptions`
GROUP BY plan_id;

-- 3. Fact table for churn analysis
CREATE OR REPLACE TABLE `ecommerce.fact.churn` AS
SELECT
  s.subscription_id,
  s.customer_id,
  s.plan_id,
  s.start_date,
  s.end_date,
  s.status,
  p.amount AS last_payment_amount,
  p.payment_date AS last_payment_date,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), s.updated_at, DAY) AS days_since_last_update,
  IF(s.status = "canceled", TRUE, FALSE) AS is_churned
FROM `ecommerce.raw.subscriptions` s
LEFT JOIN (
  SELECT
    subscription_id,
    amount,
    payment_date
  FROM `ecommerce.raw.payments`
  WHERE status = "completed"
  QUALIFY ROW_NUMBER() OVER (PARTITION BY subscription_id ORDER BY payment_date DESC) = 1
) p
ON s.subscription_id = p.subscription_id;

-- 4. View for finance & marketing reconciliation
CREATE OR REPLACE VIEW `ecommerce.vw.financial_marketing_reconciliation` AS
SELECT
  c.customer_id,
  SUM(p.amount) AS total_revenue,
  COUNT(DISTINCT s.subscription_id) AS active_subscriptions,
  SUM(CASE WHEN s.status = "canceled" THEN 1 ELSE 0 END) AS churn_count
FROM `ecommerce.raw.subscriptions` s
JOIN `ecommerce.raw.payments` p
  ON s.subscription_id = p.subscription_id
JOIN `ecommerce.dim.customers` c
  ON s.customer_id = c.customer_id
WHERE p.status = "completed"
GROUP BY c.customer_id;

-- End of warehouse_schema.sql
