<!-- project_id: da-p05 | synthetic -->
# Hospital Bed‑Occupancy Reporting in Tableau

## Context
Bilal Ahmed was engaged by a healthcare organization that relied on six separate, manually‑maintained spreadsheets to track daily hospital bed occupancy. The process was time‑consuming, error‑prone, and provided no real‑time insight for operational decision‑making. The client needed a single, reliable source of truth that could be refreshed automatically and accessed easily by staff across departments.

## What I built
Using Tableau as the visualization platform, Bilal connected directly to the client’s Microsoft SQL Server database. He wrote optimized SQL queries to pull the latest admission, discharge, and transfer data, consolidating them into a clean, normalized dataset. In Tableau, he designed an interactive dashboard that displayed:
- A real‑time occupancy heat map by ward and floor.
- Trend lines showing occupancy rates over the past week.
- Drill‑down tables for individual bed status and patient details.
- Alerts that highlighted beds approaching capacity thresholds.
The dashboard was published to Tableau Server, enabling secure, role‑based access and scheduled data extracts that refreshed daily. Bilal also documented the data model and provided a brief training session for the client’s analytics team.

## Results
The new Tableau dashboard replaced the six manual spreadsheets, delivering a single, up‑to‑date view of bed occupancy each day. This automation cut the reporting workload by an estimated 80 % and eliminated data entry errors. Hospital administrators gained immediate visibility into capacity constraints, allowing them to reallocate resources proactively. Overall, the solution streamlined operations, improved data accuracy, and supported better patient flow management throughout 2023.
