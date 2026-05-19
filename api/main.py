import os
import json

import torch
import torch.nn as nn
import numpy as np
import xgboost as xgb
import joblib
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# -----------------------------
# Initialize FastAPI app ONCE
# -----------------------------
app = FastAPI()

# -----------------------------
# Enable CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Define the SAME LSTM architecture
# -----------------------------
class LSTMModel(nn.Module):
    def __init__(self, input_size=10, hidden_size=64, num_layers=2, output_size=1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True
        )
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.fc(out[:, -1, :])
        return out

# -----------------------------
# Load Models
# -----------------------------
xgb_reg = xgb.XGBRegressor()
xgb_reg.load_model("../models/xgb_reg.json")

xgb_clf = xgb.XGBClassifier()
xgb_clf.load_model("../models/xgb_clf.json")

# -----------------------------
# Load LSTM model
# -----------------------------
# Use the same feature ordering as training (17 features from feature_cols.json)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_COLS_PATH = os.path.join(ROOT, "models", "feature_cols.json")
feature_cols = json.load(open(FEATURE_COLS_PATH))
INPUT_SIZE = len(feature_cols)

lstm_scaler = joblib.load(os.path.join(ROOT, "models", "lstm_scaler.pkl"))

lstm_model = LSTMModel(
    input_size=INPUT_SIZE,
    hidden_size=96,  # must match training hidden size
    num_layers=2,
    output_size=1,
)
state_dict = torch.load(os.path.join(ROOT, "models", "lstm_model_full.pt"), map_location="cpu")
lstm_model.load_state_dict(state_dict)
lstm_model.eval()

# -----------------------------
# API Input Schema
# -----------------------------
class InputData(BaseModel):
    """Numeric feature vector expected by the models.

    Option B: the backend is responsible for turning this raw prediction
    into a higher-level risk assessment that the UI can consume.
    """

    features: list[float]


# -----------------------------
# Risk configuration (Option B)
# -----------------------------
# You can tweak these thresholds later without changing the frontend.
LOW_RISK_THRESHOLD = 10.0
MEDIUM_RISK_THRESHOLD = 50.0


def classify_risk(predicted_cases: float) -> str:
    """Map the predicted case count to a human-readable risk bucket.

    This is a simple piecewise rule; adjust as needed.
    """
    if predicted_cases < LOW_RISK_THRESHOLD:
        return "low"
    if predicted_cases < MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "high"


# -----------------------------
# Prediction Endpoint (manual feature vector)
# -----------------------------
@app.post("/predict")
def predict(data: InputData):
    # Shape: (1, n_features)
    x = np.array(data.features, dtype=float).reshape(1, -1)

    # XGB Regression
    reg_pred = float(xgb_reg.predict(x)[0])

    # XGB Classification (e.g. outbreak yes/no)
    clf_pred = int(xgb_clf.predict(x)[0])

    # LSTM time-series prediction
    x_scaled = lstm_scaler.transform(x)
    x_lstm = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0)
    lstm_pred = float(lstm_model(x_lstm).item())

    # Simple ensemble of regression and LSTM
    ensemble_pred = float((reg_pred + lstm_pred) / 2.0)

    # High-level outputs consumed by the frontend widgets
    predicted_cases_next_week = max(0.0, ensemble_pred)
    risk_level = classify_risk(predicted_cases_next_week)

    return {
        # High-level API fields for UI components
        "predicted_cases_next_week": predicted_cases_next_week,
        "risk_level": risk_level,
        # Raw model outputs (useful for debugging / advanced UIs)
        "xgb_reg": reg_pred,
        "xgb_clf": clf_pred,
        "lstm": lstm_pred,
        "ensemble": ensemble_pred,
    }


# -----------------------------
# Available districts (for dropdowns)
# -----------------------------
@app.get("/districts")
def list_districts():
    import pandas as pd

    data_path = os.path.join(ROOT, "data", "processed", "features_matrix.csv")
    df = pd.read_csv(data_path, usecols=["district"]).dropna()
    districts = sorted(df["district"].unique().tolist())
    return {"districts": districts}


