import { useState, useEffect, type FC } from "react";
import axios from "axios";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { Line } from "react-chartjs-2";
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle,
  Activity,
  Loader2,
  Thermometer,
  Disc,
  Compass,
  Settings,
  ArrowUpRight,
  MapPin,
} from "lucide-react";
import EnhancedMap from "./components/EnhancedMap";
import ErrorBoundary from "./components/ErrorBoundary";
import type {
  PredictionResponse,
  HotspotData,
  TransformedHotspot,
  CoordinateResponse,
} from "./types/api";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

const API_URL = "/api";

/* ── Animated counter ────────────────────────────────────────── */

const AnimatedCounter: FC<{ value: number; duration?: number }> = ({
  value,
  duration = 1000,
}) => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const endValue = Math.max(0, Math.round(value));
    if (endValue === 0) {
      setCount(0);
      return;
    }

    let startTimestamp: number | null = null;
    let frameId: number;

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const eased = progress === 1 ? 1 : 1 - 2 ** (-10 * progress);
      setCount(Math.floor(eased * endValue));
      if (progress < 1) {
        frameId = window.requestAnimationFrame(step);
      } else {
        setCount(endValue);
      }
    };

    frameId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frameId);
  }, [value, duration]);

  return <span>{count.toLocaleString()}</span>;
};

/* ── Helpers ─────────────────────────────────────────────────── */

function getRiskColor(level?: string): string {
  switch (level?.toLowerCase()) {
    case "low":
      return "#10b981";
    case "medium":
      return "#f59e0b";
    case "high":
      return "#f43f5e";
    default:
      return "#3b82f6";
  }
}

function getRiskBg(level?: string): string {
  switch (level?.toLowerCase()) {
    case "low":
      return "rgba(16, 185, 129, 0.08)";
    case "medium":
      return "rgba(245, 158, 11, 0.08)";
    case "high":
      return "rgba(244, 63, 94, 0.08)";
    default:
      return "rgba(59, 130, 246, 0.08)";
  }
}

function getRiskIcon(level?: string) {
  switch (level?.toLowerCase()) {
    case "low":
      return <CheckCircle className="risk-header-icon text-emerald" />;
    case "medium":
      return <AlertTriangle className="risk-header-icon text-amber" />;
    case "high":
      return <ShieldAlert className="risk-header-icon text-rose" />;
    default:
      return <Activity className="risk-header-icon text-blue" />;
  }
}

/* ── App ─────────────────────────────────────────────────────── */

