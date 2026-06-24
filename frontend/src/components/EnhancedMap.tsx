import { useEffect, useRef, useState, type FC } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMap,
  LayersControl,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { TransformedHotspot, StatePredictionData } from "../types/api";
import axios from "axios";

const { BaseLayer } = LayersControl;
const API_URL = "/api";

/* ── Sub-components ──────────────────────────────────────────── */

interface PulsingMarkerProps {
  center: [number, number];
  radius: number;
  color: string;
}

function PulsingMarker({ center, radius, color }: PulsingMarkerProps) {
  const mapRef = useMap();
  const markerRef = useRef<L.Marker | null>(null);

  useEffect(() => {
    if (!markerRef.current) {
      const pulsingIcon = L.divIcon({
        className: "pulsing-marker",
        html: `
          <div class="pulse-ring" style="
            width: ${radius * 4}px;
            height: ${radius * 4}px;
            background: ${color};
            border-radius: 50%;
            animation: pulse-animation 2s ease-out infinite;
            opacity: 0.6;
          "></div>
          <div class="pulse-dot" style="
            width: ${radius * 2}px;
            height: ${radius * 2}px;
            background: ${color};
            border-radius: 50%;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            box-shadow: 0 0 20px ${color};
          "></div>
        `,
        iconSize: [radius * 4, radius * 4] as [number, number],
        iconAnchor: [radius * 2, radius * 2] as [number, number],
      });

      markerRef.current = L.marker(center, { icon: pulsingIcon }).addTo(mapRef);
    }

    return () => {
      if (markerRef.current) {
        mapRef.removeLayer(markerRef.current);
        markerRef.current = null;
      }
    };
  }, [center, radius, color, mapRef]);

  return null;
}

/* ── Heatmap overlay (nationwide) ───────────────────────────── */

interface HeatPoint {
  lat: number;
  lng: number;
  intensity: number;
}

interface NationHeatPoint {
  district: string;
  lat: number;
  lon: number;
  risk_level: string;
  intensity: number;
  avg_cases: number;
}

interface HeatmapLayerProps {
  points: HeatPoint[];
}

function HeatmapLayer({ points }: HeatmapLayerProps) {
  const mapRef = useMap();
  const heatLayerRef = useRef<L.Layer | null>(null);

  useEffect(() => {
    import("leaflet.heat")
      .then(() => {
        if (heatLayerRef.current) {
          mapRef.removeLayer(heatLayerRef.current);
        }

        if (points.length > 0 && L.heatLayer) {
          const heatData: Array<[number, number, number]> = points.map(
            (p) => [p.lat, p.lng, Math.max(0.1, p.intensity || 0.5)] as [number, number, number],
          );

          heatLayerRef.current = L.heatLayer(heatData, {
            radius: 35,
            blur: 35,
            maxZoom: 17,
            max: 1.0,
            minOpacity: 0.55,
            gradient: {
              0.0: "#10b981",
              0.3: "#eab308",
              0.5: "#f59e0b",
              0.7: "#ef4444",
              1.0: "#dc2626",
            },
          }).addTo(mapRef);
        }
      })
      .catch((err: Error) => {
        console.warn("Heatmap plugin not loaded:", err);
      });

    return () => {
      if (heatLayerRef.current && mapRef.hasLayer(heatLayerRef.current)) {
        mapRef.removeLayer(heatLayerRef.current);
      }
    };
  }, [points, mapRef]);

  return null;
}

/* ── Map fly-to updater ──────────────────────────────────────── */

interface MapUpdaterProps {
  center: [number, number];
  zoom: number;
}

function MapUpdater({ center, zoom }: MapUpdaterProps) {
  const map = useMap();

  useEffect(() => {
    map.flyTo(center, zoom, {
      animate: true,
      duration: 2.2,
      easeLinearity: 0.2,
    });
  }, [center, zoom, map]);

  return null;
}

/* ── State boundary choropleth layer ─────────────────────────── */

interface StateBoundaryLayerProps {
  statePredictions: StatePredictionData[];
  onStateSelect: (state: string) => void;
}

