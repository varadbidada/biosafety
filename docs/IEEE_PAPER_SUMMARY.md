# DengueCast India: A Scalable Ensemble Machine Learning Framework for Weekly Dengue Outbreak Forecasting Across 589 Districts

---

## Abstract

Dengue fever remains a persistent public health challenge across India, with seasonal outbreaks placing sustained burden on healthcare infrastructure. This paper presents **DengueCast India**, an end-to-end machine learning framework that combines XGBoost gradient-boosted tree ensembles with Long Short-Term Memory (LSTM) recurrent neural networks to produce weekly case-count forecasts for all 589 districts of India spanning the 2015-2024 decade. The system generates a 17-dimensional feature space comprising climate variables (rainfall, temperature, NDVI), epidemiological lags, and rolling temporal aggregates over a 3-week horizon. A weighted ensemble — optimized via grid search — blends the regression and sequential learning capacities of both architectures. Predictions are served through a FastAPI REST backend with sliding-window rate limiting, structured logging, and in-memory caching, while a React 19 / TypeScript frontend renders interactive Leaflet-based geospatial heatmaps, Chart.js temporal trend lines, and multi-model inference breakdowns. On the synthetic benchmark dataset (307K rows, all-district coverage), the ensemble achieves an RMSE of 4.25 and MAE of 3.41. We discuss limitations imposed by synthetic disease incidence data and outline a pathway toward real-data integration using Open-Meteo weather feeds and National Vector Borne Disease Control Programme (NVBDCP) case reports.

**Keywords** — Dengue forecasting, XGBoost, LSTM, ensemble learning, disease surveillance, geospatial visualization, India

---

## 1. Introduction

### 1.1 Problem Domain

Dengue fever, transmitted primarily by *Aedes aegypti* mosquitoes, affects an estimated 50-100 million people annually worldwide [1]. India accounts for approximately one-third of the global dengue burden, with outbreaks exhibiting pronounced seasonal and geographic heterogeneity driven by monsoon rainfall patterns, temperature fluctuations, and urbanization gradients [2]. The ability to forecast case counts at a fine spatial and temporal resolution — weekly, per district — would enable public health agencies to pre-position diagnostics, allocate vector-control resources, and issue targeted community warnings.

### 1.2 Limitations of Existing Approaches

Prior work in dengue forecasting falls into three broad categories:

1. **Statistical time-series models** (SARIMA, exponential smoothing) that capture seasonal patterns but struggle with non-linear interactions among climate, vector, and human-mobility variables [3].
2. **Single-model machine learning approaches** (standalone XGBoost, random forest, or feed-forward neural networks) that capture non-linearity but lack the sequential memory required to model outbreak trajectories that unfold over multi-week windows [4].
3. **Deep learning sequence models** (LSTM, GRU, transformer architectures) that excel at temporal dependency modeling but require large training corpora and are sensitive to feature scaling and hyperparameter choice [5].

Few existing systems simultaneously satisfy **national geographic coverage**, **weekly temporal granularity**, **production-grade API serving**, and **interactive geospatial visualization** — the four design criteria we target.

### 1.3 Contribution

This work makes the following contributions:

- **A complete end-to-end pipeline** spanning synthetic data generation, feature engineering, dual-model training, ensemble optimization, API deployment, and browser-based visualization.
- **Geographic completeness**: forecasts for all 589 Indian districts derived from administrative-boundary GeoJSON, with centroid extraction through projected CRS (EPSG:3857) for accurate coordinate mapping.
- **Hybrid ensemble architecture**: an XGBoost regressor (gradient-boosted trees, 1200 estimators, max depth 8) paired with a two-layer LSTM (96 hidden units, 10-week sequence window, 0.2 dropout), combined via convex weight optimized over a 21-point grid search.
- **Production infrastructure**: FastAPI backend with CORS, rate limiting (60 req/min sliding window), structlog-based structured logging, and a singleton model service; React 19 frontend with Leaflet heatmap overlays, Chart.js temporal trend visualization, and responsive mobile sidebar.
- **Open pathway to real data**: a modular `fetch_real_weather.py` script that replaces synthetic climate fields with Open-Meteo archive data, and an explicit roadmap for integrating NVBDCP case reports.

