import os
import json
import joblib
import pandas as pd
import xgboost as xgb

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, "data/processed/features_matrix.csv")
MODELS_PATH = os.path.join(ROOT, "models")
os.makedirs(MODELS_PATH, exist_ok=True)

print("Loading dataset:", DATA_PATH)
df = pd.read_csv(DATA_PATH)
df = df.dropna()

feature_cols = [
    "month","monsoon","rainfall","temperature","ndvi","cases",
    "rain_lag_1","ndvi_lag_1","cases_lag_1",
    "rain_lag_2","ndvi_lag_2","cases_lag_2",
    "rain_lag_3","ndvi_lag_3","cases_lag_3",
    "rain_3wk_mean","ndvi_3wk_mean"
]

X = df[feature_cols].values
y_reg = df["target_cases_next"].values
y_clf = df["risk_next"].values

print("Training XGBoost REGRESSOR (High Accuracy)...")
xgb_reg = xgb.XGBRegressor(
    n_estimators=1200,
    learning_rate=0.02,
    max_depth=8,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.2,
    objective="reg:squarederror",
    tree_method="hist"
)
xgb_reg.fit(X, y_reg)

print("Training XGBoost CLASSIFIER (High Accuracy)...")
xgb_clf = xgb.XGBClassifier(
    n_estimators=1200,
    learning_rate=0.03,
    max_depth=8,
    subsample=0.9,
    colsample_bytree=0.9,
    reg_lambda=1.0,
    objective="binary:logistic",
    tree_method="hist"
)
xgb_clf.fit(X, y_clf)

print("Saving models...")
xgb_reg.save_model(os.path.join(MODELS_PATH, "xgb_reg.json"))
xgb_clf.save_model(os.path.join(MODELS_PATH, "xgb_clf.json"))

json.dump(feature_cols, open(os.path.join(MODELS_PATH, "feature_cols.json"), "w"))

print("✓ XGBoost models saved!")