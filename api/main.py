import os
import sys
import uuid
import time
import math
import json
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
    HeatmapResponse,
    HeatmapDistrict,
    StatePredictionData,
    StatePredictionsResponse,
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

    curated: dict[str, tuple[float, float]] = {
        "Mumbai": (19.0760, 72.8777),
        "Greater Bombay": (19.0760, 72.8777),
        "Delhi": (28.7041, 77.1025),
        "Bangalore": (12.9716, 77.5946),
        "Bangalore Urban": (12.9716, 77.5946),
        "Bangalore Rural": (13.0500, 77.5500),
        "Chennai": (13.0827, 80.2707),
        "Kolkata": (22.5726, 88.3639),
        "Hyderabad": (17.3850, 78.4867),
        "Ahmedabad": (23.0225, 72.5714),
        "Ahmadabad": (23.0225, 72.5714),
        "Pune": (18.5204, 73.8567),
        "Jaipur": (26.9124, 75.7873),
        "Lucknow": (26.8467, 80.9462),
        "Surat": (21.1702, 72.8311),
        "Kanpur": (26.4499, 80.3319),
        "Nagpur": (21.1458, 79.0882),
        "Indore": (22.7196, 75.8577),
        "Thane": (19.2183, 72.9781),
        "Bhopal": (23.2599, 77.4126),
        "Visakhapatnam": (17.6868, 83.2185),
        "Pimpri-Chinchwad": (18.6298, 73.7997),
        "Patna": (25.5941, 85.1376),
        "Vadodara": (22.3072, 73.1812),
        "Ghaziabad": (28.6692, 77.4538),
        "Ludhiana": (30.9010, 75.8573),
        "Agra": (27.1767, 78.0081),
        "Nashik": (19.9975, 73.7898),
        "Faridabad": (28.4089, 77.3178),
        "Meerut": (28.9845, 77.7064),
        "Rajkot": (22.3039, 70.8022),
        "Kalyan-Dombivli": (19.2352, 73.1293),
        "Vasai-Virar": (19.3921, 72.8265),
        "Varanasi": (25.3176, 82.9739),
        "Srinagar": (34.0837, 74.7973),
        "Aurangabad": (19.8762, 75.3433),
        "Dhanbad": (23.7957, 86.4304),
        "Amritsar": (31.6340, 74.8723),
        "Navi Mumbai": (19.0330, 73.0297),
        "Allahabad": (25.4358, 81.8463),
        "Ranchi": (23.3441, 85.3096),
        "Howrah": (22.5958, 88.2636),
        "Jabalpur": (23.1815, 79.9864),
        "Gwalior": (26.2183, 78.1828),
        "Vijayawada": (16.5062, 80.6480),
        "Jodhpur": (26.2389, 73.0243),
        "Madurai": (9.9252, 78.1198),
        "Raipur": (21.2514, 81.6296),
        "Kota": (25.2138, 75.8648),
        "Guwahati": (26.1445, 91.7362),
        "Chandigarh": (30.7333, 76.7794),
        "Thiruvananthapuram": (8.5241, 76.9366),
        "Coimbatore": (11.0168, 76.9558),
        "Kochi": (9.9312, 76.2673),
        "Mangalore": (12.9141, 74.8560),
        "Mysore": (12.2958, 76.6394),
        "Bhubaneswar": (20.2961, 85.8245),
        "Salem": (11.6643, 78.1460),
        "Tiruchirappalli": (10.7905, 78.7047),
        "Dehradun": (30.3165, 78.0322),
        "Shimla": (31.1048, 77.1734),
        "Gangtok": (27.3389, 88.6065),
        "Itanagar": (27.0844, 93.6053),
        "Dispur": (26.1433, 91.7896),
        "Panaji": (15.4909, 73.8278),
        "Kohima": (25.6751, 94.1086),
        "Shillong": (25.5788, 91.8933),
        "Aizawl": (23.7307, 92.7173),
        "Agartala": (23.8315, 91.2868),
        "Imphal": (24.8170, 93.9368),
        "Port Blair": (11.6234, 92.7265),
        "Andaman Islands": (11.6234, 92.7265),
        "Silvassa": (20.2740, 73.0021),
        "Daman": (20.4145, 72.8326),
        "Diu": (20.7144, 70.9882),
        "Kavaratti": (10.5634, 72.6369),
        "Puducherry": (11.9416, 79.8083),
        "Leh": (34.1526, 77.5770),
        "Kargil": (34.5539, 76.1335),
    }

    # Start with curated overrides
    _coords_cache.update(curated)

    # Fill remaining districts from features_matrix.csv
    root = get_project_root()
    data_path = os.path.join(root, "data", "processed", "features_matrix.csv")
    df = pd.read_csv(data_path, usecols=["district", "lat", "lon"]).dropna()
    for _, row in df.iterrows():
        district = str(row["district"])
        if district not in _coords_cache:
            _coords_cache[district] = (float(row["lat"]), float(row["lon"]))

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
    coords = _cached_coords()

    if district not in coords:
        district = "Adilabad"
    lat0, lon0 = coords[district]

    nearest = sorted(
        [(d, lat, lon) for d, (lat, lon) in coords.items() if d != district],
        key=lambda x: _haversine(lat0, lon0, x[1], x[2]),
    )[:6]

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

    RADIUS_KM = 4.0

    zone_labels = [
        "North Zone", "South Zone", "East Zone", "West Zone",
        "Central Hospital Area", "Industrial Zone",
    ]
    zone_types = ["cases", "cases", "breeding", "breeding", "hospital", "cases"]

    hotspots = []
    for idx, (name, lat, lon) in enumerate(nearest):
        row = district_stats[district_stats["district"] == name]
        if row.empty:
            continue
        r = row.iloc[0]
        cases = max(1, int(r["avg_pred"]))
        max_cases = max(1, int(r["max_pred"]))
        bearing = _bearing(lat0, lon0, lat, lon)
        hlats, hlons = _destination(lat0, lon0, bearing, RADIUS_KM)
        zi = idx % len(zone_labels)
        hotspots.append(
            HotspotData(
                id=idx,
                name=f"{district} - {zone_labels[zi]}",
                district_ref=name,
                lat=hlats,
                lon=hlons,
                offset_lat=hlats - lat0,
                offset_lon=hlons - lon0,
                type=zone_types[zi],
                avg_cases=cases,
                max_cases=max_cases,
                std_cases=float(r["std_pred"]),
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


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(math.radians(lat2))
    y = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon)
    return math.degrees(math.atan2(x, y))


def _destination(lat: float, lon: float, bearing_deg: float, dist_km: float) -> tuple[float, float]:
    R = 6371.0
    brng = math.radians(bearing_deg)
    d = dist_km / R
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


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


@app.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap():
    df = _ensemble_results_df()

    latest_week = df["week_start"].max()
    recent_df = df[df["week_start"] >= (latest_week - pd.Timedelta(days=14))]

    overview = (
        recent_df.groupby("district")
        .agg({"ensemble_pred": "mean", "true_cases": "mean"})
        .reset_index()
    )
    overview.columns = ["district", "avg_pred", "avg_true"]
    overview["risk_level"] = overview["avg_pred"].apply(classify_risk_level)

    coords = _cached_coords()
    districts_data = []
    for _, row in overview.iterrows():
        d = row["district"]
        latlon = coords.get(d)
        if latlon is None:
            continue
        lat, lon = latlon
        districts_data.append(
            HeatmapDistrict(
                district=d,
                lat=lat,
                lon=lon,
                risk_level=row["risk_level"],
                intensity=min(1.0, float(row["avg_pred"]) / 50.0),
                avg_cases=float(row["avg_pred"]),
            )
        )

    return HeatmapResponse(
        districts=districts_data,
        total_districts=len(districts_data),
        latest_week=str(latest_week.date()),
    )


_STATE_BOUNDARIES_CACHE: dict | None = None


def _cached_state_boundaries() -> dict:
    global _STATE_BOUNDARIES_CACHE
    if _STATE_BOUNDARIES_CACHE is not None:
        return _STATE_BOUNDARIES_CACHE
    path = os.path.join(get_project_root(), "data", "processed", "india_states.geojson")
    if os.path.exists(path):
        with open(path) as f:
            _STATE_BOUNDARIES_CACHE = json.load(f)
    else:
        _STATE_BOUNDARIES_CACHE = {"type": "FeatureCollection", "features": []}
    return _STATE_BOUNDARIES_CACHE


@app.get("/state_boundaries")
def get_state_boundaries():
    return _cached_state_boundaries()


@app.get("/state_predictions", response_model=StatePredictionsResponse)
def get_state_predictions():
    df = _ensemble_results_df()
    states_data = _cached_states()

    latest_week = df["week_start"].max()
    recent_df = df[df["week_start"] >= (latest_week - pd.Timedelta(days=14))]

    district_avg = (
        recent_df.groupby("district")["ensemble_pred"]
        .mean()
        .reset_index()
    )

    state_results = []
    for s in states_data:
        state_name = s["state"]
        districts_in_state = s["districts"]
        state_districts = district_avg[district_avg["district"].isin(districts_in_state)]
        if state_districts.empty:
            continue
        total = float(state_districts["ensemble_pred"].sum())
        avg = float(state_districts["ensemble_pred"].mean())
        mx = float(state_districts["ensemble_pred"].max())
        cnt = len(state_districts)
        risk = classify_risk_level(avg)
        intensity = min(1.0, avg / 50.0)
        state_results.append(
            StatePredictionData(
                state=state_name,
                total_predicted_cases=round(total, 1),
                avg_predicted_cases=round(avg, 1),
                max_predicted_cases=round(mx, 1),
                district_count=cnt,
                risk_level=risk,
                intensity=round(intensity, 3),
            )
        )

    state_results.sort(key=lambda x: x.total_predicted_cases, reverse=True)
    return StatePredictionsResponse(
        states=state_results,
        latest_week=str(latest_week.date()),
    )
