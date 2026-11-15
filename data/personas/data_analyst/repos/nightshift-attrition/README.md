# nightshift-attrition

## Overview
`nightshift-attrition` is a Power BI‑based analytics pipeline that ingests call‑centre workforce logs, performs statistical preprocessing, and visualizes attrition trends. The repository contains the Power BI data model, DAX calculations, and supporting Power Query scripts that transform raw HR CSV exports into a tidy fact table. The primary insight—night‑shift agents churn 2.3× faster than day‑shift peers—drives the downstream recommendation to adjust shift scheduling policies.

## Architecture
- **Data Ingestion**: Power Query (`*.pq` files) reads `agents.csv`, `shifts.csv`, and `attendance.csv`. Queries merge on `EmployeeID`, filter out terminated records older than 12 months, and compute tenure in days.
- **Model Layer**: A star schema with `DimEmployee`, `DimShift`, and `FactAttrition`. Calculated columns use DAX to flag night‑shift assignments and calculate survival curves.
- **Analytics**: DAX measures compute:
  - `AvgTenure = AVERAGE(FactAttrition[TenureDays])`
  - `NightShiftHazard = DIVIDE(COUNTROWS(FILTER(FactAttrition, DimShift[Shift] = "Night" && FactAttrition[Left] = TRUE)), COUNTROWS(FILTER(FactAttrition, DimShift[Shift] = "Night")))`
  - `DayShiftHazard` analogous for day shift.
  - `HazardRatio = DIVIDE([NightShiftHazard], [DayShiftHazard])`
- **Visualization**: A Power BI report (`nightshift-attrition.pbix`) with line charts for survival curves, a KPI tile showing the hazard ratio, and slicers for department and tenure brackets.

## Getting Started
1. Clone the repo.
2. Open `nightshift-attrition.pbix` in Power BI Desktop (version 2.115+).
3. In **Home → Transform data**, update the source paths to point at your HR CSV exports.
4. Refresh the model; the report will recompute all DAX measures automatically.
5. Export visuals or publish to Power BI Service for stakeholder access.

## Dependencies
- Microsoft Power BI Desktop (Windows)
- Source CSV files with columns: `EmployeeID`, `HireDate`, `TerminationDate`, `Shift`, `Department`.

## License
MIT © 2023
