from pydantic import BaseModel, Field, field_validator
from typing import Optional
from config import EXPECTED_FEATURE_COUNT


class PredictionInput(BaseModel):
    features: list[float] = Field(
        ...,
        min_length=EXPECTED_FEATURE_COUNT,
        max_length=EXPECTED_FEATURE_COUNT,
        description=f"Feature vector of exactly {EXPECTED_FEATURE_COUNT} values in training order",
    )

    @field_validator("features")
    @classmethod
    def validate_features(cls, v: list[float]) -> list[float]:
        if len(v) != EXPECTED_FEATURE_COUNT:
            raise ValueError(
                f"Expected exactly {EXPECTED_FEATURE_COUNT} features, got {len(v)}"
            )
        return v


class ClimateData(BaseModel):
    rainfall: float
    temperature: float
    ndvi: float
    cases: float
    monsoon: int


class PredictionResponse(BaseModel):
    predicted_cases_next_week: float
    risk_level: str
    xgb_reg: float
    xgb_clf: int
    lstm: float
    ensemble: float
    climate: ClimateData
    district: Optional[str] = None
    week_start: Optional[str] = None
    history_week_start: Optional[str] = None
    forecast_week_1: Optional[str] = None
    forecast_week_2: Optional[str] = None
    forecast_week_3: Optional[str] = None
    predicted_cases_1w: Optional[float] = None
    predicted_cases_2w: Optional[float] = None
    predicted_cases_3w: Optional[float] = None


class StateData(BaseModel):
    state: str
    districts: list[str]


class StateListResponse(BaseModel):
    states: list[StateData]


class DistrictListResponse(BaseModel):
    districts: list[str]


class ModelMetrics(BaseModel):
    n_samples: int
    mae: float
    rmse: float
    mape: float


class ModelAccuracyResponse(BaseModel):
    district: str
    horizon: str
    metrics: dict[str, ModelMetrics]


class HotspotData(BaseModel):
    id: int
    name: str
    district_ref: str
    lat: float
    lon: float
    offset_lat: float
    offset_lon: float
    type: str
    avg_cases: int
    max_cases: int
    std_cases: float
    intensity: float


class HotspotsResponse(BaseModel):
    district: str
    center_cases: float
    center_max: float
    hotspots: list[HotspotData]
    total_hotspots: int


class DistrictOverview(BaseModel):
    district: str
    avg_cases: float
    max_cases: float
    min_cases: float
    risk_level: str
    intensity: float


class MapOverviewResponse(BaseModel):
    districts: list[DistrictOverview]
    total_districts: int
    latest_week: str


class HealthResponse(BaseModel):
    status: str
    version: str
    models_loaded: bool


class CoordinateResponse(BaseModel):
    district: str
    lat: float
    lon: float


class StatePredictionData(BaseModel):
    state: str
    total_predicted_cases: float
    avg_predicted_cases: float
    max_predicted_cases: float
    district_count: int
    risk_level: str
    intensity: float


class StatePredictionsResponse(BaseModel):
    states: list[StatePredictionData]
    latest_week: str


class HeatmapDistrict(BaseModel):
    district: str
    lat: float
    lon: float
    risk_level: str
    intensity: float
    avg_cases: float


class HeatmapResponse(BaseModel):
    districts: list[HeatmapDistrict]
    total_districts: int
    latest_week: str