import { useState, useEffect, useMemo, type FC } from "react";
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
  Search,
  Info,
  Menu,
  X,
} from "lucide-react";
import EnhancedMap from "./components/EnhancedMap";
import ErrorBoundary from "./components/ErrorBoundary";
import LandingPage from "./components/LandingPage";
import InfoTooltip from "./components/Tooltip";
import { SkeletonMap, SkeletonMetric, SkeletonChart } from "./components/Skeleton";
import type {
  PredictionResponse,
  HotspotData,
  TransformedHotspot,
  CoordinateResponse,
  StateData,
} from "./types/api";

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler,
);

const API_URL = "/api";

const AnimatedCounter: FC<{ value: number; duration?: number }> = ({
  value, duration = 1000,
}) => {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const end = Math.max(0, Math.round(value));
    if (end === 0) { setCount(0); return; }
    let startTs: number | null = null;
    let frameId: number;
    const step = (ts: number) => {
      if (!startTs) startTs = ts;
      const progress = Math.min((ts - startTs) / duration, 1);
      const eased = progress === 1 ? 1 : 1 - 2 ** (-10 * progress);
      setCount(Math.floor(eased * end));
      if (progress < 1) frameId = requestAnimationFrame(step);
      else setCount(end);
    };
    frameId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameId);
  }, [value, duration]);
  return <span>{count.toLocaleString()}</span>;
};

function getRiskColor(level?: string): string {
  switch (level?.toLowerCase()) {
    case "low": return "#10b981";
    case "medium": return "#f59e0b";
    case "high": return "#f43f5e";
    default: return "#3b82f6";
  }
}
function getRiskBg(level?: string): string {
  switch (level?.toLowerCase()) {
    case "low": return "rgba(16,185,129,0.08)";
    case "medium": return "rgba(245,158,11,0.08)";
    case "high": return "rgba(244,63,94,0.08)";
    default: return "rgba(59,130,246,0.08)";
  }
}
function getRiskIcon(level?: string) {
  switch (level?.toLowerCase()) {
    case "low": return <CheckCircle className="risk-header-icon text-emerald" />;
    case "medium": return <AlertTriangle className="risk-header-icon text-amber" />;
    case "high": return <ShieldAlert className="risk-header-icon text-rose" />;
    default: return <Activity className="risk-header-icon text-blue" />;
  }
}

const modelInfo: Record<string, { name: string; desc: string; key: string }> = {
  lstm: {
    name: "LSTM Network",
    desc: "Recurrent neural network that learns from 10-week rolling sequences. Captures seasonal patterns, lag effects, and temporal dependencies in dengue transmission.",
    key: "lstm",
  },
  xgb: {
    name: "XGBoost Regressor",
    desc: "Gradient-boosted decision tree ensemble. Handles non-linear feature interactions and provides robust point forecasts from the 17-dimensional feature space.",
    key: "xgb_reg",
  },
  ensemble: {
    name: "Ensemble Average",
    desc: "Weighted blend of XGBoost and LSTM predictions. The ensemble weight is optimized via grid search on validation data to minimize RMSE.",
    key: "ensemble",
  },
};

// ── App ──────────────────────────────────────────────────────────

