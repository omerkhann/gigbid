<!-- project_id: da-p04 | synthetic -->
# Customer Segmentation for a Microfinance Lender

## Context
In 2023, a microfinance lender approached me to improve its loan‑portfolio management. The institution serves a diverse client base across urban and rural areas, but its existing risk‑assessment framework relied on a few high‑level indicators and was not capturing the nuances of borrower behavior. The lender needed a data‑driven way to identify distinct customer groups, especially to isolate those with higher repayment risk, so that it could tailor credit terms, allocate collection resources more efficiently, and ultimately reduce default losses.

## What I built
I began by extracting the lender’s transactional and demographic data from the SQL warehouse into a Python environment. Using **pandas**, I cleaned and merged over 200,000 loan records, handling missing values, outliers, and standardizing categorical fields. I then performed **statistical analysis** to explore relationships between variables such as loan amount, repayment history, income level, and geographic location.

To create the segments, I applied a **K‑means clustering** algorithm, iterating on the number of clusters and evaluating silhouette scores. After several rounds of feature engineering—creating ratios like debt‑to‑income and repayment‑timeliness—I settled on a five‑cluster solution that balanced interpretability with statistical robustness. Each cluster was profiled with descriptive statistics and visualized using seaborn heatmaps and bar charts, allowing the client to see the key drivers of each segment.

## Results
The analysis produced **five clear customer segments**. The most critical finding was the identification of a **repayment‑risk segment** whose default rate was **three times higher** than the overall portfolio average. This insight enabled the lender to:

- Adjust credit limits and interest rates for the high‑risk group.
- Prioritize proactive outreach and monitoring for those borrowers.
- Reallocate marketing spend toward lower‑risk segments with higher repayment propensity.

Within the first quarter after implementing the segmentation, the lender reported a **12% reduction in new defaults** and a **7% improvement in loan recovery efficiency**. The project demonstrated how a disciplined blend of Python, pandas, and statistical analysis can transform raw loan data into actionable business intelligence.
