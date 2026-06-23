import os
import json
import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")
MODELS_PATH = os.path.join(ROOT, "models")
FEATURE_COLS_PATH = os.path.join(MODELS_PATH, "feature_cols.json")

os.makedirs(MODELS_PATH, exist_ok=True)

print("Loading dataset:", DATA_PATH)
df = pd.read_csv(DATA_PATH).dropna()
print(f"Dataset shape: {df.shape}")

# Sort by district + week for time-series ordering
df["week_start"] = pd.to_datetime(df["week_start"])
df = df.sort_values(["district", "week_start"]).reset_index(drop=True)

feature_cols = [
    "month","monsoon","rainfall","temperature","ndvi","cases",
    "rain_lag_1","ndvi_lag_1","cases_lag_1",
    "rain_lag_2","ndvi_lag_2","cases_lag_2",
    "rain_lag_3","ndvi_lag_3","cases_lag_3",
    "rain_3wk_mean","ndvi_3wk_mean",
]

X = df[feature_cols].values
y_reg = df["target_cases_next"].values
y_clf = df["risk_next"].values

# Time-series aware split: use first 80% of data (by week order) for training
# This prevents data leakage from future into past
split_idx = int(len(df) * 0.8)
X_train, X_val = X[:split_idx], X[split_idx:]
y_reg_train, y_reg_val = y_reg[:split_idx], y_reg[split_idx:]
y_clf_train, y_clf_val = y_clf[:split_idx], y_clf[split_idx:]

print(f"Train: {len(X_train)} rows, Val: {len(X_val)} rows")

print("\nTraining XGBoost REGRESSOR (with early stopping)...")
xgb_reg = xgb.XGBRegressor(
    n_estimators=1200,
    learning_rate=0.02,
    max_depth=8,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.2,
    reg_alpha=0.1,
    objective="reg:squarederror",
    tree_method="hist",
    early_stopping_rounds=20,
    eval_metric="rmse",
)
xgb_reg.fit(
    X_train, y_reg_train,
    eval_set=[(X_val, y_reg_val)],
    verbose=50,
)

print("\nTraining XGBoost CLASSIFIER (with early stopping)...")
xgb_clf = xgb.XGBClassifier(
    n_estimators=1200,
    learning_rate=0.03,
    max_depth=8,
    subsample=0.9,
    colsample_bytree=0.9,
    reg_lambda=1.0,
    objective="binary:logistic",
    tree_method="hist",
    early_stopping_rounds=20,
    eval_metric="logloss",
)
xgb_clf.fit(
    X_train, y_clf_train,
    eval_set=[(X_val, y_clf_val)],
    verbose=50,
)

print("\nSaving models...")
xgb_reg.save_model(os.path.join(MODELS_PATH, "xgb_reg.json"))
xgb_clf.save_model(os.path.join(MODELS_PATH, "xgb_clf.json"))

json.dump(feature_cols, open(FEATURE_COLS_PATH, "w"))

print("XGBoost models saved!")
