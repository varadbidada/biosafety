# src/data/generate_synthetic.py
import numpy as np
import pandas as pd
import os
from datetime import datetime, timedelta

os.makedirs("data/processed", exist_ok=True)
np.random.seed(42)

districts = ["D_A", "D_B", "D_C", "D_D", "D_E"]
start = datetime(2018,1,1)
weeks = 156  # 3 years weekly

rows = []
for d in districts:
    base_cases = np.random.randint(0,5)
    seasonality = np.sin(np.linspace(0, 8*np.pi, weeks))  # seasonal
    rainfall = 100 * (0.5 + 0.5*seasonality) + 50*np.random.randn(weeks)
    ndvi = 0.3 + 0.2*(0.5+0.5*seasonality) + 0.05*np.random.randn(weeks)
    temp_base = 25 + 3*np.random.randn()
    for i in range(weeks):
        sd = start + timedelta(days=7*i)
        cases = max(0, int(base_cases + 0.05*rainfall[i] + np.random.poisson(2 + 2*seasonality[i])))
        rows.append({
            "district": d,
            "week_start": sd.strftime("%Y-%m-%d"),
            "rain_sum": float(max(0, rainfall[i])),
            "ndvi_mean": float(max(0, ndvi[i])),
            "temperature": float(temp_base + 2*np.sin(i/26.0) + np.random.randn()*0.5),
            "cases": cases
        })
df = pd.DataFrame(rows)
df.to_csv("data/processed/synthetic_dengue_weekly.csv", index=False)
print("Saved synthetic data to data/processed/synthetic_dengue_weekly.csv")