function StateBoundaryLayer({ statePredictions, onStateSelect }: StateBoundaryLayerProps) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);

  const intensityToColor = (intensity: number) => {
    if (intensity < 0.25) return "#10b981";
    if (intensity < 0.4) return "#eab308";
    if (intensity < 0.6) return "#f59e0b";
    if (intensity < 0.8) return "#ef4444";
    return "#dc2626";
  };

  useEffect(() => {
    axios.get(`${API_URL}/state_boundaries`)
      .then((res) => {
        if (layerRef.current) {
          map.removeLayer(layerRef.current);
        }

        const predMap = new Map(statePredictions.map((s) => [s.state, s]));

        layerRef.current = L.geoJSON(res.data as GeoJSON.FeatureCollection, {
          style: (feature) => {
            const name = feature?.properties?.name ?? "";
            const p = predMap.get(name);
            const intensity = p?.intensity ?? 0;
            return {
              fillColor: intensityToColor(intensity),
              fillOpacity: 0.18,
              color: "#ffffff",
              weight: 2,
            };
          },
          onEachFeature: (feature, layer) => {
            const name = feature.properties?.name ?? "";
            const p = predMap.get(name);
            layer.on("click", () => {
              onStateSelect(name);
              map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 9 });
            });
            layer.bindTooltip(
              `<b>${name}</b><br/>Total cases: ${p ? Math.round(p.total_predicted_cases) : "N/A"}`,
              { sticky: true },
            );
          },
        }).addTo(map);
      })
      .catch(() => {});

    return () => {
      if (layerRef.current && map.hasLayer(layerRef.current)) {
        map.removeLayer(layerRef.current);
      }
    };
  }, [statePredictions, map, onStateSelect]);

  return null;
}

/* ── Main component ──────────────────────────────────────────── */

interface EnhancedMapProps {
  center: [number, number];
  zoom: number;
  hotspots: TransformedHotspot[];
  prediction: {
    risk_level: string;
    predicted_cases_1w: number;
    climate?: {
      temperature: number;
      rainfall: number;
      ndvi: number;
    };
  } | null;
  selectedDistrict: string;
  getRiskColor: (level?: string) => string;
  statePredictions: StatePredictionData[];
  onStateSelect: (state: string) => void;
}

