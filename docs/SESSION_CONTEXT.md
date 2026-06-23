# Session Context

Last updated: 23 Jun 2026

## Project Structure

```
biosafety/
├── api/               # FastAPI backend
│   ├── main.py       # API endpoints
│   ├── schemas.py    # Pydantic models
│   └── services/
│       └── prediction.py  # ModelService singleton
├── web/               # React + Vite frontend
│   ├── src/
│   │   ├── App.tsx         # Main dashboard (TypeScript)
│   │   ├── App.css
│   │   ├── index.css
│   │   ├── main.tsx        # Entry point
│   │   ├── components/
│   │   │   ├── EnhancedMap.tsx  # Map component (TypeScript)
│   │   │   └── ErrorBoundary.tsx
│   │   ├── types/
│   │   │   ├── api.ts          # TypeScript API types
│   │   │   └── leaflet.heat.d.ts
│   │   └── tests/
│   │       ├── setup.ts
│   │       ├── App.test.tsx         (2 tests)
│   │       └── ErrorBoundary.test.tsx (4 tests)
│   ├── package.json
│   ├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
│   ├── vite.config.js
│   └── eslint.config.js
├── models/             # Trained ML models
│   ├── xgb_reg.json       # XGBoost regressor (latest: Phase 2 retrain)
│   ├── xgb_clf.json       # XGBoost classifier (latest: Phase 2 retrain)
│   ├── lstm_model_full.pt # LSTM model (latest: Phase 2 with SEQ_LEN=10)
│   ├── lstm_scaler.pkl    # StandardScaler for LSTM
│   └── feature_cols.json  # 17 feature column names
├── src/                # Training/evaluation code
│   ├── train.py            # Pipeline orchestrator
│   ├── features/make_features.py
│   ├── models/
│   │   ├── train_xgb.py    # XGBoost with train/val split + early stopping
│   │   ├── train_lstm.py   # LSTM with SEQ_LEN=10, district sequences
│   │   └── ensemble.py     # Ensemble evaluation + weight optimization
│   ├── viz/heatmap.py
│   └── eval/evaluate.py
├── scripts/            # Utilities
│   ├── generate_india_dataset.py
│   ├── generate_us_temperature_heatmap.py
│   └── generate_us_temperature_heatmap_advanced.py
├── data/processed/     # Datasets
│   ├── features_matrix.csv      (307K rows, 24 cols)
│   ├── ensemble_results.csv
│   ├── eval_metrics.json
│   ├── dengue_weekly_clean.csv
│   └── synthetic_dengue_weekly.csv
├── docs/
│   ├── *.md           # Project documentation
│   └── SESSION_CONTEXT.md   # THIS FILE
├── tests/
│   ├── test_schemas.py  # 9 passing tests
│   └── conftest.py
├── config.py           # Centralized pydantic-settings
├── requirements.txt    # Python deps (>= ranges)
├── pyproject.toml      # ruff, black, mypy, pytest
├── Dockerfile, docker-compose.yml, nginx.conf, start.ps1
├── .env / .env.example / .gitignore
└── README.md
```

## Implementation Phases

### Phase 1: Code Quality & Infrastructure (COMPLETED)
- [x] requirements.txt with Python dependencies
- [x] pyproject.toml (ruff, black, mypy, pytest)
- [x] config.py with pydantic-settings + .env support
- [x] api/schemas.py with Pydantic models for all endpoints
- [x] api/services/prediction.py with singleton ModelService
- [x] api/main.py with lifespan, /health, pydantic validation
- [x] TypeScript config + types/api.ts for frontend
- [x] ESLint updated for TypeScript
- [x] start.ps1 for Windows one-command startup
- [x] Dockerfile + docker-compose.yml + nginx.conf
- [x] 9 unit tests (test_schemas.py)
- [x] README.md rewritten
- [x] Project directory organized (docs/, removed duplicates)

### Phase 2: ML Pipeline Hardening (COMPLETED)
- [x] LSTM training with proper SEQ_LEN=10 and district grouping
- [x] XGBoost training with train/val split + early stopping
- [x] LSTM model extracted to shared src/models/lstm_model.py
- [x] train.py pipeline orchestrator
- [x] Ensemble evaluation with batched LSTM prediction (optimized)
- [x] Updated config/.env with ensemble weights
- [x] Verified end-to-end API with all endpoints passing

### Phase 3: API Production Hardening (COMPLETED)
- [x] Rate limiting (in-memory, 60 req/min per IP on POST /predict)
- [x] In-memory cache for districts list + feature matrix (ModelService singleton)
- [x] Structured logging (structlog) with request IDs on all responses
- [x] Global exception handler catching unhandled errors → proper JSON 500
- [x] X-Request-ID header on every response for request tracing

### Phase 4: Frontend Professionalization (COMPLETED)
- [x] Full TypeScript migration (App.tsx, EnhancedMap.tsx, main.tsx)
- [x] React ErrorBoundary component with fallback UI + retry button
- [x] ErrorBoundary wrapping app root + map component
- [x] Cleaned unused imports and dead code (generateHotspots, Nominatim direct call)
- [x] Replaced direct Nominatim frontend calls → backend `/coordinates/{district}` endpoint
- [x] Backend coordinates endpoint with lazy Nominatim caching (in-memory)
- [x] Vitest + React Testing Library + jsdom setup
- [x] 6 frontend tests (ErrorBoundary: 4, App smoke: 2)
- [x] Frontend production build: ~582 KB gzipped (no errors)

### Phase 5: Data & Infrastructure (NOT STARTED)
- [ ] GitHub Actions CI
- [ ] Real data integration (Open-Meteo API)
- [ ] Model versioning

## Current Issues / Known Problems

1. **Synthetic data**: All data is synthetic (random). Model metrics (RMSE ~4.25, R2 ~0) reflect random data.
2. **scikit-learn version mismatch**: Scaler was saved with 1.6.1, loaded with 1.8.0. Non-critical.
3. **Nominatim rate limits**: Backend `/coordinates/{district}` endpoint calls Nominatim on cache miss; mass scanning may hit rate limits.

## Quick Start (dev)

```powershell
# Terminal 1 - Backend (from project root)
cd api; python -m uvicorn main:app --reload --port 8001

# Terminal 2 - Frontend (from project root)
cd web; npm run dev

# Or use script
.\start.ps1

# Retrain all models
python src/train.py
```
