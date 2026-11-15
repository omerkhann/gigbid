<!-- project_id: ml-p10 | synthetic -->
# Customer churn prediction for a telecom reseller

## Context
In 2022, a telecom reseller approached Hamza Siddiqui, a machine‑learning engineer specializing in natural language processing, large language model applications, and production ML pipelines, to address a persistent business problem: high customer turnover. The client operated in the highly competitive telecom industry where retaining existing subscribers is far more cost‑effective than acquiring new ones. They needed a data‑driven solution that could reliably identify customers at risk of leaving so that targeted retention campaigns could be deployed. The project scope required a robust predictive model built on historical usage, billing, and interaction data, with an emphasis on interpretability and scalability for future integration into the reseller’s operational workflow.

## What I built
Hamza designed an end‑to‑end churn‑prediction pipeline using Python and Scikit‑Learn. The workflow began with extensive data preprocessing: cleaning missing values, engineering features such as average monthly spend, call‑duration trends, and service‑plan changes, and encoding categorical variables. Statistical analysis was performed to assess feature relevance and to detect multicollinearity, ensuring a parsimonious model. 

For the predictive engine, a gradient‑boosted tree classifier was selected after benchmarking several algorithms (logistic regression, random forest, XGBoost). Hyper‑parameter tuning was conducted via grid search with cross‑validation, optimizing for the Area Under the ROC Curve (AUC). The final model achieved an AUC of 0.84 on a held‑out test set, indicating strong discriminative power. 

To move the solution into production, Hamza containerized the model with Docker, set up automated data pipelines using scheduled Python scripts, and exposed a REST API for real‑time scoring. Documentation and monitoring dashboards were added to track model drift and prediction confidence, allowing the client’s marketing team to receive daily lists of high‑risk customers.

## Results
The churn‑prediction model was integrated into the reseller’s retention campaign workflow. By focusing outreach on the top‑risk segment identified by the model, the client achieved a 9% reduction in churn within the targeted group during the first campaign cycle. The high AUC score validated the model’s predictive accuracy, and the production‑ready pipeline ensured the solution could be scaled and maintained with minimal overhead. This project demonstrated how advanced machine‑learning techniques, combined with solid statistical grounding and engineering best practices, can deliver tangible business value in a competitive telecom environment.
