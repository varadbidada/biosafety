"""
Fetch real weather data from Open-Meteo API for Indian districts.

Replaces synthetic weather columns (rainfall, temperature, ndvi) in the
features matrix with real historical data. Falls back to synthetic data
for any district where the API call fails.

Usage:
    python scripts/fetch_real_weather.py                    # all districts
    python scripts/fetch_real_weather.py --max-districts 5  # first 5 only
    python scripts/fetch_real_weather.py --district Adilabad  # single
"""

import os
import sys
import time
import json
import argparse

import requests as http_requests
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

INPUT_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")
OUTPUT_PATH = os.path.join(ROOT, "data/processed/features_matrix_real_weather.csv")
COORDS_CACHE_PATH = os.path.join(ROOT, "data/processed/district_coords_cache.json")

OPEN_METEO_BASE = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_DELAY = 0.25  # seconds between API calls


def load_coords_cache() -> dict:
    if os.path.exists(COORDS_CACHE_PATH):
        with open(COORDS_CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_coords_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(COORDS_CACHE_PATH), exist_ok=True)
    with open(COORDS_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_coords(district: str, cache: dict) -> tuple[float, float] | None:
    if district in cache:
        return cache[district][0], cache[district][1]
    try:
        r = http_requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"format": "json", "q": f"{district}, India", "limit": 1},
            headers={"User-Agent": "DengueCastData/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            cache[district] = [lat, lon]
            time.sleep(1.0)  # Nominatim rate limit: 1 req/sec
            return lat, lon
    except Exception as e:
        print(f"  ⚠ Nominatim failed for {district}: {e}")
    return None


def fetch_weekly_weather(
    lat: float, lon: float, start_date: str, end_date: str
) -> pd.DataFrame | None:
    """Fetch daily weather from Open-Meteo and aggregate to weekly."""
    try:
        r = http_requests.get(
            OPEN_METEO_BASE,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("daily")
        if not data or "time" not in data:
            return None

        daily = pd.DataFrame({
            "date": pd.to_datetime(data["time"]),
            "t_max": data["temperature_2m_max"],
            "t_min": data["temperature_2m_min"],
            "precip": data["precipitation_sum"],
        }).dropna()

        daily["week_start"] = daily["date"] - pd.to_timedelta(daily["date"].dt.dayofweek, unit="D")

        weekly = daily.groupby("week_start").agg(
            rainfall=("precip", "sum"),
            temperature=("t_max", "mean"),
        ).reset_index()

        weekly["temperature"] = weekly["temperature"].round(1)
        weekly["rainfall"] = weekly["rainfall"].round(1)

        return weekly
    except Exception as e:
        print(f"  ⚠ Open-Meteo failed ({lat:.2f}, {lon:.2f}): {e}")
    return None


def approx_ndvi_from_rainfall(rainfall: pd.Series) -> pd.Series:
    """Approximate NDVI from rainfall using a simple logistic model."""
    norm = rainfall.clip(0, 300) / 300.0
    ndvi = 0.1 + 0.7 * (1 / (1 + np.exp(-6 * (norm - 0.3))))
    return ndvi.round(4)


def main():
    parser = argparse.ArgumentParser(description="Fetch real weather data for Indian districts")
    parser.add_argument("--max-districts", type=int, default=None, help="Limit number of districts")
    parser.add_argument("--district", type=str, default=None, help="Process a single district")
    args = parser.parse_args()

    print("=" * 50)
    print("Real Weather Data Integration (Open-Meteo)")
    print("=" * 50)

    df = pd.read_csv(INPUT_PATH)
    df["week_start"] = pd.to_datetime(df["week_start"])
    print(f"Loaded {len(df):,} rows, {df['district'].nunique()} districts")
    print(f"Date range: {df['week_start'].min().date()} to {df['week_start'].max().date()}")

    all_districts = sorted(df["district"].unique())
    if args.district:
        districts = [args.district]
    elif args.max_districts:
        districts = all_districts[: args.max_districts]
    else:
        districts = all_districts

    print(f"Processing {len(districts)} district(s)")

    coords_cache = load_coords_cache()
    updated_count = 0
    failed_districts = []

    for i, dist in enumerate(districts):
        print(f"\n[{i+1}/{len(districts)}] {dist}")

        coords = fetch_coords(dist, coords_cache)
        if coords is None:
            print(f"  ✗ No coordinates found, skipping")
            failed_districts.append(dist)
            continue

        lat, lon = coords
        print(f"  Coordinates: {lat:.4f}, {lon:.4f}")

        weekly = fetch_weekly_weather(
            lat, lon,
            df["week_start"].min().strftime("%Y-%m-%d"),
            df["week_start"].max().strftime("%Y-%m-%d"),
        )

        if weekly is None or weekly.empty:
            print(f"  ✗ No weather data, skipping")
            failed_districts.append(dist)
            continue

        weekly["ndvi"] = approx_ndvi_from_rainfall(weekly["rainfall"])

        mask = df["district"] == dist
        existing = df.loc[mask, ["district", "week_start"]].merge(
            weekly, on="week_start", how="left"
        )

        merge_cols = ["rainfall", "temperature", "ndvi"]
        for col in merge_cols:
            df.loc[mask, col] = existing[col].values

        updated_count += 1

        time.sleep(REQUEST_DELAY)

    save_coords_cache(coords_cache)

    # Recalculate lag features and rolling means
    print(f"\nRecalculating lag features...")
    df = df.sort_values(["district", "week_start"])

    df["month"] = df["week_start"].dt.month
    df["monsoon"] = df["month"].isin([6, 7, 8, 9]).astype(int)

    for dist in df["district"].unique():
        mask = df["district"] == dist
        d = df.loc[mask].copy()
        d["rain_lag_1"] = d["rainfall"].shift(1)
        d["rain_lag_2"] = d["rainfall"].shift(2)
        d["rain_lag_3"] = d["rainfall"].shift(3)
        d["ndvi_lag_1"] = d["ndvi"].shift(1)
        d["ndvi_lag_2"] = d["ndvi"].shift(2)
        d["ndvi_lag_3"] = d["ndvi"].shift(3)
        d["cases_lag_1"] = d["cases"].shift(1)
        d["cases_lag_2"] = d["cases"].shift(2)
        d["cases_lag_3"] = d["cases"].shift(3)
        d["rain_3wk_mean"] = d["rainfall"].rolling(3).mean()
        d["ndvi_3wk_mean"] = d["ndvi"].rolling(3).mean()
        d["target_cases_next"] = d["cases"].shift(-1)
        d["risk_next"] = (d["target_cases_next"] > d["cases"].mean()).astype(int)
        df.loc[mask, d.columns] = d

    df = df.dropna().reset_index(drop=True)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\n{'=' * 50}")
    print(f"Done! {updated_count}/{len(districts)} districts updated")
    if failed_districts:
        print(f"Failed ({len(failed_districts)}): {', '.join(failed_districts[:10])}")
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Final shape: {df.shape}")
    print(f"Coords cache: {COORDS_CACHE_PATH}")


if __name__ == "__main__":
    main()
