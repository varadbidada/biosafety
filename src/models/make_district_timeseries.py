import os
import json
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")
OUT_DIR = os.path.join(ROOT, "frontend/public/district_ts")

os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(DATA_PATH)

# Sort properly
df = df.sort_values(["district", "week_start"])

# Only need last 40 weeks
df = df.groupby("district").tail(40)

for dist, sub in df.groupby("district"):
    records = [
        {"week": r["week_start"], "value": float(r["risk_next"])}
        for _, r in sub.iterrows()
    ]
    with open(os.path.join(OUT_DIR, f"{dist}.json"), "w") as f:
        json.dump({"series": records}, f)

print("✓ Time-series JSON generated:", OUT_DIR)