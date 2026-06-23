import os
import sys
import json
import numpy as np
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
    FEATURE_COLUMNS,
    EXPECTED_FEATURE_COUNT,
    XGB_REG_MODEL,
    XGB_CLF_MODEL,
    LSTM_MODEL,
    LSTM_SCALER,
)
from api.schemas import PredictionResponse, ClimateData


class LSTMModel(nn.Module):
    def __init__(self, input_size=17, hidden_size=96, num_layers=2, output_size=1):
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
        out = self.fc(out[:, -1, :])
        return out


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

    def predict_from_features(self, features: list[float]) -> PredictionResponse:
        x = np.array(features, dtype=float).reshape(1, -1)

        reg_pred = float(self.xgb_reg.predict(x)[0])
        clf_pred = int(self.xgb_clf.predict(x)[0])

        x_scaled = self.lstm_scaler.transform(x)
        x_lstm = torch.tensor(x_scaled, dtype=torch.float32).unsqueeze(0)
        lstm_pred = float(self.lstm_model(x_lstm).item())

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