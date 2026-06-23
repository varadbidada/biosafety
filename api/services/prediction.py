import os
import sys
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import xgboost as xgb
import joblib

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from config import (
    get_settings,
    get_model_path,
    get_feature_cols_path,
    EXPECTED_FEATURE_COUNT,
    XGB_REG_MODEL,
    XGB_CLF_MODEL,
    LSTM_MODEL,
    LSTM_SCALER,
)
from api.schemas import PredictionResponse, ClimateData

SEQ_LEN = 10


class LSTMModel(nn.Module):
    def __init__(self, input_size=17, hidden_size=96, num_layers=2, output_size=1, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


class ModelService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._load_models()
            ModelService._initialized = True

    def _load_models(self):
        settings = get_settings()

        feature_cols_path = get_feature_cols_path()
        with open(feature_cols_path) as f:
            self.feature_cols = json.load(f)

        self.INPUT_SIZE = len(self.feature_cols)

        self.xgb_reg = xgb.XGBRegressor()
        self.xgb_reg.load_model(str(get_model_path(XGB_REG_MODEL)))

        self.xgb_clf = xgb.XGBClassifier()
        self.xgb_clf.load_model(str(get_model_path(XGB_CLF_MODEL)))

        self.lstm_scaler = joblib.load(str(get_model_path(LSTM_SCALER)))

        self.lstm_model = LSTMModel(
            input_size=self.INPUT_SIZE,
            hidden_size=96,
            num_layers=2,
            output_size=1,
        )
        state_dict = torch.load(
            str(get_model_path(LSTM_MODEL)), map_location="cpu"
        )
        self.lstm_model.load_state_dict(state_dict)
        self.lstm_model.eval()

    def classify_risk(self, predicted_cases: float) -> str:
        settings = get_settings()
        if predicted_cases < settings.low_risk_threshold:
            return "low"
        if predicted_cases < settings.medium_risk_threshold:
            return "medium"
        return "high"

    def _predict_lstm(self, sequence: np.ndarray) -> float:
        """Predict using LSTM with a (seq_len, n_features) sequence."""
        seq_scaled = self.lstm_scaler.transform(sequence)
        seq_tensor = torch.tensor(seq_scaled, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            pred = float(self.lstm_model(seq_tensor).item())
        return pred

    def _build_sequence(self, features: list[float]) -> np.ndarray:
        """Build a sequence for LSTM from a single feature vector by replication."""
        return np.array([features] * SEQ_LEN, dtype=float)

    def predict_from_features(self, features: list[float]) -> PredictionResponse:
        x = np.array(features, dtype=float).reshape(1, -1)

        reg_pred = float(self.xgb_reg.predict(x)[0])
        clf_pred = int(self.xgb_clf.predict(x)[0])

        # Build sequence for LSTM (replicate single vector SEQ_LEN times)
        seq = self._build_sequence(features)
        lstm_pred = self._predict_lstm(seq)

        settings = get_settings()
        ensemble_pred = float(
            settings.ensemble_weight_xgb * reg_pred
            + settings.ensemble_weight_lstm * lstm_pred
        )

        predicted_cases_next_week = max(0.0, ensemble_pred)
        risk_level = self.classify_risk(predicted_cases_next_week)

        return PredictionResponse(
            predicted_cases_next_week=predicted_cases_next_week,
            risk_level=risk_level,
            xgb_reg=reg_pred,
            xgb_clf=clf_pred,
            lstm=lstm_pred,
            ensemble=ensemble_pred,
            climate=ClimateData(
                rainfall=features[self.feature_cols.index("rainfall")]
                if "rainfall" in self.feature_cols
                else 0.0,
                temperature=features[self.feature_cols.index("temperature")]
                if "temperature" in self.feature_cols
                else 0.0,
                ndvi=features[self.feature_cols.index("ndvi")]
                if "ndvi" in self.feature_cols
                else 0.0,
                cases=features[self.feature_cols.index("cases")]
                if "cases" in self.feature_cols
                else 0.0,
                monsoon=int(
                    features[self.feature_cols.index("monsoon")]
                    if "monsoon" in self.feature_cols
                    else 0
                ),
            ),
        )

    _feature_matrix_df: pd.DataFrame | None = None

    def _get_feature_matrix(self) -> pd.DataFrame:
        if ModelService._feature_matrix_df is not None:
            return ModelService._feature_matrix_df
        root = _project_root
        path = os.path.join(root, "data", "processed", "features_matrix.csv")
        df = pd.read_csv(path)
        df["week_start"] = pd.to_datetime(df["week_start"])
        ModelService._feature_matrix_df = df
        return df

    def predict_district(self, district: str) -> tuple[list[float], float, float, float] | None:
        """Get latest feature vector + historical sequence for a district.
        
        Returns (features, xgb_pred, lstm_pred, ensemble_pred) or None if district not found.
        """
        df = self._get_feature_matrix()

        df_d = df[df["district"] == district].copy()
        if df_d.empty:
            return None

        df_d = df_d.sort_values("week_start").reset_index(drop=True)

        # Get the last SEQ_LEN rows for LSTM sequence
        n_rows = len(df_d)
        if n_rows >= SEQ_LEN:
            seq_slice = df_d.iloc[n_rows - SEQ_LEN:]
        else:
            seq_slice = df_d.iloc[:]

        seq_features = seq_slice[self.feature_cols].values.astype(float)

        # Pad if not enough historical data
        if len(seq_features) < SEQ_LEN:
            pad = np.tile(seq_features[0], (SEQ_LEN - len(seq_features), 1))
            seq_features = np.vstack([pad, seq_features])

        latest_row = df_d.iloc[-1]
        features = [float(latest_row[col]) for col in self.feature_cols]

        # XGBoost prediction
        x = np.array(features, dtype=float).reshape(1, -1)
        reg_pred = float(self.xgb_reg.predict(x)[0])

        # LSTM prediction using historical sequence
        lstm_pred = self._predict_lstm(seq_features)

        # Ensemble
        settings = get_settings()
        ensemble_pred = float(
            settings.ensemble_weight_xgb * reg_pred
            + settings.ensemble_weight_lstm * lstm_pred
        )

        return features, reg_pred, lstm_pred, ensemble_pred

    def is_healthy(self) -> bool:
        try:
            dummy_features = [0.0] * EXPECTED_FEATURE_COUNT
            self.predict_from_features(dummy_features)
            return True
        except Exception:
            return False


_model_service: ModelService | None = None


def get_model_service() -> ModelService:
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service
