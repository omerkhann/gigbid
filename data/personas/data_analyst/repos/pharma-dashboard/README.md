# pharma-dashboard

## Overview
`pharma-dashboard` is a Power BI solution that consolidates sales data from a pharmaceutical distribution network into a single, refreshable data model. The repository contains the SQL scripts for data extraction, the Power BI data model (`.pbix`) and supporting documentation. The goal is to enable area managers to generate monthly performance reports in under two hours, down from a manual three‑day process.

## Architecture
- **Source Systems**: Transactional sales data resides in a relational database (SQL Server). The data is normalized across tables for orders, customers, products, and inventory.
- **ETL Layer**: A set of parameterized T‑SQL scripts (`extract_*.sql`) perform incremental extracts, clean data (null handling, type casting), and load it into a staging schema. A subsequent `transform.sql` script builds the star schema used by Power BI, creating fact and dimension tables.
- **Data Model**: The Power BI file references the fact table (`FactSales`) and dimension tables (`DimProduct`, `DimRegion`, `DimTime`). Relationships are defined using surrogate keys. Measures are built with DAX for YoY growth, market share, and KPI thresholds.
- **Visualization**: The dashboard includes a summary page with slicers for region, product line, and time period, plus drill‑through pages for detailed order analysis.

## Prerequisites
- Microsoft SQL Server 2019+ with read access to the source database.
- Power BI Desktop (latest version).
- Windows environment (Power BI Desktop is Windows‑only).

## Setup & Execution
1. Clone the repo.
2. Open a PowerShell prompt and run `.setup.ps1` to create the staging schema and execute the ETL scripts against the target server (edit `config.json` with connection strings first).
3. Open `PharmaSales.pbix` in Power BI Desktop.
4. Click **Refresh** to pull the latest data; the model will refresh in ~2 hours for the full month.
5. Publish to Power BI Service for scheduled refreshes and share with the 40 area managers.

## Maintenance
- Update `extract_*.sql` when source tables change.
- Adjust DAX measures in the `.pbix` as new KPIs are required.
- Re‑run `setup.ps1` after any schema modifications.

---
*This repository is intended for internal use by the pharma distribution analytics team.*
