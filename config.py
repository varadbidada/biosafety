from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    api_reload: bool = True

    # CORS
    cors_origins: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]

    # Model Paths (relative to project root)
    models_dir: str = "models"
    data_dir: str = "data/processed"

    # Feature Columns (must match training)
    feature_cols_path: str = "models/feature_cols.json"

    # External APIs
    open_meteo_base_url: str = "https://archive-api.open-meteo.com/v1/archive"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org/search"

    # Prediction Config
    low_risk_threshold: float = 10.0
    medium_risk_threshold: float = 50.0
    ensemble_weight_xgb: float = 0.5
    ensemble_weight_lstm: float = 0.5

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_project_root() -> Path:
    return Path(__file__).parent


def get_models_dir() -> Path:
    return get_project_root() / get_settings().models_dir


def get_data_dir() -> Path:
    return get_project_root() / get_settings().data_dir


def get_feature_cols_path() -> Path:
    return get_project_root() / get_settings().feature_cols_path


def get_model_path(model_name: str) -> Path:
    return get_models_dir() / model_name


# Model file names (constants)
XGB_REG_MODEL = "xgb_reg.json"
XGB_CLF_MODEL = "xgb_clf.json"
LSTM_MODEL = "lstm_model_full.pt"
LSTM_SCALER = "lstm_scaler.pkl"
FEATURE_COLS = "feature_cols.json"

# Data file names
FEATURES_MATRIX = "features_matrix.csv"
ENSEMBLE_RESULTS = "ensemble_results.csv"
DENGUE_WEEKLY_CLEAN = "dengue_weekly_clean.csv"
SYNTHETIC_DENGUE = "synthetic_dengue_weekly.csv"

# Feature columns (from training)
FEATURE_COLUMNS = [
    "month",
    "monsoon",
    "rainfall",
    "temperature",
    "ndvi",
    "cases",
    "rain_lag_1",
    "ndvi_lag_1",
    "cases_lag_1",
    "rain_lag_2",
    "ndvi_lag_2",
    "cases_lag_2",
    "rain_lag_3",
    "ndvi_lag_3",
    "cases_lag_3",
    "rain_3wk_mean",
    "ndvi_3wk_mean",
]

EXPECTED_FEATURE_COUNT = len(FEATURE_COLUMNS)