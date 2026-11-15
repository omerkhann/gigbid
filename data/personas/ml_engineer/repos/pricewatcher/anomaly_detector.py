import pandas as pd
import numpy as np

# Historical price data for a product (mocked for illustration)
# In practice, this would be loaded from a database or CSV
historical_prices = pd.DataFrame({
    "timestamp": pd.date_range(end=pd.Timestamp.utcnow(), periods=30, freq="D"),
    "price": np.random.normal(loc=49.99, scale=5.0, size=30)
})

# Current price snapshot (would come from scraper output)
current_snapshot = pd.DataFrame({
    "product_id": ["12345"],
    "price": [39.99],
    "timestamp": [pd.Timestamp.utcnow()]
})


def detect_anomaly(current_df, historical_df, threshold=0.15):
    """Detects price anomalies relative to historical mean.
    Returns True if price deviates more than threshold (in %).
    """
    # Merge by product_id if historical data has per-product columns
    # For this example, we assume single product
    mean_price = historical_df["price"].mean()
    std_price = historical_df["price"].std()
    current_price = current_df["price"].iloc[0]
    deviation = abs(current_price - mean_price) / mean_price
    print(f"Mean: {mean_price:.2f}, Current: {current_price:.2f}, Deviation: {deviation:.2%}")
    return deviation > threshold

if __name__ == "__main__":
    is_anomaly = detect_anomaly(current_snapshot, historical_prices)
    if is_anomaly:
        print("⚠️  Price anomaly detected! Sending alert...")
    else:
        print("✅ Price within expected range.")
