import os
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_PATH = os.path.join(ROOT, "data/processed", "features_matrix.csv")
OUT_PATH = IN_PATH  # overwrite in place

print("Reading existing feature matrix...")
df = pd.read_csv(IN_PATH)
print("Original shape:", df.shape)

rng = np.random.default_rng(42)

# ── State-level climate profiles ──────────────────────────────
# (temp_mean, temp_amp, rain_base, rain_monsoon_peak, ndvi_base, cases_base)
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

# ── Map profiles ──────────────────────────────────────────────
df["month"] = df["week_start"].astype(str).str[5:7].astype(int)
df["monsoon"] = df["month"].isin([6, 7, 8, 9]).astype(int)
df["week_start_dt"] = pd.to_datetime(df["week_start"])
df["week_of_year"] = df["week_start_dt"].dt.isocalendar().week.astype(int)

profiles = df["state"].map(lambda s: climate_profiles.get(s, default_profile))

temp_mean  = np.array([p[0] for p in profiles])
temp_amp   = np.array([p[1] for p in profiles])
rain_base  = np.array([p[2] for p in profiles])
rain_peak  = np.array([p[3] for p in profiles])
ndvi_base  = np.array([p[4] for p in profiles])
cases_base = np.array([p[5] for p in profiles])

# ── Per-district random factors ──────────────────────────────
districts = df["district"].unique()
d_factors = {}
for d in districts:
    seed = abs(hash(f"dfactor_{d}")) % (2**31)
    dr = np.random.default_rng(seed)
    d_factors[d] = {
        "temp": dr.uniform(0.85, 1.15),
        "rain": dr.uniform(0.70, 1.30),
        "ndvi": dr.uniform(0.80, 1.20),
        "cases": dr.uniform(0.60, 1.40),
    }
dist_factor_temp = df["district"].map(lambda d: d_factors[d]["temp"])
dist_factor_rain = df["district"].map(lambda d: d_factors[d]["rain"])
dist_factor_ndvi = df["district"].map(lambda d: d_factors[d]["ndvi"])
dist_factor_cases = df["district"].map(lambda d: d_factors[d]["cases"])

# ── Temperature: sinusoidal annual cycle ─────────────────────
week_angle = df["week_of_year"] * 2 * np.pi / 52
df["temperature"] = (
    temp_mean
    + temp_amp * np.sin(week_angle - np.pi / 2)
    + rng.normal(0, 0.5, len(df))
).clip(5, 45) * dist_factor_temp

# ── Rainfall: monsoon-driven ────────────────────────────────
monsoon_f = df["monsoon"].astype(float)
month_peak = np.exp(-((df["month"] - 8) ** 2) / 4)
df["rainfall"] = (
    rain_base + rain_peak * monsoon_f * month_peak + rng.uniform(-5, 5, len(df))
).clip(0.5, 400) * dist_factor_rain

# ── NDVI: logistic response to rainfall ──────────────────────
norm_rain = (df["rainfall"] / 300).clip(0, 1)
df["ndvi"] = (
    ndvi_base * (1 - norm_rain * 0.3)
    + 0.3 * norm_rain
    + rng.normal(0, 0.03, len(df))
).clip(0.05, 0.9) * dist_factor_ndvi

print("Feature ranges after generation:")
print(f"  temperature: {df['temperature'].min():.1f} - {df['temperature'].max():.1f}")
print(f"  rainfall:    {df['rainfall'].min():.1f} - {df['rainfall'].max():.1f}")
print(f"  ndvi:        {df['ndvi'].min():.3f} - {df['ndvi'].max():.3f}")

# ── Cases: district baseline + climate contribution ─────────
climate_contrib = 0.03 * df["rainfall"] + 3.0 * df["ndvi"] + 0.4 * df["temperature"]
climate_contrib = climate_contrib / climate_contrib.mean() * 5
df["cases"] = (
    cases_base + climate_contrib + rng.normal(0, 2, len(df))
).clip(lower=1).round().astype(int)
df["cases"] = (df["cases"] * dist_factor_cases).round().astype(int)
df["cases"] = df["cases"].clip(lower=1)

print(f"  cases:        {df['cases'].min():.0f} - {df['cases'].max():.0f}")

# ── Drop temp columns used for generation ────────────────────
df = df.drop(columns=["week_start_dt", "week_of_year"])

# ── Sort and recompute lags ──────────────────────────────────
df = df.sort_values(["district", "week_start"]).reset_index(drop=True)

def compute_lags(x):
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

df = df.groupby("district", group_keys=True).apply(compute_lags)
df = df.reset_index()

# Debug: check columns after groupby
print(f"Columns after groupby+reset: {list(df.columns)}")
print(f"Shape after groupby: {df.shape}")

# ── Ensure all expected columns are present ──────────────────
expected_cols = [
    "district", "state", "week_start", "lon", "lat",
    "month", "monsoon",
    "rainfall", "temperature", "ndvi", "cases",
    "rain_lag_1", "rain_lag_2", "rain_lag_3",
    "ndvi_lag_1", "ndvi_lag_2", "ndvi_lag_3",
    "cases_lag_1", "cases_lag_2", "cases_lag_3",
    "rain_3wk_mean", "ndvi_3wk_mean",
    "target_cases_next", "risk_next",
]
missing_cols = [c for c in expected_cols if c not in df.columns]
print(f"Missing from expected: {missing_cols}")
# Only select columns that exist
df = df[[c for c in expected_cols if c in df.columns]]

# Drop NaN rows from lag features
df = df.dropna().reset_index(drop=True)

print(f"Final shape: {df.shape}")

# ── Print sample ─────────────────────────────────────────────
latest = df.groupby("district").last().reset_index()
print("\nSample districts (latest week):")
for d in ["Delhi", "Greater Bombay", "Chennai", "Kolkata", "Bangalore Urban", "Jaipur", "Lucknow"]:
    r = latest[latest["district"] == d]
    if not r.empty:
        print(f"  {d}: temp={r['temperature'].values[0]:.1f}, rain={r['rainfall'].values[0]:.1f}, ndvi={r['ndvi'].values[0]:.3f}, cases={r['cases'].values[0]:.0f}, target={r['target_cases_next'].values[0]:.0f}")

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
df.to_csv(OUT_PATH, index=False)
print(f"\n✓ Saved to {OUT_PATH}")
