import os
import sys
import uuid
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import structlog
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from config import get_settings, get_project_root
from api.schemas import (
    PredictionResponse,
    DistrictListResponse,
    StateData,
    StateListResponse,
    ModelAccuracyResponse,
    ModelMetrics,
    HotspotsResponse,
    HotspotData,
    MapOverviewResponse,
    DistrictOverview,
    HealthResponse,
    CoordinateResponse,
    PredictionInput,
)
from api.services.prediction import get_model_service


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._max = max_requests
        self._window = window_seconds

    def check(self, key: str = "default") -> bool:
        now = time.monotonic()
        timestamps = self._buckets[key]
        self._buckets[key] = [t for t in timestamps if now - t < self._window]
        if len(self._buckets[key]) >= self._max:
            return False
        self._buckets[key].append(now)
        return True


_districts_cache: dict[str, list[str] | None] = {"districts": None}
_coords_cache: dict[str, tuple[float, float]] = {}

logger = structlog.get_logger()


def classify_risk_level(pred: float) -> str:
    s = get_settings()
    if pred < s.low_risk_threshold:
        return "low"
    if pred < s.medium_risk_threshold:
        return "medium"
    return "high"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if settings.log_format == "dev"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    logger.info("Initializing model service...")
    get_model_service()
    logger.info("Model service ready")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="DengueCast India API",
    description="Dengue outbreak prediction for Indian districts using XGBoost + LSTM ensemble",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rate_limiter = RateLimiter(max_requests=60, window_seconds=60)

# ─── Middleware ───────────────────────────────────────────────────────


@app.middleware("http")
async def add_request_id_and_catch_errors(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:8])
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request error")
        response = JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
    response.headers["X-Request-ID"] = request_id
    return response


# ─── Exception Handlers ──────────────────────────────────────────────


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# ─── Helper ──────────────────────────────────────────────────────────


def _cached_districts() -> list[str]:
    if _districts_cache["districts"] is not None:
        return _districts_cache["districts"]
    root = get_project_root()
    data_path = os.path.join(root, "data", "processed", "features_matrix.csv")
    df = pd.read_csv(data_path, usecols=["district"]).dropna()
    districts = sorted(df["district"].unique().tolist())
    _districts_cache["districts"] = districts
    return districts


def _cached_states() -> list[dict]:
    root = get_project_root()
    data_path = os.path.join(root, "data", "processed", "features_matrix.csv")
    df = pd.read_csv(data_path, usecols=["state", "district"]).dropna()
    pairs = df.drop_duplicates()
    state_map: dict[str, set[str]] = {}
    for _, row in pairs.iterrows():
        state_map.setdefault(str(row["state"]), set()).add(str(row["district"]))
    result = []
    for state in sorted(state_map):
        result.append({
            "state": state,
            "districts": sorted(state_map[state]),
        })
    return result


def _cached_coords() -> dict[str, tuple[float, float]]:
    if _coords_cache:
        return _coords_cache
    root = get_project_root()
    data_path = os.path.join(root, "data", "processed", "features_matrix.csv")
    df = pd.read_csv(data_path, usecols=["district", "lat", "lon"]).dropna()
    for _, row in df.iterrows():
        _coords_cache[str(row["district"])] = (float(row["lat"]), float(row["lon"]))
    return _coords_cache


def _ensemble_results_df() -> pd.DataFrame:
    root = get_project_root()
    path = os.path.join(root, "data", "processed", "ensemble_results.csv")
    df = pd.read_csv(path)
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


# ─── Endpoints ───────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
def health_check():
    svc = get_model_service()
    return HealthResponse(
        status="ok" if svc.is_healthy() else "degraded",
        version="0.1.0",
        models_loaded=svc.is_healthy(),
    )


@app.get("/coordinates/{district}", response_model=CoordinateResponse)
def get_coordinates(district: str):
    cache = _cached_coords()
    if district in cache:
        lat, lon = cache[district]
        return CoordinateResponse(district=district, lat=lat, lon=lon)
    logger.warning("coordinates_not_found", district=district)
    return CoordinateResponse(district=district, lat=20.5937, lon=78.9629)


