import os
import pandas as pd
import numpy as np
import geopandas as gpd
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOJSON_PATH = os.path.join(ROOT, "frontend/public/india_districts.geojson")
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
# STATE-LEVEL CLIMATE PROFILES
# ----------------------------
# Each state gets: (temp_mean, temp_amp, rain_base, rain_monsoon_peak, ndvi_base, cases_base)
# temp_amp = amplitude of annual sine wave
# rain_base = dry-season weekly rainfall (mm)
# rain_monsoon_peak = additional weekly rainfall during monsoon peak (mm)
# cases_base = baseline weekly cases per 100k
climate_profiles = {
    "Kerala":          (27.5, 3.0, 30,  250, 0.70, 35),
    "Tamil Nadu":      (28.5, 4.0, 15,  180, 0.55, 28),
    "Karnataka":       (26.5, 4.5, 10,  200, 0.60, 25),
    "Andhra Pradesh":  (28.0, 4.0, 8,   160, 0.50, 22),
    "Telangana":       (27.5, 5.0, 8,   150, 0.45, 20),
    "Maharashtra":     (26.0, 5.0, 10,  200, 0.50, 24),
    "Gujarat":         (27.0, 6.0, 5,   180, 0.40, 18),
    "Rajasthan":       (26.0, 8.0, 3,   120, 0.25, 12),
    "Punjab":          (23.0, 8.0, 5,   140, 0.45, 15),
    "Haryana":         (24.5, 7.0, 5,   120, 0.40, 14),
    "Uttar Pradesh":   (25.5, 7.0, 8,   150, 0.45, 18),
    "Bihar":           (26.0, 5.5, 10,  160, 0.50, 22),
    "West Bengal":     (26.5, 5.0, 15,  200, 0.60, 28),
    "Jharkhand":       (25.0, 5.0, 10,  160, 0.50, 20),
    "Odisha":          (27.0, 4.0, 15,  220, 0.55, 26),
    "Chhattisgarh":    (26.0, 4.5, 12,  180, 0.55, 22),
    "Madhya Pradesh":  (25.5, 6.0, 8,   160, 0.45, 18),
    "Assam":           (24.0, 5.0, 20,  250, 0.65, 30),
    "Arunachal Pradesh": (20.0, 5.0, 25, 300, 0.70, 15),
    "Nagaland":        (22.0, 4.0, 15,  200, 0.60, 18),
    "Manipur":         (23.0, 4.0, 15,  200, 0.60, 18),
    "Mizoram":         (23.0, 3.5, 20,  250, 0.65, 20),
    "Tripura":         (24.0, 4.0, 20,  250, 0.65, 22),
    "Meghalaya":       (20.0, 4.0, 30,  350, 0.70, 20),
    "Sikkim":          (15.0, 6.0, 20,  250, 0.55, 12),
    "Himachal Pradesh": (18.0, 8.0, 10, 180, 0.45, 10),
    "Uttarakhand":     (20.0, 7.0, 10,  200, 0.50, 12),
    "Jammu and Kashmir": (15.0, 10.0, 10, 150, 0.40, 8),
    "Ladakh":          (8.0,  12.0, 2,   40,  0.15, 3),
    "Delhi":           (25.0, 8.0, 5,   140, 0.35, 16),
    "Chandigarh":      (24.0, 7.0, 5,   130, 0.40, 14),
    "Goa":             (27.0, 3.0, 20,  280, 0.65, 30),
    "Puducherry":      (28.5, 3.5, 15,  180, 0.55, 28),
    "Andaman Islands": (27.0, 2.0, 30,  300, 0.70, 25),
    "Dadra and Nagar Haveli": (26.0, 5.0, 10, 200, 0.50, 20),
    "Daman and Diu":   (27.0, 5.0, 8,   180, 0.45, 18),
    "Lakshadweep":     (28.0, 1.5, 25,  220, 0.65, 22),
}

default_profile = (26.0, 5.0, 10, 150, 0.45, 18)

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
# ADD STATE-SPECIFIC SYNTHETIC FEATURES WITH SEASONAL PATTERNS
# ----------------------------
rng = np.random.default_rng(42)

df["month"] = df["week_start"].dt.month
df["monsoon"] = df["month"].isin([6, 7, 8, 9]).astype(int)
df["week_of_year"] = df["week_start"].dt.isocalendar().week.astype(int)