const EnhancedMap: FC<EnhancedMapProps> = ({
  center,
  zoom,
  hotspots,
  prediction,
  selectedDistrict,
  getRiskColor,
  statePredictions,
  onStateSelect,
}) => {
  const [mapLayer, setMapLayer] = useState<string>("dark");
  const [showHeatmap, setShowHeatmap] = useState<boolean>(false);
  const [show3D, setShow3D] = useState<boolean>(false);
  const [nationHeat, setNationHeat] = useState<NationHeatPoint[]>([]);

  useEffect(() => {
    axios.get<{ districts: NationHeatPoint[] }>(`${API_URL}/heatmap`)
      .then((res) => {
        if (res.data && res.data.districts) {
          setNationHeat(res.data.districts);
        }
      })
      .catch(() => {});
  }, []);

  const heatmapPoints: HeatPoint[] = showHeatmap && nationHeat.length > 0
    ? nationHeat.map((d) => ({
        lat: d.lat,
        lng: d.lon,
        intensity: d.intensity ?? 0.5,
      }))
    : [];

  return (
    <div className="enhanced-map-container">
      <div className="map-controls-panel">
        <div className="map-layer-selector">
          {(["dark", "hybrid", "terrain", "satellite"] as const).map(
            (layer) => (
              <button
                key={layer}
                className={`map-btn ${mapLayer === layer ? "active" : ""}`}
                onClick={() => setMapLayer(layer)}
              >
                {layer === "dark"
                  ? "🌙 Dark"
                  : layer === "hybrid"
                    ? "🗺️ Hybrid"
                    : layer === "terrain"
                      ? "⛰️ Terrain"
                      : "🛰️ Satellite"}
              </button>
            ),
          )}
        </div>

        <div className="map-overlay-controls">
          <label className="overlay-toggle">
            <input
              type="checkbox"
              checked={showHeatmap}
              onChange={(e) => setShowHeatmap(e.target.checked)}
            />
            <span>🔥 Heatmap</span>
          </label>
          <label className="overlay-toggle">
            <input
              type="checkbox"
              checked={show3D}
              onChange={(e) => setShow3D(e.target.checked)}
            />
            <span>📊 3D Markers</span>
          </label>
        </div>
      </div>

      <div className="map-view-wrapper">
        <MapContainer
          center={center}
          zoom={zoom}
          scrollWheelZoom={true}
          style={{ height: "100%", width: "100%" }}
          zoomControl={true}
        >
          <LayersControl position="topright">
            {mapLayer === "satellite" && (
              <BaseLayer checked name="Satellite">
                <TileLayer
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  attribution="&copy; Esri"
                  maxZoom={19}
                />
              </BaseLayer>
            )}
            {mapLayer === "hybrid" && (
              <BaseLayer checked name="Hybrid">
                <TileLayer
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  attribution="&copy; Esri"
                  maxZoom={19}
                />
                <TileLayer
                  url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png"
                  attribution="&copy; CARTO"
                  maxZoom={19}
                />
              </BaseLayer>
            )}
            {mapLayer === "terrain" && (
              <BaseLayer checked name="Terrain">
                <TileLayer
                  url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
                  attribution="&copy; OpenTopoMap"
                  maxZoom={17}
                />
              </BaseLayer>
            )}
            {mapLayer === "dark" && (
              <BaseLayer checked name="Dark">
                <TileLayer
                  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                  attribution="&copy; CARTO"
                  maxZoom={19}
                />
              </BaseLayer>
            )}
          </LayersControl>

          <MapUpdater center={center} zoom={zoom} />

          <StateBoundaryLayer statePredictions={statePredictions} onStateSelect={onStateSelect} />

          {showHeatmap && <HeatmapLayer points={heatmapPoints} />}

          {hotspots.map((hotspot) => (
            <CircleMarker
              key={hotspot.id}
              center={hotspot.coords}
              radius={
                show3D
                  ? 12 + Math.min(15, hotspot.cases / 2)
                  : 10 + Math.min(12, hotspot.cases / 3)
              }
              pathOptions={{
                color:
                  hotspot.type === "breeding"
                    ? "#3b82f6"
                    : hotspot.type === "hospital"
                      ? "#8b5cf6"
                      : getRiskColor(prediction?.risk_level),
                fillColor:
                  hotspot.type === "breeding"
                    ? "#3b82f6"
                    : hotspot.type === "hospital"
                      ? "#8b5cf6"
                      : getRiskColor(prediction?.risk_level),
                fillOpacity: show3D
                  ? 0.35 + (hotspot.intensity ?? 0) * 0.3
                  : 0.25 + (hotspot.intensity ?? 0) * 0.2,
                weight: 1.5,
              }}
            >
              <Popup className="premium-popup">
                <div className="pop-desc">
                  <h4>{hotspot.name}</h4>
                  <div className="pop-divider"></div>
                  <p>
                    Average Cases: <strong>{hotspot.cases}</strong>
                  </p>
                  {hotspot.maxCases != null && (
                    <p>
                      Peak Cases: <strong>{hotspot.maxCases}</strong>
                    </p>
                  )}
                  <p>
                    Type:{" "}
                    <span className="source-tag">
                      {hotspot.type.toUpperCase()}
                    </span>
                  </p>
                  {hotspot.intensity != null && (
                    <p>
                      Intensity:{" "}
                      <strong>{(hotspot.intensity * 100).toFixed(0)}%</strong>
                    </p>
                  )}
                  {hotspot.districtRef && (
                    <p
                      style={{
                        fontSize: "0.65rem",
                        marginTop: "0.25rem",
                        opacity: 0.7,
                      }}
                    >
                      Based on: {hotspot.districtRef}
                    </p>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* Legend */}
        <div className="map-legend">
          <div className="map-legend-title">Dengue Risk Index</div>
          <div className="map-legend-gradient" />
          <div className="map-legend-labels">
            <span>Low</span>
            <span>Moderate</span>
            <span>High</span>
            <span>Very High</span>
          </div>
          <div className="map-legend-note">
            0 &mdash; 25 &mdash; 50 &mdash; 75 &mdash; 100+ predicted cases (District heatmap &bull; State choropleth)
          </div>
        </div>
      </div>
    </div>
  );
};

export default EnhancedMap;