@app.post("/predict", response_model=PredictionResponse)
def predict(data: PredictionInput, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    svc = get_model_service()
    resp = svc.predict_from_features(data.features)
    logger.info("predict_request", client_ip=client_ip)
    return resp


@app.get("/districts", response_model=DistrictListResponse)
def list_districts():
    return DistrictListResponse(districts=_cached_districts())


@app.get("/states", response_model=StateListResponse)
def list_states():
    return StateListResponse(states=_cached_states())


@app.get("/predict_latest")
def predict_latest(district: str = Query("Adilabad")):
    svc = get_model_service()

    result = svc.predict_district(district)
    if result is None:
        result = svc.predict_district("Adilabad")
        if result is None:
            raise HTTPException(status_code=404, detail="District not found")

    features, reg_pred, lstm_pred, ensemble_pred = result
    settings = get_settings()
    predicted_cases_1w = max(0.0, ensemble_pred)
    risk_level = classify_risk_level(predicted_cases_1w)

    df = svc._get_feature_matrix()
    df_d = df[df["district"] == district].copy()
    if df_d.empty:
        df_d = df.copy()
    latest_row = df_d.sort_values("week_start").iloc[-1]
    history_week_start = latest_row["week_start"]

    predicted_cases_2w = max(0.0, predicted_cases_1w * 1.05)
    predicted_cases_3w = max(0.0, predicted_cases_1w * 1.10)

    week_1 = history_week_start + pd.Timedelta(days=7)
    week_2 = history_week_start + pd.Timedelta(days=14)
    week_3 = history_week_start + pd.Timedelta(days=21)

    return {
        "district": str(latest_row["district"]),
        "week_start": str(history_week_start.date()),
        "history_week_start": str(history_week_start.date()),
        "forecast_week_1": str(week_1.date()),
        "forecast_week_2": str(week_2.date()),
        "forecast_week_3": str(week_3.date()),
        "predicted_cases_next_week": predicted_cases_1w,
        "predicted_cases_1w": predicted_cases_1w,
        "predicted_cases_2w": predicted_cases_2w,
        "predicted_cases_3w": predicted_cases_3w,
        "risk_level": risk_level,
        "xgb_reg": reg_pred,
        "xgb_clf": int(svc.xgb_clf.predict(np.array(features, dtype=float).reshape(1, -1))[0]),
        "lstm": lstm_pred,
        "ensemble": ensemble_pred,
        "climate": {
            "rainfall": float(latest_row.get("rainfall", 0.0)),
            "temperature": float(latest_row.get("temperature", 0.0)),
            "ndvi": float(latest_row.get("ndvi", 0.0)),
            "cases": float(latest_row.get("cases", 0.0)),
            "monsoon": int(latest_row.get("monsoon", 0)),
        },
    }


@app.get("/model_accuracy", response_model=ModelAccuracyResponse)
def model_accuracy(district: str | None = None):
    df = _ensemble_results_df()

    if district:
        df = df[df["district"] == district]
        if df.empty:
            return ModelAccuracyResponse(
                district=district, horizon="1-week ahead", metrics={}
            )

    def compute_metrics(col: str) -> dict | None:
        if col not in df.columns:
            return None
        sub = df[["true_cases", col]].dropna()
        if sub.empty:
            return None
        y_true = sub["true_cases"].to_numpy(dtype=float)
        y_pred = sub[col].to_numpy(dtype=float)
        err = y_pred - y_true
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err**2)))
        denom = np.maximum(1.0, np.abs(y_true))
        mape = float(np.mean(np.abs(err) / denom) * 100.0)
        return {"n_samples": int(len(sub)), "mae": mae, "rmse": rmse, "mape": mape}

    metrics = {}
    for col, key in [("xgb_pred", "xgb"), ("lstm_pred", "lstm"), ("ensemble_pred", "ensemble")]:
        m = compute_metrics(col)
        if m is not None:
            metrics[key] = ModelMetrics(**m)

    return ModelAccuracyResponse(
        district=district or "ALL", horizon="1-week ahead", metrics=metrics
    )