const App: FC = () => {
  const [view, setView] = useState<"landing" | "dashboard">("landing");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Data state
  const [states, setStates] = useState<StateData[]>([]);
  const [selectedState, setSelectedState] = useState("");
  const [selectedDistrict, setSelectedDistrict] = useState("");
  const [districtSearch, setDistrictSearch] = useState("");
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Map state
  const [districtCoords, setDistrictCoords] = useState<[number, number]>([20.5937, 78.9629]);
  const [coordsCache, setCoordsCache] = useState<Record<string, [number, number]>>({});
  const [mapZoom, setMapZoom] = useState(5);
  const [hotspots, setHotspots] = useState<TransformedHotspot[]>([]);

  // Derived: filtered districts for current state + search
  const currentDistricts = useMemo(() => {
    const s = states.find((s) => s.state === selectedState);
    if (!s) return [];
    const q = districtSearch.toLowerCase();
    if (!q) return s.districts;
    return s.districts.filter((d) => d.toLowerCase().includes(q));
  }, [states, selectedState, districtSearch]);

  const fetchStates = async () => {
    try {
      const res = await axios.get<{ states: StateData[] }>(`${API_URL}/states`);
      const list = res.data.states;
      setStates(list);
      if (list.length > 0) {
        setSelectedState(list[0].state);
        if (list[0].districts.length > 0) {
          setSelectedDistrict(list[0].districts[0]);
        }
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
        hotspots: HotspotData[]; total_hotspots: number;
      }>(`${API_URL}/hotspots`, { params: { district } });

      const transformedHotspots: TransformedHotspot[] = hotspotsRes.data.hotspots.map(
        (h: HotspotData) => ({
          id: h.id,
          name: h.name,
          coords: [h.lat, h.lon] as [number, number],
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

  // Initialize data on first dashboard mount
  useEffect(() => {
    if (view === "dashboard") {
      fetchStates();
    }
  }, [view]);

  // Re-fetch when district changes
  useEffect(() => {
    if (view === "dashboard" && selectedDistrict) {
      fetchCoordinates(selectedDistrict).then(() => {
        fetchPrediction(selectedDistrict);
      });
    }
  }, [selectedDistrict, view]);

  const chartData: ChartData<"line"> | null = prediction
    ? {
        labels: [
          prediction.history_week_start || "History",
          prediction.forecast_week_1 || "Week 1",
          prediction.forecast_week_2 || "Week 2",
          prediction.forecast_week_3 || "Week 3",
        ],
        datasets: [{
          label: "Predicted Vector Density (Weekly cases)",
          data: [
            prediction.climate?.cases || 0,
            prediction.predicted_cases_1w ?? 0,
            prediction.predicted_cases_2w ?? 0,
            prediction.predicted_cases_3w ?? 0,
          ],
          borderColor: getRiskColor(prediction.risk_level),
          backgroundColor: (context) => {
            const { ctx, chartArea } = context.chart;
            if (!chartArea) return "transparent";
            const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
            g.addColorStop(0, getRiskBg(prediction.risk_level));
            g.addColorStop(1, "rgba(0,0,0,0)");
            return g;
          },
          tension: 0.4,
          fill: true,
          pointBackgroundColor: getRiskColor(prediction.risk_level),
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 7,
          borderWidth: 2,
        }],
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
        grid: { color: "rgba(255,255,255,0.04)", drawBorder: false },
        ticks: { color: "#94a3b8", font: { family: "Outfit", size: 11 } },
      },
      x: {
        grid: { display: false },
        ticks: { color: "#94a3b8", font: { family: "Outfit", size: 11 } },
      },
    },
  };

  if (view === "landing") {
    return <LandingPage onEnter={() => setView("dashboard")} />;
  }

  return (
    <ErrorBoundary>
      <div className="modern-layout">
        {/* Mobile hamburger */}
        <button
          className="hamburger"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label="Toggle sidebar"
        >
          {sidebarOpen ? <X size={22} /> : <Menu size={22} />}
        </button>

        {/* Overlay for mobile */}
        {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

        {/* ── Sidebar ── */}
        <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
          <div className="branding">
            <div className="brand-logo">
              <Settings className="brand-icon spinning-icon" />
              <h2>DengueCast<span>.in</span></h2>
            </div>
            <div className="system-status">
              <span className="dot pulse-dot" />
              <span>MODEL MATRIX ONLINE</span>
            </div>
          </div>

          <div className="sidebar-control-section">
            <div className="control-label">LOCATOR NODE</div>

            {/* State dropdown */}
            <div className="select-container">
              <MapPin className="select-icon" />
              <select
                value={selectedState}
                onChange={(e) => {
                  setSelectedState(e.target.value);
                  setDistrictSearch("");
                  const s = states.find((s) => s.state === e.target.value);
                  if (s && s.districts.length > 0) {
                    setSelectedDistrict(s.districts[0]);
                  }
                }}
                disabled={states.length === 0}
                className="premium-select"
              >
                {states.map((s) => (
                  <option key={s.state} value={s.state}>{s.state}</option>
                ))}
              </select>
            </div>

            {/* District search */}
            <div className="select-container">
              <Search className="select-icon" style={{ left: "0.75rem" }} />
              <input
                type="text"
                className="premium-select district-search"
                placeholder="Search district..."
                value={districtSearch}
                onChange={(e) => setDistrictSearch(e.target.value)}
              />
            </div>

            {/* District list */}
            <div className="select-container">
              <MapPin className="select-icon" />
              <div className="district-list-box">
                {currentDistricts.length === 0 ? (
                  <div className="district-list-empty">No districts found</div>
                ) : (
                  currentDistricts.map((d) => (
                    <div
                      key={d}
                      className={`district-list-item${d === selectedDistrict ? " district-list-item-active" : ""}`}
                      onClick={() => setSelectedDistrict(d)}
                    >
                      {d}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {prediction && (
            <div className="sidebar-metrics">
              <div className="sidebar-metric-box">
                <div className="metric-header">
                  {getRiskIcon(prediction.risk_level)}
                  <span>HAZARD INDEX</span>
                </div>
                <div className="metric-val" style={{ color: getRiskColor(prediction.risk_level) }}>
                  {prediction.risk_level.toUpperCase()}
                </div>
                <div className="metric-footer">Based on LSTM & XGBoost predictions</div>
              </div>

              <div className="sidebar-metric-box">
                <div className="metric-header">
                  <Thermometer className="metric-icon text-orange" />
                  <span>ENVIRONMENTAL HYGROMETRY</span>
                </div>
                <div className="climate-progress-list">
                  {(["temperature", "rainfall", "ndvi"] as const).map((k) => {
                    const labels = { temperature: "Temp", rainfall: "Rainfall", ndvi: "NDVI Index" };
                    const units = { temperature: "°C", rainfall: "mm", ndvi: "" };
                    const maxVals = { temperature: 45, rainfall: 300, ndvi: 0.8 };
                    const colors = { temperature: "bg-orange", rainfall: "bg-blue", ndvi: "bg-emerald" };
                    const val = prediction.climate?.[k] ?? 0;
                    return (
                      <div key={k} className="progress-item">
                        <div className="prog-labels">
                          <span>{labels[k]}</span>
                          <span>{k === "ndvi" ? val.toFixed(2) : k === "temperature" ? val.toFixed(1) : val.toFixed(0)}{units[k]}</span>
                        </div>
                        <div className="prog-track">
                          <div className={`prog-bar ${colors[k]}`} style={{ width: `${Math.min(100, (val / maxVals[k]) * 100)}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </aside>

        {/* ── Main Panel ── */}
        <main className="main-panel">
          <header className="top-navbar">
            <div className="panel-headline">
              <h1>Epidemiological Operations Center</h1>
              <p>Predictive vector analysis and outbreak modeling for Indian districts</p>
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
            <div className="dashboard-grid-layout dashboard-loading">
              <SkeletonMap />
              <SkeletonMetric />
              <SkeletonChart />
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

              {/* Forecast highlight */}
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
                    <div className="large-stat-val" style={{ color: getRiskColor(prediction.risk_level) }}>
                      <AnimatedCounter value={Math.round(prediction.predicted_cases_1w ?? 0)} />
                    </div>
                  </div>
                  <div className="forecast-timeline-steps">
                    <div className="time-step">
                      <span className="time-lbl">WEEK 2</span>
                      <span className="time-val">{Math.round(prediction.predicted_cases_2w ?? 0)}</span>
                    </div>
                    <div className="time-step">
                      <span className="time-lbl">WEEK 3</span>
                      <span className="time-val">{Math.round(prediction.predicted_cases_3w ?? 0)}</span>
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
                  {(["lstm", "xgb_reg", "xgb_clf", "ensemble"] as const).map((key) => {
                    const label =
                      key === "lstm" ? "LSTM Network"
                      : key === "xgb_reg" ? "XGBoost Regressor"
                      : key === "xgb_clf" ? "XGBoost Classifier"
                      : "Ensemble Average";
                    const value =
                      key === "xgb_clf"
                        ? prediction.xgb_clf === 1 ? "Outbreak" : "Normal"
                        : prediction[key].toFixed(2);
                    const barWidth =
                      key === "xgb_clf"
                        ? prediction.xgb_clf === 1 ? "100%" : "15%"
                        : `${Math.min(100, (prediction[key === "lstm" ? "lstm" : key === "xgb_reg" ? "xgb_reg" : "ensemble"] / 60) * 100)}%`;
                    const barColor =
                      key === "lstm" ? "bg-blue"
                      : key === "xgb_reg" ? "bg-purple"
                      : key === "xgb_clf" ? "bg-rose"
                      : "bg-emerald";
                    const info = key !== "xgb_clf" ? modelInfo[key === "xgb_reg" ? "xgb" : key === "lstm" ? "lstm" : "ensemble"] : null;
                    return (
                      <div key={key} className="engine-metric-node">
                        <span className="engine-name">
                          {label}
                          {info && (
                            <InfoTooltip content={
                              <div className="tp-content">
                                <strong>{info.name}</strong>
                                <p>{info.desc}</p>
                              </div>
                            }>
                              <Info size={13} className="engine-info-icon" />
                            </InfoTooltip>
                          )}
                        </span>
                        <span className="engine-number">{value}</span>
                        <div className="engine-track">
                          <div className={`engine-bar ${barColor}`} style={{ width: barWidth }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-panel-state">
              <Compass className="spinning-icon big-icon" />
              <p>Select a target locator node to load epidemiological predictions.</p>
            </div>
          )}
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default App;
