export interface ClimateData {
  rainfall: number;
  temperature: number;
  ndvi: number;
  cases: number;
  monsoon: number;
}

export interface HotspotData {
  id: number;
  name: string;
  district_ref: string;
  offset_lat: number;
  offset_lon: number;
  type: "cases" | "breeding" | "hospital";
  avg_cases: number;
  max_cases: number;
  std_cases: number;
  intensity: number;
  coords?: [number, number];
}

export interface PredictionResponse {
  district?: string;
  week_start?: string;
  history_week_start?: string;
  forecast_week_1?: string;
  forecast_week_2?: string;
  forecast_week_3?: string;
  predicted_cases_next_week: number;
  predicted_cases_1w?: number;
  predicted_cases_2w?: number;
  predicted_cases_3w?: number;
  risk_level: "low" | "medium" | "high";
  xgb_reg: number;
  xgb_clf: number;
  lstm: number;
  ensemble: number;
  climate: ClimateData;
}

export interface HotspotsResponse {
  district: string;
  center_cases: number;
  center_max: number;
  hotspots: HotspotData[];
  total_hotspots: number;
}

export interface DistrictOverview {
  district: string;
  avg_cases: number;
  max_cases: number;
  min_cases: number;
  risk_level: "low" | "medium" | "high";
  intensity: number;
}

export interface MapOverviewResponse {
  districts: DistrictOverview[];
  total_districts: number;
  latest_week: string;
}

export interface ModelMetrics {
  n_samples: number;
  mae: number;
  rmse: number;
  mape: number;
}

export interface ModelAccuracyResponse {
  district: string;
  horizon: string;
  metrics: Record<string, ModelMetrics>;
}

export interface DistrictListResponse {
  districts: string[];
}

export interface TransformedHotspot {
  id: number;
  name: string;
  coords: [number, number];
  type: string;
  cases: number;
  maxCases?: number;
  intensity: number;
  districtRef: string;
}

export interface CoordinateResponse {
  district: string;
  lat: number;
  lon: number;
}