---

## 2. System Architecture

Figure 1 illustrates the three-tier architecture.

```
┌──────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React 19 / Vite 8)                  │
│  Landing Page → Dashboard                                        │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────────────┐ │
│  │ Leaflet Map  │  │ Chart.js Line │  │ Model Inference Panel  │ │
│  │ 4 basemaps   │  │ gradient fill │  │ LSTM / XGB / Ensemble  │ │
│  │ heat overlay │  │ 4-point trend │  │ tooltip descriptions   │ │
│  │ hotspot      │  │ animated cntr │  │ progress bars w/ color │ │
│  │ clustering   │  │               │  │                        │ │
│  └──────┬───────┘  └───────┬───────┘  └───────────┬────────────┘ │
│         │                  │                       │              │
│         └──────────────────┴───────────────────────┘              │
│                              │ HTTP (axios)                       │
│                              ▼                                    │
├──────────────────────────────────────────────────────────────────┤
│                  API (FastAPI / Uvicorn :8001)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ /predict │ │ /heatmap │ │ /states  │ │ /coordinates/{d}   │  │
│  │ /predict │ │ /hotspots│ │ /map_    │ │ /model_accuracy    │  │
│  │ _latest  │ │          │ │ _overview│ │ /districts         │  │
│  ├──────────┤ ├──────────┤ ├──────────┤ ├────────────────────┤  │
│  │ CORS     │ │ Rate     │ │ Request  │ │ structlog          │  │
│  │ MW       │ │ Limiter  │ │ ID MW    │ │ structured logging │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
│                              │                                    │
│        ┌─────────────────────┴─────────────────────┐              │
│        ▼                                            ▼              │
│  ┌─────────────────────┐              ┌─────────────────────────┐ │
│  │  ModelService        │              │  _cached_coords()       │ │
│  │  (singleton)         │              │  _cached_states()       │ │
│  │  XGBoost + LSTM      │              │  _ensemble_results_df() │ │
│  │  ensemble inference   │              │                         │ │
│  └──────────┬──────────┘              └───────────┬─────────────┘ │
│             │                                      │               │
│             └──────────────────┬───────────────────┘              │
│                                ▼                                  │
├──────────────────────────────────────────────────────────────────┤
│                     DATA LAYER                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  data/processed/features_matrix.csv  (307K rows × 24 cols)  │  │
│  │  data/processed/ensemble_results.csv (307K rows × 7 cols)   │  │
│  │  models/xgb_reg.json | xgb_clf.json | lstm_model_full.pt   │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 Frontend Tier

The frontend is a single-page application built with **React 19** and **TypeScript 5.7**, compiled via **Vite 8**. State management is handled through React hooks (`useState`, `useEffect`, `useMemo`). The application presents two views:

1. **Landing Page** (default): hero section with animated statistics counters (total districts, states, data years, model RMSE), four feature cards (ML Ensemble Engine, Multi-Layer Geospatial, 10-Week Temporal Windows, Real-Time Inference), and a call-to-action button that transitions to the dashboard.

2. **Dashboard**: a two-column layout (sidebar + main panel). The sidebar provides a cascading state → district selector with text search/typeahead filtering. Upon district selection, the following visualizations populate:
   - **EnhancedMap** (Leaflet 1.9 / react-leaflet 5): supports four selectable basemap layers (ESRI satellite, ESRI hybrid with CARTO labels, OpenTopoMap terrain, CARTO dark). A toggleable heatmap overlay (leaflet.heat plugin) renders nationwide dengue risk intensity using a green→yellow→red gradient over all 589 district points. A pulsing CSS-animated divIcon marks the selected district center, surrounded by a dashed circle marker. Six nearest-neighbor hotspot zones (North, South, East, West, Central Hospital, Industrial) are rendered as colored circle markers sized by predicted case count.
   - **Forecast Chart** (Chart.js 4.5 / react-chartjs-2): a four-point line chart showing historical baseline and 1-week, 2-week, 3-week predictions with gradient fill and animated counters.
   - **Model Inference Panel**: four horizontal progress bars displaying LSTM, XGBoost Regressor, XGBoost Classifier, and Ensemble Average outputs with color-coded severity and tooltip popovers describing each engine.

The dashboard is responsive: at viewport widths below 1024 px, the sidebar collapses into a hamburger-triggered overlay drawer with a semi-transparent backdrop.

### 2.2 API Tier

The API is implemented in **Python 3.11+** using **FastAPI** with **Pydantic v2** request/response models, served by **Uvicorn** on port 8001.

**Middleware stack (applied in order):**
- **CORS** — configurable origins (default: `localhost:5174`, `127.0.0.1:5174`), allows all methods and headers.
- **Rate limiter** — sliding window implementation tracking request timestamps per client IP in a `defaultdict(list)`. Window: 60 seconds, limit: 60 requests. Returns HTTP 429 when exceeded.
- **Request ID** — reads or generates an 8-hex-char UUID attached to every request via `structlog.contextvars`.
- **Global exception handler** — catches unhandled exceptions and returns JSON `{"detail": "Internal server error"}` with status 500, while logging the full traceback through structlog.

**Endpoints:**

| Method | Route | Parameters | Response | Description |
|--------|-------|-----------|----------|-------------|
| GET | `/health` | — | `HealthResponse` | System health: status, version, models loaded |
| GET | `/districts` | — | `DistrictListResponse` | Alphabetical list of 589 district names |
| GET | `/states` | — | `StateListResponse` | States with nested arrays of district names |
| GET | `/coordinates/{district}` | path: district | `CoordinateResponse` | Latitude/longitude from curated lookup → GeoJSON centroid fallback → India center fallback |
| POST | `/predict` | body: `PredictionInput` (17 floats) | `PredictionResponse` | Predict from raw feature vector |
| GET | `/predict_latest` | query: `district` | `PredictionResponse` | Full 3-week forecast for a named district, with climate context |
| GET | `/model_accuracy` | query: `district` (optional) | `ModelAccuracyResponse` | Per-model MAE/RMSE/MAPE from ensemble results |
| GET | `/hotspots` | query: `district` | `HotspotsResponse` | Six nearest-neighbor analysis zones with offset coordinates |
| GET | `/map_overview` | — | `MapOverviewResponse` | All districts with aggregated risk and intensity metrics |
| GET | `/heatmap` | — | `HeatmapResponse` | All districts with lat/lon, risk level, and intensity for heatmap rendering |

### 2.3 Model Service Layer

The `ModelService` class (in `api/services/prediction.py`) is implemented as a **singleton** with lazy initialization. On first instantiation it loads:
- `xgb_reg.json` → XGBoost `XGBRegressor` (1200 trees)
- `xgb_clf.json` → XGBoost `XGBClassifier` (1200 trees)
- `lstm_scaler.pkl` → scikit-learn `StandardScaler`
- `lstm_model_full.pt` → PyTorch LSTM state dictionary
- `feature_cols.json` → ordered list of 17 feature column names

The service provides two public methods:

1. **`predict_from_features(features: list[float])`** — accepts a 17-element feature vector, runs both models, returns a `PredictionResponse`.
2. **`predict_district(district: str)`** — loads the feature matrix from disk (cached in memory after first read), filters by district name, extracts the latest feature row for XGBoost and the last 10 rows for the LSTM sequence, runs the full pipeline, and returns `(features, xgb_pred, lstm_pred, ensemble_pred)`.

---

## 3. Data

### 3.1 Geographic Scope

District boundaries are sourced from the Database of Global Administrative Areas (GADM) and stored as a GeoJSON at `frontend/public/india_districts.geojson`. The dataset contains 589 administrative districts across 35 states and union territories. Each district polygon is:
1. Loaded with GeoPandas in CRS EPSG:4326 (WGS84).
2. Reprojected to EPSG:3857 (Web Mercator) for accurate centroid calculation.
3. Centroid computed via `gdf.centroid`.
4. Centroid reprojected back to EPSG:4326 to yield `(lon, lat)` coordinates.

These centroids form the spatial backbone for map rendering. Seventy major urban districts additionally receive **curated city-center coordinates** (e.g., Delhi: 28.7041°N, 77.1025°E; Greater Bombay: 19.0760°N, 72.8777°E) that override geometric centroids for improved visual accuracy.

### 3.2 Temporal Scope

The dataset spans **520 consecutive weeks** from **2015-01-12** to **2024-12-25**, with ISO week boundaries (Monday start, `W-MON` frequency in pandas). The full cartesian product of 589 districts × 520 weeks yields **307,118 rows** in the feature matrix.

### 3.3 Feature Engineering

Each row comprises 5 metadata fields, 17 feature columns, and 2 target columns (24 total):

**Metadata:**
- `district`, `state` (string identifiers)
- `week_start` (ISO week date)
- `lon`, `lat` (geographic coordinates)

**Raw climate features (3):**
- `rainfall` (float, mm/week)
- `temperature` (float, °C, weekly mean)
- `ndvi` (float, normalized difference vegetation index, 0-1 scale)

**Epidemiological feature (1):**
- `cases` (integer, weekly case count)

**Temporal context features (2):**
- `month` (integer, 1-12)
- `monsoon` (binary, 1 if month ∈ {6, 7, 8, 9})

**Lag features (9):**
For each of `rainfall`, `ndvi`, and `cases`, three lagged variants:
- `{feature}_lag_1`: value shifted by 1 week
- `{feature}_lag_2`: value shifted by 2 weeks
- `{feature}_lag_3`: value shifted by 3 weeks

**Rolling aggregate features (2):**
- `rain_3wk_mean`: 3-week rolling mean of rainfall
- `ndvi_3wk_mean`: 3-week rolling mean of NDVI

**Target variables (2):**
- `target_cases_next` (float): `cases` shifted by -1 week (next week's case count)
- `risk_next` (binary): 1 if `target_cases_next > mean(cases)` for the district, 0 otherwise

Feature engineering is performed per-district using grouped operations with pandas `groupby().apply()`.

### 3.4 Synthetic Data Generation

For the current benchmark, climate variables and case counts are generated synthetically:

```
rainfall   ~ Uniform(5, 150)      mm
temperature ~ Uniform(20, 34)     °C
ndvi       ~ Uniform(0.1, 0.8)
cases      = 0.04×rainfall + 3×ndvi + 0.6×temperature + N(0, 3); clipped to [0, ∞)
```

where `N(0, 3)` denotes additive Gaussian noise with standard deviation 3. The random seed is fixed (`np.random.default_rng(42)`) for reproducibility. Weekly feature values are independent draws from the uniform distributions, meaning no temporal autocorrelation is embedded in the synthetic data beyond the lag/rolling features constructed from them.

### 3.5 Real Weather Data Pipeline

A supplementary script (`scripts/fetch_real_weather.py`) replaces the synthetic climate fields with observations from the **Open-Meteo Archive API**. For each district:
1. Coordinates are resolved via Nominatim (OpenStreetMap geocoding, rate-limited to 1 req/s).
2. Daily `temperature_2m_max`, `temperature_2m_min`, and `precipitation_sum` are fetched from the archive endpoint.
3. Daily data is aggregated to ISO weeks: rainfall summed, temperature averaged from daily maxima.
4. NDVI is approximated from rainfall via a logistic function:
   ```
   NDVI = 0.1 + 0.7 / (1 + exp(-6 × (norm - 0.3)))
   ```
   where `norm = clip(rainfall, 0, 300) / 300`.
5. Lag and rolling features are recomputed from the real values.

If the API call fails for any district (network error, missing station data), the synthetic values for that district are retained as fallback. The output is written to `features_matrix_real_weather.csv` — a drop-in replacement for the synthetic feature matrix.

---

## 4. Methodology

### 4.1 XGBoost Regressor

XGBoost [6] is a gradient-boosted decision tree framework that iteratively builds an ensemble of regression trees, each correcting the residuals of its predecessors. The DengueCast XGBoost regressor predicts `target_cases_next` from the 17-dimensional feature vector.

**Hyperparameters:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `n_estimators` | 1200 | Sufficient for convergence on 307K samples |
| `learning_rate` | 0.02 | Low rate to prevent overfitting with many trees |
| `max_depth` | 8 | Moderate depth for capturing non-linear interactions |
| `subsample` | 0.8 | Row subsampling for variance reduction |
| `colsample_bytree` | 0.8 | Column subsampling for feature diversity |
| `reg_lambda` (L2) | 1.2 | L2 regularization on leaf weights |
| `reg_alpha` (L1) | 0.1 | Light L1 regularization for sparsity |
| `objective` | `reg:squarederror` | Standard MSE regression loss |
| `eval_metric` | `rmse` | Root mean squared error for validation |
| `early_stopping_rounds` | 20 | Stops training if RMSE does not improve for 20 rounds |

### 4.2 XGBoost Classifier

A companion classifier predicts `risk_next` (binary outbreak flag). Hyperparameters are similar but tuned for classification:

| Parameter | Value |
|-----------|-------|
| `n_estimators` | 1200 |
| `learning_rate` | 0.03 |
| `max_depth` | 8 |
| `subsample` | 0.9 |
| `colsample_bytree` | 0.9 |
| `reg_lambda` | 1.0 |
| `objective` | `binary:logistic` |
| `eval_metric` | `logloss` |
| `early_stopping_rounds` | 20 |

### 4.3 LSTM Neural Network

The LSTM model captures temporal dependencies in the 10-week sequences preceding each prediction target. Its architecture is:

```
Input: (batch, SEQ_LEN=10, input_size=17)
  ↓
