import os
import pandas as pd
import numpy as np
import geopandas as gpd
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOJSON_PATH = os.path.join(ROOT, "web/public/india_districts.geojson")
OUT_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")

print("GeoJSON:", GEOJSON_PATH)

# ----------------------------
# LOAD DISTRICT GEOJSON
# ----------------------------
gdf = gpd.read_file(GEOJSON_PATH)

gdf["district"] = gdf["NAME_2"].astype(str).str.strip()
gdf["state"] = gdf["NAME_1"].astype(str).str.strip()

# Use projected CRS for centroid accuracy
gdf = gdf.to_crs(3857)
gdf["lon"] = gdf.centroid.to_crs(4326).x
gdf["lat"] = gdf.centroid.to_crs(4326).y
gdf = gdf.to_crs(4326)

# ----------------------------
# GENERATE WEEKLY DATES
# ----------------------------
dates = pd.date_range("2015-01-05", "2024-12-25", freq="W-MON")
print("Total weeks:", len(dates))

rows = []
for _, r in gdf.iterrows():
    for d in dates:
        rows.append({
            "district": r["district"],
            "state": r["state"],
            "week_start": d,
            "lon": r["lon"],
            "lat": r["lat"],
        })

df = pd.DataFrame(rows)
print("Raw:", df.shape)

# ----------------------------
# ADD SYNTHETIC FEATURES
# ----------------------------
rng = np.random.default_rng(42)

df["month"] = df["week_start"].dt.month
df["monsoon"] = df["month"].isin([6, 7, 8, 9]).astype(int)

df["rainfall"] = rng.uniform(5, 150, len(df))
df["temperature"] = rng.uniform(20, 34, len(df))
df["ndvi"] = rng.uniform(0.1, 0.8, len(df))

base = (df["rainfall"] * 0.04 + df["ndvi"] * 3 + df["temperature"] * 0.6)
df["cases"] = (base + rng.normal(0, 3, len(df))).clip(lower=0).astype(int)

# ----------------------------
# LAG FEATURES
# ----------------------------
df = df.sort_values(["district", "week_start"])

def add_lags(x):
    x["rain_lag_1"] = x["rainfall"].shift(1)
    x["rain_lag_2"] = x["rainfall"].shift(2)
    x["rain_lag_3"] = x["rainfall"].shift(3)

    x["ndvi_lag_1"] = x["ndvi"].shift(1)
    x["ndvi_lag_2"] = x["ndvi"].shift(2)
    x["ndvi_lag_3"] = x["ndvi"].shift(3)

    x["cases_lag_1"] = x["cases"].shift(1)
    x["cases_lag_2"] = x["cases"].shift(2)
    x["cases_lag_3"] = x["cases"].shift(3)

    x["rain_3wk_mean"] = x["rainfall"].rolling(3).mean()
    x["ndvi_3wk_mean"] = x["ndvi"].rolling(3).mean()

    x["target_cases_next"] = x["cases"].shift(-1)
    x["risk_next"] = (x["target_cases_next"] > x["cases"].mean()).astype(int)

    return x

df = df.groupby("district").apply(add_lags).reset_index(drop=True)

df = df.dropna()

print("Final:", df.shape)

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
df.to_csv(OUT_PATH, index=False)

print("✓ Saved:", OUT_PATH)