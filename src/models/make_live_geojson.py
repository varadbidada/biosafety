import os
import json
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xgboost as xgb
from sklearn.preprocessing import StandardScaler

# --------------------------------------
# PATHS
# --------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")
GEOJSON_PATH = os.path.join(ROOT, "web/public/india_districts.geojson")
MODELS_PATH = os.path.join(ROOT, "models")
OUTPUT_GEOJSON = os.path.join(ROOT, "web/public/live_risk.geojson")

print("ROOT =", ROOT)
print("Loading data from:", DATA_PATH)

# --------------------------------------
# LOAD FEATURE COLS
# --------------------------------------
feature_cols = json.load(open(os.path.join(MODELS_PATH, "feature_cols.json")))
INPUT_SIZE = len(feature_cols)
print("Detected INPUT_SIZE =", INPUT_SIZE)

# --------------------------------------
# LSTM ARCHITECTURE
# --------------------------------------
class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size=96, num_layers=2, output_size=1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


# --------------------------------------
# LOAD MODELS
# --------------------------------------
print("Loading XGBoost...")

xgb_reg = xgb.XGBRegressor()
xgb_reg.load_model(os.path.join(MODELS_PATH, "xgb_reg.json"))

xgb_clf = xgb.XGBClassifier()
xgb_clf.load_model(os.path.join(MODELS_PATH, "xgb_clf.json"))

print("Loading LSTM...")

lstm_scaler = joblib.load(os.path.join(MODELS_PATH, "lstm_scaler.pkl"))

lstm_model = LSTMModel(input_size=INPUT_SIZE)
state = torch.load(os.path.join(MODELS_PATH, "lstm_model_full.pt"), map_location="cpu")
lstm_model.load_state_dict(state)
lstm_model.eval()

print("✓ Loaded all models successfully")

# --------------------------------------
# LOAD FEATURE MATRIX (latest rows)
# --------------------------------------
df = pd.read_csv(DATA_PATH)

latest = df.sort_values("week_start").groupby("district").tail(1)
latest = latest.fillna(0)

X = latest[feature_cols].values

# --------------------------------------
# PREDICT
# --------------------------------------
reg_pred = xgb_reg.predict(X)

X_scaled = lstm_scaler.transform(X)
X_lstm = torch.tensor(X_scaled, dtype=torch.float32).unsqueeze(1)
lstm_pred = lstm_model(X_lstm).detach().numpy().flatten()

risk_raw = (reg_pred + lstm_pred) / 2
risk_norm = (risk_raw - risk_raw.min()) / (risk_raw.max() - risk_raw.min() + 1e-9)

latest["risk"] = risk_norm

# Map district to risk
risk_map = dict(zip(latest["district"], latest["risk"]))

# --------------------------------------
# UPDATE GEOJSON (NAME_2 → district)
# --------------------------------------
with open(GEOJSON_PATH, "r") as f:
    geo = json.load(f)

updated = 0

for feature in geo["features"]:
    props = feature["properties"]

    # district name in your file
    district = (
        props.get("NAME_2")
        or props.get("name_2")
        or props.get("district")
        or props.get("DISTRICT")
        or None
    )

    if not district:
        feature["properties"]["risk"] = 0
        continue

    risk = float(risk_map.get(district, 0))
    feature["properties"]["risk"] = risk
    updated += 1

with open(OUTPUT_GEOJSON, "w") as f:
    json.dump(geo, f)

print(f"✓ Saved updated live_risk.geojson → {OUTPUT_GEOJSON}")
print(f"Updated {updated} districts.")