# Assign climate profiles per state
state_profiles = df["state"].map(climate_profiles).fillna(lambda x: default_profile)
# Since fillna with callable doesn't work this way, use a different approach:
unknown = df[~df["state"].isin(climate_profiles)]["state"].unique()
for s in unknown:
    print(f"  Warning: no climate profile for '{s}', using defaults")
state_profiles = df["state"].map(lambda s: climate_profiles.get(s, default_profile))

temp_mean   = state_profiles.map(lambda p: p[0])
temp_amp    = state_profiles.map(lambda p: p[1])
rain_base   = state_profiles.map(lambda p: p[2])
rain_peak   = state_profiles.map(lambda p: p[3])
ndvi_base   = state_profiles.map(lambda p: p[4])
cases_base  = state_profiles.map(lambda p: p[5])

# Per-district random variation in baselines (±20% of state values)
district_rng = df.groupby("district").ngroup().map(
    lambda x: np.random.default_rng(abs(hash(f"district_{x}")) % (2**31))
)
# Pre-compute per-district factors
unique_districts = df["district"].unique()
district_factors = {}
for d in unique_districts:
    seed = abs(hash(f"factor_{d}")) % (2**31)
    drng = np.random.default_rng(seed)
    district_factors[d] = {
        "temp": drng.uniform(0.85, 1.15),
        "rain": drng.uniform(0.70, 1.30),
        "ndvi": drng.uniform(0.80, 1.20),
        "cases": drng.uniform(0.60, 1.40),
    }

# Temperature: sinusoidal annual cycle
# Peak in week ~20 (mid-May), trough in week ~46 (mid-November)
week_angle = df["week_of_year"] * 2 * np.pi / 52
df["temperature"] = (
    temp_mean
    + temp_amp * np.sin(week_angle - np.pi / 2)  # peak at week 20
    + rng.normal(0, 0.5, len(df))
).clip(5, 45)
# Apply district factor
df["temperature"] = df.apply(
    lambda row: row["temperature"] * district_factors[row["district"]]["temp"], axis=1
)

# Rainfall: monsoon-driven with district-specific intensity
# Monsoon months (Jun-Sep) get high rainfall, dry season gets baseline
monsoon_factor = df["monsoon"].astype(float)
# Peak rainfall in August (month 8)
month_peak = np.exp(-((df["month"] - 8) ** 2) / 4)
df["rainfall"] = (
    rain_base
    + rain_peak * monsoon_factor * month_peak
    + rng.uniform(-5, 5, len(df))
).clip(0.5, 400)
df["rainfall"] = df.apply(
    lambda row: row["rainfall"] * district_factors[row["district"]]["rain"], axis=1
)

# NDVI: follows rainfall with logistic response
norm_rain = (df["rainfall"] / 300).clip(0, 1)
df["ndvi"] = (
    ndvi_base * (1 - norm_rain * 0.3)
    + 0.3 * norm_rain
    + rng.normal(0, 0.03, len(df))
).clip(0.05, 0.9)
df["ndvi"] = df.apply(
    lambda row: row["ndvi"] * district_factors[row["district"]]["ndvi"], axis=1
)

# Cases: district-specific baseline + climate contribution + autoregressive component
climate_contribution = (
    0.03 * df["rainfall"]
    + 3.0 * df["ndvi"]
    + 0.4 * df["temperature"]
)
# Scale contribution to be ~25% of total cases
climate_contribution = climate_contribution / climate_contribution.mean() * 5

df["cases"] = (
    cases_base
    + climate_contribution
    + rng.normal(0, 2, len(df))
).clip(lower=1).round().astype(int)
df["cases"] = df.apply(
    lambda row: max(1, round(row["cases"] * district_factors[row["district"]]["cases"])), axis=1
)

df = df.drop(columns=["week_of_year"])

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
print("Sample districts:")
latest = df.groupby("district").last().reset_index()
for d in ["Delhi", "Greater Bombay", "Chennai", "Kolkata", "Bangalore Urban", "Jaipur", "Lucknow"]:
    r = latest[latest["district"] == d]
    if not r.empty:
        print(f"  {d}: temp={r['temperature'].values[0]:.1f}, rain={r['rainfall'].values[0]:.1f}, ndvi={r['ndvi'].values[0]:.3f}, cases={r['cases'].values[0]:.0f}, target={r['target_cases_next'].values[0]:.0f}")

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
df.to_csv(OUT_PATH, index=False)

print("✓ Saved:", OUT_PATH)