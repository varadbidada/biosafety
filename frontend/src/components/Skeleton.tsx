import type { FC } from "react";

interface SkeletonBoxProps {
  width?: string;
  height?: string;
  borderRadius?: string;
  style?: React.CSSProperties;
}

const SkeletonBox: FC<SkeletonBoxProps> = ({
  width = "100%",
  height = "1rem",
  borderRadius = "6px",
  style,
}) => (
  <div
    className="sk-shimmer"
    style={{ width, height, borderRadius, ...style }}
  />
);

export const SkeletonMap: FC = () => (
  <div className="sk-map">
    <SkeletonBox height="100%" />
  </div>
);

export const SkeletonChart: FC = () => (
  <div className="sk-card">
    <div className="sk-card-header">
      <SkeletonBox width="60%" height="1.2rem" />
    </div>
    <SkeletonBox height="200px" style={{ marginTop: "1rem" }} />
  </div>
);

export const SkeletonMetric: FC = () => (
  <div className="sk-card sk-card-small">
    <SkeletonBox width="40%" height="0.75rem" />
    <SkeletonBox width="80%" height="2.5rem" style={{ marginTop: "0.5rem" }} />
    <SkeletonBox width="50%" height="0.7rem" style={{ marginTop: "0.25rem" }} />
  </div>
);

export const SkeletonSidebar: FC = () => (
  <div className="sk-sidebar">
    <SkeletonBox width="70%" height="1.5rem" style={{ marginBottom: "2rem" }} />
    <SkeletonBox width="100%" height="2.5rem" />
    <SkeletonBox width="100%" height="2.5rem" style={{ marginTop: "0.5rem" }} />
    <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <SkeletonBox width="100%" height="6rem" />
      <SkeletonBox width="100%" height="8rem" />
    </div>
  </div>
);

export const SkeletonDashboard: FC = () => (
  <div className="sk-dashboard">
    <div className="sk-dashboard-left">
      <SkeletonMap />
      <div className="sk-dashboard-row">
        <SkeletonMetric />
        <SkeletonChart />
      </div>
    </div>
    <div className="sk-dashboard-right">
      <SkeletonBox width="100%" height="100%" borderRadius="8px" />
    </div>
  </div>
);

export default SkeletonBox;
