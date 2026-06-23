# DengueCast India

AI-powered dengue outbreak forecasting system for Indian districts, using an ensemble of XGBoost and LSTM models.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Start both servers
.\start.ps1

# Or start manually:
# Terminal 1: cd api && python -m uvicorn main:app --reload --port 8001
# Terminal 2: cd frontend && npm run dev
```

- **Frontend:** http://localhost:5174
- **API Docs:** http://localhost:8001/docs
- **Health:** http://localhost:8001/health

## Project Structure

```
biosafety/
├── api/               # FastAPI backend (model serving)
│   ├── main.py        # API endpoints
│   ├── schemas.py     # Pydantic request/response models
│   └── services/      # Business logic (prediction, etc.)
├── frontend/               # React + Vite frontend
│   ├── src/
│   │   ├── App.tsx    # Main dashboard
│   │   ├── components/
│   │   └── types/     # TypeScript type definitions
│   └── vite.config.js
├── models/            # Pre-trained ML models
├── src/               # Training & evaluation scripts
├── scripts/           # Data generation & utilities
├── data/              # Datasets (processed)
├── config.py          # Centralized settings
├── requirements.txt   # Python dependencies
├── Dockerfile         # Containerization
└── docker-compose.yml # Full stack deployment
```

## Models

| Model | Type | File |
|-------|------|------|
| XGBoost Regressor | Regression | `models/xgb_reg.json` |
| XGBoost Classifier | Binary (outbreak yes/no) | `models/xgb_clf.json` |
| LSTM | Time-series regression | `models/lstm_model_full.pt` |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check + model status |
| GET | `/districts` | List all available districts |
| GET | `/predict_latest?district=` | Latest prediction for a district |
| POST | `/predict` | Predict from raw feature vector |
| GET | `/model_accuracy?district=` | Model accuracy metrics |
| GET | `/hotspots?district=` | Nearby hotspot predictions |
| GET | `/map_overview` | Overview of all districts |

## Tech Stack

- **Backend:** Python, FastAPI, PyTorch, XGBoost, scikit-learn
- **Frontend:** React 19, Vite, Leaflet, Chart.js, Lucide Icons
- **Infrastructure:** Docker, Docker Compose
