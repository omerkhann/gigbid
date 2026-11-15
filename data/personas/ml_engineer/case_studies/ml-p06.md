<!-- project_id: ml-p06 | synthetic -->
# Lead-Scoring Model for a B2B Sales Team

## Context
In 2023, a B2B services company approached me to improve the efficiency of its sales pipeline. The sales team relied on manual lead qualification, which resulted in a high volume of low‑quality prospects and a low conversion rate. The client needed a data‑driven solution that could rank incoming leads by their likelihood to convert, allowing the team to focus on the most promising opportunities. The project scope included building a predictive model, integrating it with existing data sources, and delivering actionable scores that could be used in daily sales workflows.

## What I built
I designed and delivered an end‑to‑end lead‑scoring system using Python and Scikit‑Learn. The workflow began with a comprehensive data analysis phase, where I extracted historical lead data from the client’s SQL database, cleaned and engineered features such as engagement metrics, firmographics, and interaction timestamps. I then split the data into training and validation sets and evaluated several algorithms—including logistic regression, gradient boosting, and random forests—selecting the model that offered the best balance of precision and recall for the top‑decile leads.

The final model was a Gradient Boosting Classifier tuned via grid search, producing a probability score for each lead. I packaged the model as a reproducible pipeline using Scikit‑Learn’s `Pipeline` class, enabling seamless retraining as new data arrives. To operationalize the solution, I created a lightweight API that queried the SQL warehouse, applied the model, and returned scores in real time. Documentation and a simple dashboard were provided so the sales team could visualize lead rankings and track score distribution.

## Results
The lead‑scoring model quickly demonstrated impact. Leads placed in the top decile of the scoring distribution converted at **3.2 ×** the average conversion rate of all leads, dramatically improving the efficiency of the sales outreach process. The client reported a measurable increase in pipeline velocity and a reduction in time spent on low‑quality prospects. The solution was fully integrated into the existing workflow, and the model’s modular design ensures it can be retrained and refined as the business evolves.
