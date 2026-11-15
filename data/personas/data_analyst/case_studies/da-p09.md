<!-- project_id: da-p09 | synthetic -->
# Warehouse SQL model for a subscription box company

## Context
The client, an ecommerce subscription‑box business, was struggling with fragmented data sources. Finance and marketing teams each maintained their own spreadsheets and ad‑hoc queries, leading to conflicting figures for churn, revenue, and campaign performance. Decision‑makers lacked a single, reliable view of the key metrics, which slowed strategic planning and caused friction between departments.

## What I built
I designed a centralized relational data model that consolidated all operational tables—orders, subscriptions, payments, and customer interactions—into a cohesive structure. The model captured the lifecycle of each subscriber, from acquisition through renewal or cancellation, enabling precise churn calculations. I created automated processes to pull raw data from the source systems, clean and transform it, and load it into the new model on a daily schedule. The transformation logic standardized date formats, resolved duplicate records, and derived calculated fields such as lifetime value and average order frequency.

To make the data accessible, I built a suite of interactive dashboards and reports. These visualisations allowed finance to reconcile revenue and expense figures, while marketing could track campaign ROI and subscriber growth trends. The reports were built with drag‑and‑drop visual tools, offering drill‑through capabilities so users could explore the underlying data without needing SQL expertise.

## Results
The new model became the single source of truth for churn and related metrics. Finance and marketing now reference the same numbers, eliminating previous disagreements and reducing the time spent reconciling reports by over 50 %. Executives gained confidence in the data, enabling faster, data‑driven decisions around pricing, inventory, and marketing spend. The automated refresh schedule ensured that the dashboards always reflected the latest activity, supporting real‑time monitoring of business health.