const App: FC = () => {
  const [districts, setDistricts] = useState<string[]>([]);
  const [selectedDistrict, setSelectedDistrict] = useState("");
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [districtCoords, setDistrictCoords] = useState<[number, number]>([20.5937, 78.9629]);
  const [coordsCache, setCoordsCache] = useState<Record<string, [number, number]>>({});
  const [mapZoom, setMapZoom] = useState(5);
  const [hotspots, setHotspots] = useState<TransformedHotspot[]>([]);

  const fetchDistricts = async () => {
    try {
      const res = await axios.get<{ districts: string[] }>(`${API_URL}/districts`);
      setDistricts(res.data.districts);
      if (res.data.districts.length > 0) {
        setSelectedDistrict(res.data.districts[0]);
      }
    } catch {
      setError("Connection interrupted. Please verify backend state.");
    }
  };

  const fetchCoordinates = async (district: string) => {
    if (coordsCache[district]) {
      setDistrictCoords(coordsCache[district]);
      setMapZoom(12);
      return;
    }
    try {
      const res = await axios.get<CoordinateResponse>(`${API_URL}/coordinates/${district}`);
      const { lat, lon } = res.data;
      const coords: [number, number] = [lat, lon];
      setDistrictCoords(coords);
      setMapZoom(coords[0] === 20.5937 ? 5 : 12);
      setCoordsCache((prev) => ({ ...prev, [district]: coords }));
    } catch {
      setDistrictCoords([20.5937, 78.9629]);
      setMapZoom(5);
    }
  };

  const fetchPrediction = async (district: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<PredictionResponse>(`${API_URL}/predict_latest`, {
        params: { district },
      });
      setPrediction(res.data);

      const hotspotsRes = await axios.get<{
        hotspots: HotspotData[];
        total_hotspots: number;
      }>(`${API_URL}/hotspots`, { params: { district } });

      const transformedHotspots: TransformedHotspot[] = hotspotsRes.data.hotspots.map(
        (h: HotspotData) => ({
          id: h.id,
          name: h.name,
          coords: [
            districtCoords[0] + h.offset_lat,
            districtCoords[1] + h.offset_lon,
          ] as [number, number],
          type: h.type,
          cases: h.avg_cases,
          maxCases: h.max_cases,
          intensity: h.intensity,
          districtRef: h.district_ref,
        }),
      );

      setHotspots(transformedHotspots);
    } catch {
      setError("Operational error: Unable to retrieve prediction metrics.");
      setHotspots([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDistricts();
  }, []);

  useEffect(() => {
    if (selectedDistrict) {
      fetchCoordinates(selectedDistrict).then(() => {
        fetchPrediction(selectedDistrict);
      });
    }
  }, [selectedDistrict]);

  const chartData: ChartData<"line"> | null = prediction
    ? {
        labels: [
          prediction.history_week_start || "History",
          prediction.forecast_week_1 || "Week 1",
          prediction.forecast_week_2 || "Week 2",
          prediction.forecast_week_3 || "Week 3",
        ],
        datasets: [
          {
            label: "Predicted Vector Density (Weekly cases)",
            data: [
              prediction.climate?.cases || 0,
              prediction.predicted_cases_1w ?? 0,
              prediction.predicted_cases_2w ?? 0,
              prediction.predicted_cases_3w ?? 0,
            ],
            borderColor: getRiskColor(prediction.risk_level),
            backgroundColor: (context) => {
              const chart = context.chart;
              const { ctx, chartArea } = chart;
              if (!chartArea) return "transparent";
              const gradient = ctx.createLinearGradient(
                0,
                chartArea.top,
                0,
                chartArea.bottom,
              );
              gradient.addColorStop(0, getRiskBg(prediction.risk_level));
              gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
              return gradient;
            },
            tension: 0.4,
            fill: true,
            pointBackgroundColor: getRiskColor(prediction.risk_level),
            pointBorderColor: "#ffffff",
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 7,
            borderWidth: 2,
          },
        ],
      }
    : null;

  const chartOptions: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1f2937",
        titleFont: { family: "Outfit", size: 13, weight: "600" },
        bodyFont: { family: "Outfit", size: 12 },
        padding: 12,
        cornerRadius: 6,
        borderColor: "rgba(255,255,255,0.08)",
        borderWidth: 1,
      },
    },
    scales: {
      y: {
        grid: { color: "rgba(255, 255, 255, 0.04)", drawBorder: false },
        ticks: { color: "#94a3b8", font: { family: "Outfit", size: 11 } },
      },
      x: {
        grid: { display: false },
        ticks: { color: "#94a3b8", font: { family: "Outfit", size: 11 } },
      },
    },
  };

  return (
    <ErrorBoundary>
      <div className="modern-layout">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="branding">
            <div className="brand-logo">
              <Settings className="brand-icon spinning-icon" />
              <h2>
                DengueCast<span>.in</span>
              </h2>
            </div>
            <div className="system-status">
              <span className="dot pulse-dot"></span>
              <span>MODEL MATRIX ONLINE</span>
            </div>
          </div>

          <div className="sidebar-control-section">
            <div className="control-label">LOCATOR NODE</div>
            <div className="select-container">
              <MapPin className="select-icon" />
              <select
                value={selectedDistrict}
                onChange={(e) => setSelectedDistrict(e.target.value)}
                disabled={districts.length === 0}
                className="premium-select"
              >
                {districts.length === 0 && <option>Connecting matrix...</option>}
                {districts.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {prediction && (
            <div className="sidebar-metrics">
              <div className="sidebar-metric-box">
                <div className="metric-header">
                  {getRiskIcon(prediction.risk_level)}
                  <span>HAZARD INDEX</span>
                </div>
                <div
                  className="metric-val"
                  style={{ color: getRiskColor(prediction.risk_level) }}
                >
                  {prediction.risk_level.toUpperCase()}
                </div>
                <div className="metric-footer">
                  Based on LSTM & XGBoost predictions
                </div>
              </div>

              <div className="sidebar-metric-box font-medium">
                <div className="metric-header">
                  <Thermometer className="metric-icon text-orange" />
                  <span>ENVIRONMENTAL HYGROMETRY</span>
                </div>
                <div className="climate-progress-list">
                  <div className="progress-item">
                    <div className="prog-labels">
                      <span>Temp</span>
                      <span>{prediction.climate?.temperature.toFixed(1)}°C</span>
                    </div>
                    <div className="prog-track">
                      <div
                        className="prog-bar bg-orange"
                        style={{
                          width: `${Math.min(100, ((prediction.climate?.temperature ?? 0) / 45) * 100)}%`,
                        }}
                      ></div>
                    </div>
                  </div>

                  <div className="progress-item">
                    <div className="prog-labels">
                      <span>Rainfall</span>
                      <span>{prediction.climate?.rainfall.toFixed(0)}mm</span>
                    </div>
                    <div className="prog-track">
                      <div
                        className="prog-bar bg-blue"
                        style={{
                          width: `${Math.min(100, ((prediction.climate?.rainfall ?? 0) / 300) * 100)}%`,
                        }}
                      ></div>
                    </div>
                  </div>

                  <div className="progress-item">
                    <div className="prog-labels">
                      <span>NDVI Index</span>
                      <span>{prediction.climate?.ndvi.toFixed(2)}</span>
                    </div>
                    <div className="prog-track">
                      <div
                        className="prog-bar bg-emerald"
                        style={{
                          width: `${Math.min(100, ((prediction.climate?.ndvi ?? 0) / 0.8) * 100)}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </aside>

        {/* Main */}
        <main className="main-panel">
          <header className="top-navbar">
            <div className="panel-headline">
              <h1>Epidemiological Operations Center</h1>
              <p>
                Predictive vector analysis and outbreak modeling for Indian
                districts
              </p>
            </div>
            <div className="current-run-info">
              <span className="run-tag">DB RUN: 104-B</span>
              <span className="run-date">
                {prediction ? prediction.history_week_start : "LOADING..."}
              </span>
            </div>
          </header>

          {error && <div className="modern-error-banner">{error}</div>}

          {loading ? (
            <div className="modern-loader">
              <Loader2 className="loading-spinner" />
              <p>Recalibrating ensemble forecasts...</p>
            </div>
          ) : prediction ? (
            <div className="dashboard-grid-layout">
              {/* Map */}
              <div className="card map-card-large">
                <div className="card-header-modern">
                  <div className="card-title">
                    <Compass className="card-icon" />
                    <h3>Advanced Geospatial Analysis & Risk Mapping</h3>
                  </div>
                  <div className="card-badge">MULTI-LAYER SATELLITE</div>
                </div>
                <ErrorBoundary>
                  <EnhancedMap
                    center={districtCoords}
                    zoom={mapZoom}
                    hotspots={hotspots}
                    prediction={prediction}
                    selectedDistrict={selectedDistrict}
                    getRiskColor={getRiskColor}
                  />
                </ErrorBoundary>
              </div>

              {/* Quick forecast */}
              <div className="card forecast-highlight-card">
                <div className="card-header-modern">
                  <div className="card-title">
                    <ArrowUpRight className="card-icon" />
                    <h3>Weekly Outbreak Forecast</h3>
                  </div>
                </div>
                <div className="forecast-stat-container">
                  <div className="main-stat-display">
                    <span className="stat-label">PREDICTED INFECTIONS</span>
                    <div
                      className="large-stat-val"
                      style={{ color: getRiskColor(prediction.risk_level) }}
                    >
                      <AnimatedCounter
                        value={Math.round(prediction.predicted_cases_1w ?? 0)}
                      />
                    </div>
                  </div>
                  <div className="forecast-timeline-steps">
                    <div className="time-step">
                      <span className="time-lbl">WEEK 2</span>
                      <span className="time-val">
                        {Math.round(prediction.predicted_cases_2w ?? 0)}
                      </span>
                    </div>
                    <div className="time-step">
                      <span className="time-lbl">WEEK 3</span>
                      <span className="time-val">
                        {Math.round(prediction.predicted_cases_3w ?? 0)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Chart */}
              <div className="card chart-card-modern">
                <div className="card-header-modern">
                  <div className="card-title">
                    <Activity className="card-icon" />
                    <h3>Outbreak Path (3-Week Trend)</h3>
                  </div>
                </div>
                <div className="forecast-chart-wrapper">
                  <Line data={chartData!} options={chartOptions} />
                </div>
              </div>

              {/* Model breakdown */}
              <div className="card decision-engines-card">
                <div className="card-header-modern">
                  <div className="card-title">
                    <Disc className="card-icon" />
                    <h3>Multimodel Inference Engine Breakdown</h3>
                  </div>
                </div>
                <div className="engine-split-grid">
                  <div className="engine-metric-node">
                    <span className="engine-name">LSTM Network</span>
                    <span className="engine-number">
                      {prediction.lstm.toFixed(2)}
                    </span>
                    <div className="engine-track">
                      <div
                        className="engine-bar bg-blue"
                        style={{
                          width: `${Math.min(100, (prediction.lstm / 60) * 100)}%`,
                        }}
                      ></div>
                    </div>
                  </div>

                  <div className="engine-metric-node">
                    <span className="engine-name">XGBoost Regressor</span>
                    <span className="engine-number">
                      {prediction.xgb_reg.toFixed(2)}
                    </span>
                    <div className="engine-track">
                      <div
                        className="engine-bar bg-purple"
                        style={{
                          width: `${Math.min(100, (prediction.xgb_reg / 60) * 100)}%`,
                        }}
                      ></div>
                    </div>
                  </div>

                  <div className="engine-metric-node">
                    <span className="engine-name">XGBoost Classifier</span>
                    <span className="engine-number">
                      {prediction.xgb_clf === 1 ? "Outbreak" : "Normal"}
                    </span>
                    <div className="engine-track">
                      <div
                        className="engine-bar bg-rose"
                        style={{
                          width: prediction.xgb_clf === 1 ? "100%" : "15%",
                        }}
                      ></div>
                    </div>
                  </div>

                  <div className="engine-metric-node">
                    <span className="engine-name">Ensemble Average</span>
                    <span className="engine-number">
                      {prediction.ensemble.toFixed(2)}
                    </span>
                    <div className="engine-track">
                      <div
                        className="engine-bar bg-emerald"
                        style={{
                          width: `${Math.min(100, (prediction.ensemble / 60) * 100)}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-panel-state">
              <Compass className="spinning-icon big-icon" />
              <p>
                Select a target locator node in the sidebar to load
                epidemiological predictions.
              </p>
            </div>
          )}
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default App;
