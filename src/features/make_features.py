# src/features/make_features.py
"""
Create lag features and rolling statistics for each district-week.
Input: data/processed/dengue_weekly_clean.csv
Output: data/processed/features_matrix.csv
Usage:
  python src/features/make_features.py
"""
import pandas as pd
import numpy as np
import os

os.makedirs("data/processed", exist_ok=True)

def build_features(df):
    df = df.copy()
    df['week_start'] = pd.to_datetime(df['week_start'])
    # ensure consistent weekly index per district
    out_rows = []
    for district, g in df.groupby('district'):
        g = g.sort_values('week_start').reset_index(drop=True)
        # create lag features for rain and ndvi
        for lag in [1,2,3]:  # weeks; 1 ~ 1 week, 2 ~ 2 weeks (approx 7/14/21 days)
            g[f'rain_lag_{lag}'] = g['rain_sum'].shift(lag)
            g[f'ndvi_lag_{lag}'] = g['ndvi_mean'].shift(lag)
            g[f'cases_lag_{lag}'] = g['cases'].shift(lag)
        # rolling means
        g['rain_3wk_mean'] = g['rain_sum'].rolling(window=3, min_periods=1).mean()
        g['ndvi_3wk_mean'] = g['ndvi_mean'].rolling(window=3, min_periods=1).mean()
        # season flags: month / monsoon (Jun-Sep)
        g['month'] = g['week_start'].dt.month
        g['monsoon'] = g['month'].isin([6,7,8,9]).astype(int)
        # neighbor average (optional) - placeholder 0 (we'll fill if adjacency provided)
        g['neighbor_rain_mean'] = 0.0
        out_rows.append(g)
    df_feat = pd.concat(out_rows, axis=0).reset_index(drop=True)
    # fill NaNs
    df_feat = df_feat.fillna(0)
    # target: next_week_cases (shift -1)
    df_feat['target_cases_next'] = df_feat.groupby('district')['cases'].shift(-1).fillna(0).astype(int)
    # classification target: risk (0 low,1 med,2 high) based on threshold of next week cases
    def risk_bucket(x):
        if x==0: return 0
        if x<=5: return 1
        return 2
    df_feat['risk_next'] = df_feat['target_cases_next'].apply(risk_bucket)
    return df_feat

def main():
    inp = "data/processed/dengue_weekly_clean.csv"
    print("Loading", inp)
    df = pd.read_csv(inp)
    df_feat = build_features(df)
    out = "data/processed/features_matrix.csv"
    df_feat.to_csv(out, index=False)
    print("Saved features matrix to", out)

if __name__ == "__main__":
    main()