# src/data/preprocess.py
"""
Preprocess GEE export or synthetic weekly CSV into cleaned weekly matrix.
Input: data/raw/india_district_weekly.csv  OR data/processed/synthetic_dengue_weekly.csv
Output: data/processed/dengue_weekly_clean.csv
Usage:
  python src/data/preprocess.py --input data/raw/india_district_weekly.csv --cases data/raw/dengue_cases_weekly.csv
Or to use synthetic:
  python src/data/preprocess.py --input data/processed/synthetic_dengue_weekly.csv
"""
import pandas as pd
import numpy as np
import argparse
import os

os.makedirs("data/processed", exist_ok=True)

def load_input(path):
    df = pd.read_csv(path)
    # normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def fill_and_align(df):
    # Expect columns like: district, week_start or start_date, ndvi_mean, rain_sum, cases (optional)
    # Normalize date column
    date_cols = [c for c in df.columns if 'start' in c or 'date' in c]
    if len(date_cols) == 0:
        raise ValueError("No date column found. Expected week_start or start_date column.")
    date_col = date_cols[0]
    df[date_col] = pd.to_datetime(df[date_col])
    # rename to week_start
    df = df.rename(columns={date_col: 'week_start'})
    # If end_date exists keep it, else compute
    if 'end_date' not in df.columns:
        df['week_end'] = df['week_start'] + pd.Timedelta(days=6)
    else:
        df['week_end'] = pd.to_datetime(df['end_date'])
    # Ensure numeric columns exist
    for col in ['ndvi_mean', 'rain_sum', 'temperature', 'cases']:
        if col not in df.columns:
            df[col] = np.nan
    # Fill NDVI nulls with group median (district)
    df['ndvi_mean'] = df['ndvi_mean'].astype(float)
    df['rain_sum'] = df['rain_sum'].astype(float)
    df['temperature'] = df['temperature'].astype(float)
    # fill by district median then global median
    df['ndvi_mean'] = df.groupby('district')['ndvi_mean'].transform(lambda x: x.fillna(x.median()))
    df['ndvi_mean'] = df['ndvi_mean'].fillna(df['ndvi_mean'].median())
    df['rain_sum'] = df.groupby('district')['rain_sum'].transform(lambda x: x.fillna(x.median()))
    df['rain_sum'] = df['rain_sum'].fillna(0.0)
    df['temperature'] = df['temperature'].fillna(df['temperature'].median())
    # Cases: if missing, set to 0 (for synthetic or missing weeks)
    if 'cases' in df.columns:
        df['cases'] = df['cases'].fillna(0).astype(int)
    else:
        df['cases'] = 0
    # Sort
    df = df.sort_values(['district','week_start']).reset_index(drop=True)
    return df

def main(args):
    print("Loading input:", args.input)
    df = load_input(args.input)
    df_clean = fill_and_align(df)
    out = "data/processed/dengue_weekly_clean.csv"
    df_clean.to_csv(out, index=False)
    print("Saved cleaned weekly CSV to", out)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to GEE output or synthetic csv")
    p.add_argument("--cases", required=False, help="Optional separate dengue cases CSV (not used)")
    args = p.parse_args()
    main(args)