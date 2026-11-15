import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.ensemble import RandomForestRegressor

# Load processed data
PROCESSED_DIR = "/data/processed"
file_path = f"{PROCESSED_DIR}/sales_202411.csv"

df = pd.read_csv(file_path, parse_dates=["sale_date"])

# Prepare features and target
X = df[['day_of_week', 'month', 'quantity', 'price']]
y = df['total_amount']

# Time‑series split
tscv = TimeSeriesSplit(n_splits=5)
mape_scores = []
for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    model = RandomForestRegressor(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mape = mean_absolute_percentage_error(y_test, preds)
    mape_scores.append(mape)

print(f"Average MAPE across folds: {np.mean(mape_scores):.2%}")
