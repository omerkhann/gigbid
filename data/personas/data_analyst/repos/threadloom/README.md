# threadloom

## Overview
`threadloom` is a Microsoft Excel‑based tool that automates inventory ageing analysis for a mid‑size apparel retailer. The workbook ingests daily stock snapshots, calculates age buckets, flags slow‑moving SKUs, and generates a markdown recommendation sheet. All calculations are performed with native Excel formulas and a VBA module that orchestrates data refresh, pivot generation, and report export.

## Architecture
- **Data Input** – Raw inventory CSVs are imported into the `RawData` sheet via the `ImportData` macro. The macro validates column headers, normalises dates, and appends new rows to a growing table.
- **Processing Layer** – The `AgeCalc` sheet contains vectorised formulas that compute `DaysInStock`, assign each SKU to an ageing bucket (0‑30, 31‑90, 91‑180, >180 days), and calculate turnover ratios.
- **VBA Engine** – `Module1` implements three core procedures:
  1. `RefreshAll` – triggers a full recalculation, updates pivot tables, and clears stale cache.
  2. `GenerateReport` – extracts SKUs with >180 days in stock, computes potential markdown impact, and writes a formatted report to `Report` sheet.
  3. `ExportMarkdownPlan` – creates a CSV containing SKU, current price, suggested markdown, and projected clearance timeline.
- **Visualization** – The `Dashboard` sheet hosts slicers and charts (stacked bar for age distribution, line chart for weekly markdown performance) linked to the pivot tables.

## How to Run
1. Clone or download the repository and open `threadloom.xlsm` in Excel (2016+ with macro support).
2. Press `Alt+F8`, select `RefreshAll`, and run to load the latest inventory file (`inventory_YYYYMMDD.csv`).
3. After the refresh completes, run `GenerateReport` to populate the `Report` sheet.
4. Use `ExportMarkdownPlan` to output `markdown_plan.csv` which can be handed to the merchandising team.

## Dependencies
- Microsoft Excel (Windows/macOS) with VBA enabled.
- No external libraries; all logic resides in Excel formulas and native VBA.

## Result Snapshot
Running the full pipeline on the Q1 dataset identified $180k of slow stock and, when the generated markdown plan was applied, 70% of that inventory cleared within a single quarter.