@app.get("/hotspots", response_model=HotspotsResponse)
def get_hotspots(district: str = Query("Adilabad")):
    df = _ensemble_results_df()

    latest_week = df["week_start"].max()
    recent_df = df[df["week_start"] >= (latest_week - pd.Timedelta(days=28))]

    district_stats = (
        recent_df.groupby("district")
        .agg({"ensemble_pred": ["mean", "std", "max"], "true_cases": "mean"})
        .reset_index()
    )
    district_stats.columns = ["district", "avg_pred", "std_pred", "max_pred", "avg_true"]

    selected_data = district_stats[district_stats["district"] == district]
    if selected_data.empty:
        selected_data = district_stats.iloc[0:1]
        district = selected_data["district"].values[0]

    district_stats["similarity"] = abs(
        district_stats["avg_pred"] - selected_data["avg_pred"].values[0]
    )
    neighbors = district_stats[
        district_stats["district"] != district
    ].nsmallest(6, "similarity")

    offsets = [
        {"name": "North Zone", "dLat": 0.015, "dLon": 0.008, "type": "cases"},
        {"name": "South Zone", "dLat": -0.012, "dLon": -0.010, "type": "cases"},
        {"name": "East Zone", "dLat": 0.008, "dLon": 0.018, "type": "breeding"},
        {"name": "West Zone", "dLat": -0.006, "dLon": -0.015, "type": "breeding"},
        {"name": "Central Hospital Area", "dLat": 0.003, "dLon": 0.005, "type": "hospital"},
        {"name": "Industrial Zone", "dLat": 0.020, "dLon": -0.012, "type": "cases"},
    ]

    hotspots = []
    for idx, (_, neighbor) in enumerate(neighbors.iterrows()):
        if idx >= len(offsets):
            break
        offset = offsets[idx]
        cases = max(1, int(neighbor["avg_pred"]))
        max_cases = max(1, int(neighbor["max_pred"]))
        hotspots.append(
            HotspotData(
                id=idx,
                name=f"{district} - {offset['name']}",
                district_ref=neighbor["district"],
                offset_lat=offset["dLat"],
                offset_lon=offset["dLon"],
                type=offset["type"],
                avg_cases=cases,
                max_cases=max_cases,
                std_cases=float(neighbor["std_pred"]),
                intensity=min(1.0, cases / 50.0),
            )
        )

    return HotspotsResponse(
        district=district,
        center_cases=float(selected_data["avg_pred"].values[0]),
        center_max=float(selected_data["max_pred"].values[0]),
        hotspots=hotspots,
        total_hotspots=len(hotspots),
    )


@app.get("/map_overview", response_model=MapOverviewResponse)
def get_map_overview():
    df = _ensemble_results_df()

    latest_week = df["week_start"].max()
    recent_df = df[df["week_start"] >= (latest_week - pd.Timedelta(days=14))]

    district_overview = (
        recent_df.groupby("district")
        .agg({"ensemble_pred": ["mean", "max", "min"], "true_cases": "mean"})
        .reset_index()
    )
    district_overview.columns = ["district", "avg_pred", "max_pred", "min_pred", "avg_true"]
    district_overview["risk_level"] = district_overview["avg_pred"].apply(classify_risk_level)

    districts_data = []
    for _, row in district_overview.iterrows():
        districts_data.append(
            DistrictOverview(
                district=row["district"],
                avg_cases=float(row["avg_pred"]),
                max_cases=float(row["max_pred"]),
                min_cases=float(row["min_pred"]),
                risk_level=row["risk_level"],
                intensity=min(1.0, float(row["avg_pred"]) / 50.0),
            )
        )

    return MapOverviewResponse(
        districts=districts_data,
        total_districts=len(districts_data),
        latest_week=str(latest_week.date()),
    )
