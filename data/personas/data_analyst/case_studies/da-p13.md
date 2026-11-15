<!-- project_id: da-p13 | synthetic -->
# Data cleaning of a 300k-row CRM export

## Context
The client operates in the B2B services sector and relies on a customer relationship management (CRM) system to track interactions, sales opportunities, and contact information. Over time the exported data set had grown to 300,000 rows, but it contained a large amount of noise: duplicate records, incomplete fields, and a high email bounce rate that was hurting campaign effectiveness. The client needed a clean, reliable data source that could be used for reporting and outreach without spending weeks manually hunting down errors.

## What I built
I began by pulling the raw export into a spreadsheet‑friendly environment and then applied a series of systematic steps to cleanse the data. First, I identified and removed exact duplicate rows, then I used logical rules to merge records that represented the same contact but had slight variations (for example, differences in case or spacing). Next, I standardized key fields such as email addresses, phone numbers, and company names to ensure consistency across the entire file. I also filtered out records with missing or malformed email addresses, as these were the primary cause of bounce‑backs. Throughout the process I documented each transformation so the client could reproduce the workflow on future exports.

## Results
The cleaning routine eliminated 38,000 duplicate entries, reducing the data set to a more manageable size and improving its overall quality. After the cleanup, the email bounce rate dropped dramatically from 14 % to just 3 %, meaning that outreach campaigns reached far more intended recipients. The client now has a single, trustworthy source of truth for their CRM data, which feeds directly into their reporting dashboards and supports more accurate decision‑making. The streamlined process also saves the client several hours each month that were previously spent on manual data correction.
