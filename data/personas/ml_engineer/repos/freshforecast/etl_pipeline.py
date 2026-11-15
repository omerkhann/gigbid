import os
import pandas as pd
from datetime import datetime

# Configuration
DATA_DIR = os.getenv("DATA_DIR", "/data/raw")
PROCESSED_DIR = os.getenv("PROCESSED_DIR", "/data/processed")

# Helper functions

def load_sales_data(file_name: str) -> pd.DataFrame:
    """Load raw sales CSV into a DataFrame."""
    path = os.path.join(DATA_DIR, file_name)
    df = pd.read_csv(path, parse_dates=["sale_date"])
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Basic cleaning: remove duplicates, fill missing values."""
    df = df.drop_duplicates(subset=["transaction_id"])
    df['quantity'] = df['quantity'].fillna(0)
    df['price'] = df['price'].fillna(method='ffill')
    return df


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """Create features needed for forecasting."""
    df['total_amount'] = df['quantity'] * df['price']
    df['day_of_week'] = df['sale_date'].dt.dayofweek
    df['month'] = df['sale_date'].dt.month
    return df


def save_processed(df: pd.DataFrame, file_name: str) -> None:
    """Persist processed DataFrame to CSV."""
    out_path = os.path.join(PROCESSED_DIR, file_name)
    df.to_csv(out_path, index=False)

# Main ETL routine
if __name__ == "__main__":
    raw_file = f"sales_{datetime.now().strftime('%Y%m')}.csv"
    df_raw = load_sales_data(raw_file)
    df_clean = clean_data(df_raw)
    df_features = feature_engineering(df_clean)
    save_processed(df_features, raw_file)
