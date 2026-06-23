import os
import json
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import torch
import xgboost as xgb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models.lstm_model import LSTMModel

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")
MODELS_PATH = os.path.join(ROOT, "models")
OUTPUT_PATH = os.path.join(ROOT, "data/processed/ensemble_results.csv")
METRICS_PATH = os.path.join(ROOT, "data/processed/eval_metrics.json")
SEQ_LEN = 10


def load_models():
    with open(os.path.join(MODELS_PATH, "feature_cols.json")) as f:
        feature_cols = json.load(f)
    INPUT_SIZE = len(feature_cols)

    xgb_model = xgb.XGBRegressor()
    xgb_model.load_model(os.path.join(MODELS_PATH, "xgb_reg.json"))

    scaler = joblib.load(os.path.join(MODELS_PATH, "lstm_scaler.pkl"))

    lstm_model = LSTMModel(input_size=INPUT_SIZE)
    lstm_model.load_state_dict(torch.load(
        os.path.join(MODELS_PATH, "lstm_model_full.pt"), map_location="cpu"
    ))
    lstm_model.eval()

    return xgb_model, lstm_model, scaler, feature_cols


def load_feature_data():
    df = pd.read_csv(DATA_PATH)
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


def lstm_predict_sequences(df, feature_cols, lstm_model, scaler, seq_len=SEQ_LEN):
    """Generate LSTM predictions per district using sliding windows (batched)."""
    all_preds = []
    districts = df["district"].unique()
    total = len(districts)

    for idx, district in enumerate(districts):
        if (idx + 1) % 50 == 0:
            print(f"  LSTM progress: {idx+1}/{total} districts", flush=True)

        g = df[df["district"] == district].sort_values("week_start").reset_index(drop=True)
        values = g[feature_cols].values

        if len(values) < seq_len:
            all_preds.extend([np.nan] * len(values))
            continue

        # Transform ALL data for this district at once
        scaled = scaler.transform(values)

        # Build sequences vectorized
        n = len(values)
        sequences = np.zeros((n - seq_len + 1, seq_len, len(feature_cols)))
        for i in range(seq_len):
            sequences[:, i, :] = scaled[i : n - seq_len + i + 1]

        # Batched LSTM prediction
        seq_tensor = torch.tensor(sequences, dtype=torch.float32)
        with torch.no_grad():
            preds = lstm_model(seq_tensor).squeeze().numpy()
        if preds.ndim == 0:
            preds = np.array([preds.item()])

        # Pad initial rows with NaN (no history to form a full sequence)
        padded = np.full(seq_len - 1, np.nan)
        district_preds = np.concatenate([padded, preds])
        all_preds.extend(district_preds.tolist())

    return np.array(all_preds)


def compute_metrics(y_true, y_pred, prefix=""):
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_t, y_p = y_true[mask], y_pred[mask]

    if len(y_t) == 0:
        return {}

    mae = mean_absolute_error(y_t, y_p)
    rmse = np.sqrt(mean_squared_error(y_t, y_p))
    denom = np.maximum(1.0, np.abs(y_t))
    mape = float(np.mean(np.abs(y_p - y_t) / denom) * 100.0)
    r2 = r2_score(y_t, y_p)

    return {
        "n_samples": int(len(y_t)),
        "mae": float(f"{mae:.2f}"),
        "rmse": float(f"{rmse:.2f}"),
        "mape": float(f"{mape:.2f}"),
        "r2": float(f"{r2:.3f}"),
    }


def optimize_ensemble_weights(xgb_preds, lstm_preds, true_cases):
    from sklearn.metrics import mean_squared_error

    mask = ~(np.isnan(xgb_preds) | np.isnan(lstm_preds) | np.isnan(true_cases))
    x, l, t = xgb_preds[mask], lstm_preds[mask], true_cases[mask]

    best_weight = 0.5
    best_rmse = float("inf")

    for w in np.arange(0.0, 1.01, 0.05):
        ensemble = w * x + (1 - w) * l
        rmse = np.sqrt(mean_squared_error(t, ensemble))
        if rmse < best_rmse:
            best_rmse = rmse
            best_weight = w

    return best_weight, best_rmse


def run_evaluation():
    print("=" * 50)
    print("Ensemble Evaluation")
    print("=" * 50)

    print("\nLoading feature data...")
    df = load_feature_data()
    print(f"Data shape: {df.shape}")

    print("Loading models...")
    xgb_model, lstm_model, scaler, feature_cols = load_models()

    print("Running XGBoost predictions...")
    X = df[feature_cols].fillna(0)
    xgb_preds = xgb_model.predict(X)

    print("Running LSTM predictions...")
    lstm_preds = lstm_predict_sequences(df, feature_cols, lstm_model, scaler)

    min_len = min(len(xgb_preds), len(lstm_preds))
    xgb_preds = xgb_preds[:min_len]
    lstm_preds = lstm_preds[:min_len]
    true_cases = df["target_cases_next"].values[:min_len]

    print("\nOptimizing ensemble weights...")
    best_weight, best_rmse = optimize_ensemble_weights(xgb_preds, lstm_preds, true_cases)
    ensemble_preds = best_weight * xgb_preds + (1 - best_weight) * lstm_preds

    print(f"Optimal weight: XGB={best_weight:.2f}, LSTM={1-best_weight:.2f}")
    print(f"Best ensemble RMSE: {best_rmse:.2f}")

    print("\n--- Model Metrics ---")
    metrics = {
        "ensemble_weight_xgb": best_weight,
        "ensemble_weight_lstm": 1 - best_weight,
        "xgb": compute_metrics(true_cases, xgb_preds),
        "lstm": compute_metrics(true_cases, lstm_preds),
        "ensemble": compute_metrics(true_cases, ensemble_preds),
    }

    for model_name, m in metrics.items():
        if isinstance(m, dict) and "n_samples" in m:
            print(f"  {model_name.upper()}: MAE={m['mae']}, RMSE={m['rmse']}, R2={m['r2']}, MAPE={m['mape']}%")

    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved to {METRICS_PATH}")

    out_df = pd.DataFrame({
        "district": (df["district"].values[:min_len] if "district" in df.columns
                     else [""] * min_len),
        "week_start": (df["week_start"].values[:min_len]
                       if "week_start" in df.columns
                       else [""] * min_len),
        "true_cases": true_cases,
        "xgb_pred": xgb_preds,
        "lstm_pred": lstm_preds,
        "ensemble_pred": ensemble_preds,
    })
    out_df.to_csv(OUTPUT_PATH, index=False)
    print(f"Predictions saved to {OUTPUT_PATH}")

    return metrics


if __name__ == "__main__":
    run_evaluation()
