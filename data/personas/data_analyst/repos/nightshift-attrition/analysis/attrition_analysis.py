import pandas as pd
import numpy as np

# Load data
# Assume CSV exported from Power BI data source
df = pd.read_csv('call_center_data.csv')

# Preprocess
# Convert timestamp to datetime and extract shift

df['Timestamp'] = pd.to_datetime(df['Timestamp'])

def get_shift(ts):
    hour = ts.hour
    if 6 <= hour < 14:
        return 'Day'
    elif 14 <= hour < 22:
        return 'Evening'
    else:
        return 'Night'

df['Shift'] = df['Timestamp'].apply(get_shift)

# Compute attrition rate per shift
# Attrition flag: 1 if agent left, 0 otherwise
shift_stats = df.groupby('Shift')['Attrition'].agg(['sum','count']).rename(columns={'sum':'left','count':'total'})
shift_stats['attrition_rate'] = shift_stats['left'] / shift_stats['total']

# Calculate relative rate
night_rate = shift_stats.loc['Night','attrition_rate']
day_rate = shift_stats.loc['Day','attrition_rate']
evening_rate = shift_stats.loc['Evening','attrition_rate']

# Night shift attrition multiplier
multiplier = night_rate / ((day_rate + evening_rate)/2)
print('Night shift attrition multiplier:', round(multiplier,2))

# Export summary for Power BI report
shift_stats.to_csv('shift_attrition_summary.csv', index=True)
