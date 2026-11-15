<!-- project_id: da-p15 | synthetic -->
# Cohort Retention Report for a Mobile Game

## Context
The client, a developer in the gaming industry, needed a clear view of how new players were staying engaged after their first week. Their existing dashboards were fragmented, making it difficult for product and design teams to pinpoint where the onboarding experience was losing users. The goal was to create a single, easy‑to‑read report that broke down retention by the day a player first installed the game, allowing the team to test and iterate on onboarding tweaks quickly.

## What I built
I started by pulling raw event logs that recorded every user action from the moment of installation onward. Using a structured query language, I transformed those logs into a tidy table that grouped players into cohorts based on their install date and calculated the percentage of each cohort that returned on day 1, day 2, … up to day 7. I then layered the data into a visual dashboard that displayed a heat‑map style retention curve, a line chart that highlighted day‑7 trends over time, and a set of filters so stakeholders could slice the data by region, device type, or acquisition channel. All of the calculations and visual elements were built within a business intelligence platform that the client already used, ensuring the report could be refreshed automatically each day without manual intervention.

## Results
The day‑7 retention metric was the most actionable insight. When the product team examined the cohort curve, they saw a consistent dip on day 7 across several launch windows. Using the new report, they ran a small A/B test that introduced a brief tutorial at the end of day 6. After the change, the day‑7 retention figure rose by four percentage points, a meaningful uplift for a free‑to‑play title where every retained user translates into additional revenue opportunities. The client now relies on this report for weekly strategy meetings, and the transparent visual format has reduced the time spent gathering data from hours to a few minutes per week.
