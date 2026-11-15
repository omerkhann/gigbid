# freshforecast

**Overview**

`freshforecast` is a Python‑based demand‑forecasting pipeline built for a multi‑store grocery chain. It ingests daily sales logs, enriches them with promotional and weather metadata, and produces point forecasts for the next 28 days. The model architecture combines a gradient‑boosted regressor (XGBoost) with engineered statistical features (lagged sales, rolling averages, holiday flags) to capture seasonality and promotional lift. The pipeline is containerised with Docker and orchestrated via a simple Airflow DAG for nightly retraining and scoring.

**Architecture**

1. **ETL Layer** – `scripts/etl.py` pulls raw CSVs from an S3 bucket, applies type coercion with pandas, and writes cleaned parquet files to a staging area.
2. **Feature Store** – `features/` builds time‑series features (7‑day/28‑day windows, day‑of‑week dummies) and stores them in a SQLite DB for reproducibility.
3. **Modeling** – `model/train.py` loads features, splits on a time‑based holdout, trains XGBoost, and logs MAPE to MLflow. The best model artifact is saved as `model.pkl`.
4. **Scoring** – `model/predict.py` reads the latest features, generates forecasts, and writes results back to S3 for downstream consumption.
5. **Orchestration** – `airflow/dag.py` defines tasks for ETL, feature generation, training, and prediction, scheduled to run at 02:00 UTC.

**Running Locally**

```bash
# Clone and enter repo
git clone https://github.com/youruser/freshforecast.git && cd freshforecast

# Build Docker image
docker build -t freshforecast .

# Start Airflow (docker‑compose) and trigger the DAG
docker-compose up -d
airflow dags trigger freshforecast_dag
```

The pipeline achieves a mean absolute percentage error (MAPE) of 11 %, a substantial improvement over the legacy spreadsheet approach (19 %).