# -----------------------------
# Prediction from latest historical row
# -----------------------------
@app.get("/predict_latest")
def predict_latest(district: str = "Adilabad"):
    """Fetch the most recent feature row for a district and run a prediction.

    This lets the frontend trigger a prediction without the user
    manually entering 17 feature values.

    The models themselves are 1-week ahead forecasters, so here we
    expose that as "1 week" and then derive simple 2- and 3-week
    horizons so the UI can say "next 1/2/3 weeks" instead of showing
    only a past calendar date from the dataset.
    """
    import pandas as pd

    data_path = os.path.join(ROOT, "data", "processed", "features_matrix.csv")
    df = pd.read_csv(data_path)

    # Restrict to the requested district, if present
    df_d = df[df["district"] == district].copy()
    if df_d.empty:
        # Fall back to global latest row if district not found
        df_d = df.copy()

    df_d["week_start"] = pd.to_datetime(df_d["week_start"])
    latest_row = df_d.sort_values("week_start").iloc[-1]

    # Build feature vector using the same columns / ordering as training
    features = [float(latest_row[col]) for col in feature_cols]

    # Reuse the core prediction logic
    x = np.array(features, dtype=float).reshape(1, -1)

    reg_pred = float(xgb_reg.predict(x)[0])
    clf_pred = int(xgb_clf.predict(x)[0])

    x_scaled = lstm_scaler.transform(x)
    x_lstm = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0)
    lstm_pred = float(lstm_model(x_lstm).item())

    ensemble_pred = float((reg_pred + lstm_pred) / 2.0)

    # 1‑week ahead prediction from the ensemble
    predicted_cases_1w = max(0.0, ensemble_pred)

    # Very simple derived 2‑ and 3‑week horizons so the UI can
    # display a short forecast strip. You can replace this later
    # with a proper multi‑step model if desired.
    predicted_cases_2w = max(0.0, ensemble_pred * 1.05)
    predicted_cases_3w = max(0.0, ensemble_pred * 1.10)

    risk_level = classify_risk(predicted_cases_1w)

    # Historical week in the dataset
    history_week_start = latest_row["week_start"]

    # Future forecast weeks relative to the last historical week
    week_1 = history_week_start + pd.Timedelta(days=7)
    week_2 = history_week_start + pd.Timedelta(days=14)
    week_3 = history_week_start + pd.Timedelta(days=21)

    return {
        "district": str(latest_row["district"]),
        # Keep the original field for backwards compatibility, but
        # the UI should treat this as the last historical data week.
        "week_start": str(history_week_start.date()),
        "history_week_start": str(history_week_start.date()),
        "forecast_week_1": str(week_1.date()),
        "forecast_week_2": str(week_2.date()),
        "forecast_week_3": str(week_3.date()),
        # 1‑week ahead (for existing UI)
        "predicted_cases_next_week": predicted_cases_1w,
        # Explicit 1/2/3 week horizons
        "predicted_cases_1w": predicted_cases_1w,
        "predicted_cases_2w": predicted_cases_2w,
        "predicted_cases_3w": predicted_cases_3w,
        "risk_level": risk_level,
        "xgb_reg": reg_pred,
        "xgb_clf": clf_pred,
        "lstm": lstm_pred,
        "ensemble": ensemble_pred,
    }


# -----------------------------
# Model accuracy endpoint (historic backtest)
# -----------------------------
@app.get("/model_accuracy")
def model_accuracy(district: str | None = None):
    """Return simple error metrics for XGB, LSTM and the ensemble.

    Uses the backtest file data/processed/ensemble_results.csv which
    stores true cases and predictions over time. This is meant for
    displaying model accuracy in the UI, not for training.
    """
    import pandas as pd

    metrics_path = os.path.join(ROOT, "data", "processed", "ensemble_results.csv")
    df = pd.read_csv(metrics_path)

    if district:
        df = df[df["district"] == district]
        if df.empty:
            return {
                "district": district,
                "metrics": {},
                "message": "No backtest rows for this district",
            }

    def compute_metrics(col: str):
        if col not in df.columns:
            return None
        sub = df[["true_cases", col]].dropna()
        if sub.empty:
            return None
        y_true = sub["true_cases"].to_numpy(dtype=float)
        y_pred = sub[col].to_numpy(dtype=float)
        err = y_pred - y_true
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err ** 2)))
        # Avoid division by zero by clamping the denominator to >= 1
        denom = np.maximum(1.0, np.abs(y_true))
        mape = float(np.mean(np.abs(err) / denom) * 100.0)
        return {
            "n_samples": int(len(sub)),
            "mae": mae,
            "rmse": rmse,
            "mape": mape,
        }

    metrics = {}
    for col, key in [("xgb_pred", "xgb"), ("lstm_pred", "lstm"), ("ensemble_pred", "ensemble")]:
        m = compute_metrics(col)
        if m is not None:
            metrics[key] = m

    return {
        "district": district or "ALL",
        "horizon": "1-week ahead",
        "metrics": metrics,
    }
