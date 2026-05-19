# src/models/ensemble.py

import pandas as pd
import numpy as np
import torch
import joblib
import os
from sklearn.metrics import mean_squared_error
from models.train_lstm import LSTMModel
import xgboost as xgb

SEQ_LEN = 10

def load_models(feature_cols):
    # Load XGB
    xgb_model = joblib.load("models/xgb_reg.model")

    # Load scaler
    scaler = joblib.load("models/lstm_scaler.pkl")

    # Load LSTM
    lstm_model = LSTMModel(input_dim=len(feature_cols))
    lstm_model.load_state_dict(torch.load("models/lstm_model.pt"))
    lstm_model.eval()

    return xgb_model, lstm_model, scaler


def load_feature_data():
    df = pd.read_csv("data/processed/features_matrix.csv")
    df["week_start"] = pd.to_datetime(df["week_start"])

    feature_cols = [
        c for c in df.columns 
        if c not in ["district", "week_start", "week_end", "target_cases_next", "risk_next"]
    ]

    return df, feature_cols


def lstm_predict_sequence(df, feature_cols, lstm_model, scaler):
    preds = []

    for district, g in df.groupby("district"):
        g = g.sort_values("week_start").reset_index(drop=True)
        X = g[feature_cols].values
        X_scaled = scaler.transform(X)

        district_preds = []

        for i in range(len(g) - SEQ_LEN - 1):
            seq = X_scaled[i:i+SEQ_LEN]
            seq_tensor = torch.tensor(seq, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                pred = lstm_model(seq_tensor).item()
            district_preds.append(pred)

        # pad initial values with NaN to align with XGB outputs
        preds.extend([np.nan]*SEQ_LEN + district_preds)

    return np.array(preds)


def main():
    print("Loading feature data...")
    df, feature_cols = load_feature_data()

    print("Loading models...")
    xgb_model, lstm_model, scaler = load_models(feature_cols)

    print("Running XGBoost predictions...")
    X = df[feature_cols].fillna(0)
    xgb_preds = xgb_model.predict(X)

    print("Running LSTM predictions...")
    lstm_preds = lstm_predict_sequence(df, feature_cols, lstm_model, scaler)

    # Align lengths
    min_len = min(len(xgb_preds), len(lstm_preds))
    xgb_preds = xgb_preds[:min_len]
    lstm_preds = lstm_preds[:min_len]
    true_cases = df["target_cases_next"].values[:min_len]

    # Ensemble = weighted average
    ensemble_preds = 0.6 * xgb_preds + 0.4 * lstm_preds

    print("\n--- Ensemble Regression Report ---")
    mask = ~np.isnan(ensemble_preds)
    rmse = np.sqrt(mean_squared_error(true_cases[mask], ensemble_preds[mask]))
    print("Ensemble RMSE:", rmse)

    # Save ensemble predictions for evaluation
    out_df = pd.DataFrame({
    "district": df["district"][:min_len].values,
    "week_start": df["week_start"][:min_len].values,
    "true_cases": true_cases,
    "xgb_pred": xgb_preds,
    "lstm_pred": lstm_preds,
    "ensemble_pred": ensemble_preds
})

    out_df.to_csv("data/processed/ensemble_results.csv", index=False)
    print("Saved ensemble results to data/processed/ensemble_results.csv")


if __name__ == "__main__":
    main()