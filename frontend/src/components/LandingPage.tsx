import { useState, useEffect, type FC } from "react";

interface StatItem {
  value: number;
  label: string;
  suffix?: string;
}

const stats: StatItem[] = [
  { value: 589, label: "Districts", suffix: "+" },
  { value: 35, label: "States / UTs" },
  { value: 4, label: "RMSE Score", suffix: ".2" },
];

const features = [
  {
    icon: "🤖",
    title: "ML Ensemble Engine",
    desc: "XGBoost + LSTM dual-model architecture blends regression and sequential learning for high-fidelity forecasts.",
  },
  {
    icon: "🛰️",
    title: "Multi-Layer Geospatial",
    desc: "4 satellite basemaps with heatmap overlays, hotspot clustering, and 3D marker visualization.",
  },
  {
    icon: "📊",
    title: "10-Week Temporal Windows",
    desc: "LSTM analyzes rolling 10-week sequences to capture seasonal patterns and outbreak trajectories.",
  },
  {
    icon: "⚡",
    title: "Real-Time Inference",
    desc: "Sub-second ensemble predictions served via REST API with rate limiting and structured logging.",
  },
];

function AnimatedStat({ stat, visible }: { stat: StatItem; visible: boolean }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!visible) return;
    const end = stat.value;
    if (end === 0) { setCount(0); return; }
    let startTs: number | null = null;
    let frameId: number;
    const step = (ts: number) => {
      if (!startTs) startTs = ts;
      const progress = Math.min((ts - startTs) / 1200, 1);
      const eased = progress === 1 ? 1 : 1 - 2 ** (-10 * progress);
      setCount(Math.floor(eased * end));
      if (progress < 1) frameId = requestAnimationFrame(step);
      else setCount(end);
    };
    frameId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameId);
  }, [visible, stat.value]);

  return (
    <div className="lp-stat">
      <span className="lp-stat-value">
        {count}
        {stat.suffix ?? "+"}
      </span>
      <span className="lp-stat-label">{stat.label}</span>
    </div>
  );
}

interface LandingPageProps {
  onEnter: () => void;
}

const LandingPage: FC<LandingPageProps> = ({ onEnter }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className={`lp-root ${visible ? "lp-visible" : ""}`}>
      <div className="lp-bg-grid" />

      <header className="lp-header">
        <div className="lp-brand">
          <div className="lp-brand-icon">🦟</div>
          <span className="lp-brand-text">DengueCast<span>.in</span></span>
        </div>
      </header>

      <main className="lp-main">
        <section className="lp-hero">
          <div className="lp-badge">AI-PREDICTIVE HEALTH INTELLIGENCE</div>
          <h1 className="lp-title">
            Dengue Outbreak<br />
            <span className="lp-gradient">Prediction System</span>
          </h1>
          <p className="lp-subtitle">
            Real-time ensemble machine learning forecasts for 589 Indian districts.
            Monitor, predict, and visualize dengue transmission risk across the country.
          </p>

          <div className="lp-stats-row">
            {stats.map((s) => (
              <AnimatedStat key={s.label} stat={s} visible={visible} />
            ))}
          </div>

          <button className="lp-cta" onClick={onEnter}>
            <span>Launch Dashboard</span>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </section>

        <section className="lp-features">
          {features.map((f) => (
            <div key={f.title} className="lp-feature-card">
              <span className="lp-feature-icon">{f.icon}</span>
              <h3 className="lp-feature-title">{f.title}</h3>
              <p className="lp-feature-desc">{f.desc}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="lp-footer">
        <span>DengueCast India v0.2.0</span>
        <span className="lp-footer-dot">·</span>
        <span>College Research Project</span>
        <span className="lp-footer-dot">·</span>
        <span>Synthetic Data Demo</span>
      </footer>
    </div>
  );
};

export default LandingPage;