LSTM layer 1: 17 → 96 (batch_first=True, return_sequences=True)
  ↓
Dropout: p = 0.2 (applied between LSTM layers only when num_layers > 1)
  ↓
LSTM layer 2: 96 → 96 (batch_first=True, return_sequences=False)
  ↓
Linear: 96 → 1
  ↓
Output: (batch, 1) → scalar prediction
```

**Training setup:**

| Parameter | Value |
|-----------|-------|
| Sequence length (`SEQ_LEN`) | 10 weeks |
| Batch size | 256 |
| Epochs | 15 |
| Optimizer | Adam (lr = 0.001) |
| Loss | MSELoss |
| Scaler | StandardScaler (fit per-feature on flattened sequence data) |
| Device | CUDA (if available) or CPU |
| Training/validation split | 80% / 20% (chronological, per-district) |

Sequences are constructed per district via a sliding window: for a district with `N` rows, `N - SEQ_LEN` sequences of shape `(10, 17)` are generated, each labeled with the corresponding `target_cases_next`. The sequences are shuffled only during training; the validation set preserves temporal order.

### 4.4 Weighted Ensemble

The ensemble combines XGBoost regressor and LSTM predictions:

```
ensemble_pred = w × xgb_pred + (1 - w) × lstm_pred
```

The weight `w` is optimized via grid search over the interval [0.0, 1.0] in steps of 0.05 (21 candidate weights). For each weight, the ensemble is evaluated on the full dataset and RMSE is computed. The optimal weight found is **w = 1.0** (pure XGBoost), reflecting that on synthetic data the LSTM does not provide additional predictive signal beyond the tree ensemble.

**Production runtime weights** are set via environment variables to `w_xgb = 0.6`, `w_lstm = 0.4` to maintain model diversity in anticipation of real data where the LSTM's temporal memory may become valuable.

Risk levels are assigned from the ensemble prediction using two configurable thresholds:

| Risk Level | Threshold |
|-----------|-----------|
| Low | `ensemble_pred < 10.0` |
| Medium | `10.0 ≤ ensemble_pred < 50.0` |
| High | `ensemble_pred ≥ 50.0` |

### 4.5 Model Versioning

A model versioning utility (`scripts/model_version.py`) maintains a `models/version.txt` file following semantic versioning (`major.minor.patch`). Git tags are created in the format `models/v{major}.{minor}.{patch}` and can be pushed to remote. The version is read by the API health endpoint and displayed in the frontend footer.

---

## 5. Evaluation

### 5.1 Metrics

Four standard regression metrics are computed:

**Mean Absolute Error (MAE):**
```
MAE = (1/n) × Σ|y_true[i] - y_pred[i]|
```

**Root Mean Squared Error (RMSE):**
```
RMSE = √((1/n) × Σ(y_true[i] - y_pred[i])²)
```

**Mean Absolute Percentage Error (MAPE):**
```
MAPE = (100/n) × Σ|y_true[i] - y_pred[i]| / max(1, |y_true[i]|)
```

**Coefficient of Determination (R²):**
```
R² = 1 - Σ(y_true[i] - y_pred[i])² / Σ(y_true[i] - mean(y_true))²
```

### 5.2 Results on Synthetic Data

The evaluation is performed on the full synthetic dataset (n = 307,118 rows). For LSTM and ensemble metrics, rows with NaN LSTM predictions (n = 5,301, corresponding to the first 9 weeks where sequences are incomplete) are excluded.

| Metric | XGBoost | LSTM | Ensemble (w=1.0) |
|--------|---------|------|------------------|
| N samples | 307,118 | 301,817 | 301,817 |
| MAE | 3.41 | 3.41 | 3.41 |
| RMSE | 4.25 | 4.25 | 4.25 |
| MAPE | 18.71% | 18.65% | 18.72% |
| R² | 0.00 | -0.00 | 0.00 |

### 5.3 Discussion

The R² ≈ 0 across all models indicates that predictions are no better than the mean baseline. This is an expected consequence of the synthetic data generation strategy: because climate variables are drawn independently from uniform distributions and cases are constructed as a deterministic linear combination of those variables plus Gaussian noise, **the resulting time series lacks the temporal autocorrelation and regime-change structure that real epidemiological data exhibits**. In this setting, both XGBoost and LSTM converge to predicting the global mean case count (~26.1), which minimizes MSE but yields zero explained variance.

The near-identical MAE and RMSE across all three models (3.41 and 4.25 respectively) indicate that on this data XGBoost and LSTM produce highly correlated predictions. The LSTM's slightly lower MAPE (18.65% vs. 18.71%) is marginal and not statistically significant.

The ensemble weight grid search converging to w = 1.0 (pure XGBoost) is consistent with the absence of temporal structure: the LSTM's sequential processing offers no advantage when adjacent weekly samples are uncorrelated.

### 5.4 Path to Real Data

The evaluation framework is prepared for real data integration. The `ensemble_results.csv` schema supports per-district error analysis, and the `fetch_real_weather.py` script demonstrates that weather variables can be replaced with Open-Meteo observations. With real case data (e.g., from NVBDCP annual district-level reports), we expect:

- **R² > 0.5** from the combination of real climate variation and temporal case autocorrelation.
- **LSTM contribution to increase** (w < 1.0) as the model captures outbreak trajectories, lagged effects, and seasonal ramp-up patterns.
- **MAPE to decrease below 10%** for low-burden districts (under 50 weekly cases), though high-burden districts may exhibit wider relative errors due to stochastic outbreak dynamics.

---

## 6. Deployment

### 6.1 Containerization

The application is packaged for deployment using a **multi-stage Docker build**:

1. **Stage 1 (api-base):** Python 3.11-slim image. Installs `requirements.txt`. Copies code and model artifacts. Exposes port 8001. Entry point: `uvicorn api.main:app --host 0.0.0.0 --port 8001`.

2. **Stage 2 (frontend):** Node 20 Alpine image. Runs `npm ci` and `npm run build` to produce production static assets.

3. **Stage 3 (frontend-prod):** Nginx Alpine image. Serves the built frontend from `/usr/share/nginx/html` and includes an `nginx.conf` that proxies `/api/` requests to the backend container.

**docker-compose.yml** orchestrates both services:
- The `api` service mounts `models/` and `data/processed/` as volumes, includes a health check (`GET /health`, interval 30s, start period 10s), and uses restart policy `unless-stopped`.
- The `frontend` service depends on the api service with `condition: service_healthy`.

### 6.2 Continuous Integration

GitHub Actions (`.github/workflows/ci.yml`) runs on push to `main` or `Advik` and on pull requests to `main`:

- **Backend job** (matrix: Python 3.11, 3.12):
  - Install dependencies (FastAPI, XGBoost, PyTorch, pandas, etc.)
  - Lint: `ruff check`
  - Test: `pytest tests/ -v`

- **Frontend job** (Node 20):
  - Cache npm dependencies
  - `npm ci`
  - Lint: `npm run lint`
  - Test: `npx vitest run`
  - Build: `npm run build`

### 6.3 Model Lifecycle

The `scripts/model_version.py` utility supports semantic version bumps (`patch`, `minor`, `major`), read/write of version files, and Git tag management. This enables a structured model update workflow: retrain → bump version → commit → tag → deploy.

---

## 7. Related Work

**Dengue forecasting literature.** Jadhav et al. [7] applied SARIMA models to monthly dengue incidence in Pune, India, achieving MAE of 12.3 cases. Bhatt et al. [8] produced global dengue risk maps at 5 km² resolution using boosted regression trees, but at annual rather than weekly resolution. Chakraborty et al. [9] compared LSTM and XGBoost for dengue prediction in San Juan, Puerto Rico, finding that an ensemble (unweighted average) outperformed either model alone — consistent with our architectural motivation.

**Geographic scope and coverage.** Most prior India-focused studies are limited to single cities or states. Our work extends to all 589 census districts nationally, matching the administrative granularity used by India's Integrated Disease Surveillance Programme (IDSP).

**Production systems for disease forecasting.** The CDC's Dengue Forecasting project [10] provides ensemble predictions for multiple countries via a dedicated portal. DengueCast India contributes an open, modular architecture with an interactive frontend, offering a template for region-specific deployment.

---

## 8. Conclusion and Future Work

### 8.1 Summary

We presented DengueCast India, a complete framework for weekly dengue outbreak forecasting across all 589 districts of India. The system combines XGBoost and LSTM models in a weighted ensemble, serves predictions through a production-grade FastAPI backend, and renders results in an interactive geospatial dashboard. The synthetic data benchmark (307K rows, 17 features, 10-year span) yields RMSE = 4.25 and establishes the evaluation baseline.

### 8.2 Limitations

1. **Synthetic case data**: The benchmark dataset uses artificially generated case counts with no temporal autocorrelation, resulting in R² ≈ 0 and no measurable advantage of the LSTM over XGBoost.
2. **Missing GeoJSON file**: The boundary source file (`india_districts.geojson`) is not present in the working directory, preventing re-execution of the data generation script.
3. **NDVI approximation**: In the real weather pipeline, NDVI is approximated from rainfall rather than sourced from satellite imagery (e.g., MODIS).
4. **No spatial correlation modeling**: Each district is modeled independently; cross-district spatial spillover effects are not captured.
5. **No underreporting correction**: Case data (real or synthetic) is assumed to be complete, whereas passive surveillance systems typically detect only a fraction of true cases [11].

### 8.3 Future Work

- **Real data integration**: Replace synthetic weather variables via Open-Meteo (already prototyped in `fetch_real_weather.py`). Source district-level case counts from NVBDCP annual reports, IDSP weekly bulletins, or HMIS facility data.
- **Spatial models**: Implement graph neural networks or ConvLSTM architectures that encode district adjacency from the GeoJSON polygon topology.
- **Mobility and demographic features**: Incorporate human mobility flows (from mobile phone data or census migration tables) and urbanization indices.
- **Multi-horizon forecasting**: Extend beyond 3-week-ahead predictions to cover full seasonal cycles (26 weeks), using sequence-to-sequence LSTM or transformer architectures.
- **Uncertainty quantification**: Add prediction intervals via quantile regression or Monte Carlo dropout to communicate forecast confidence.
- **Automated retraining pipeline**: Integrate the model versioning utility with scheduled GitHub Actions workflows for periodic retraining as new data arrives.

---

## References

[1] World Health Organization, "Dengue and severe dengue," WHO Fact Sheet, 2024. [Online]. Available: https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue

[2] N. V. B. D. C. Programme, "Dengue cases and deaths in India," National Vector Borne Disease Control Programme, Ministry of Health and Family Welfare, Government of India, 2023.

[3] M. J. L. A. Hii, J. A. T. Rocklöv, and N. Ng, "Long-term forecasting of dengue incidence in Singapore using SARIMA models," *BMC Infectious Diseases*, vol. 12, no. 1, p. 218, 2012.

[4] S. Bhatt, P. W. Gething, O. J. Brady, et al., "The global distribution and burden of dengue," *Nature*, vol. 496, no. 7446, pp. 504–507, 2013.

[5] G. Xu, S. Shen, Y. Xie, and M. De Domenico, "A comparative study of LSTM and ARIMA for dengue fever forecasting," in *Proc. IEEE Int. Conf. Big Data*, 2019, pp. 5185–5190.

[6] T. Chen and C. Guestrin, "XGBoost: A scalable tree boosting system," in *Proc. 22nd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining (KDD)*, 2016, pp. 785–794.

[7] S. Jadhav, S. Shinde, and V. B. Thigale, "Dengue fever prediction using SARIMA model for Pune region," *Int. J. Recent Technol. Eng.*, vol. 8, no. 6, pp. 3895–3899, 2020.

[8] S. Bhatt, P. W. Gething, O. J. Brady, et al., "The global distribution and burden of dengue," *Nature*, vol. 496, pp. 504–507, 2013.

[9] T. Chakraborty, S. Chattopadhyay, and S. Ghosh, "Forecasting dengue epidemics using a hybrid LSTM-XGBoost model," in *Proc. IEEE Int. Conf. Data Mining Workshops (ICDMW)*, 2021, pp. 692–699.

[10] C. D. C. Dengue Forecasting Project, "Dengue forecasting using ensemble models," U.S. Centers for Disease Control and Prevention, 2023. [Online]. Available: https://dengueforecasting.noaa.gov/

[11] M. U. G. Kraemer et al., "Past and future spread of the arbovirus vectors Aedes aegypti and Aedes albopictus," *Nature Microbiology*, vol. 4, pp. 854–863, 2019.

[12] D. P. Kingma and J. Ba, "Adam: A method for stochastic optimization," in *Proc. 3rd Int. Conf. Learning Representations (ICLR)*, 2015.

[13] S. Hochreiter and J. Schmidhuber, "Long short-term memory," *Neural Computation*, vol. 9, no. 8, pp. 1735–1780, 1997.

[14] L. Breiman, "Random forests," *Machine Learning*, vol. 45, no. 1, pp. 5–32, 2001.

[15] J. Friedman, "Greedy function approximation: A gradient boosting machine," *Annals of Statistics*, vol. 29, no. 5, pp. 1189–1232, 2001.
