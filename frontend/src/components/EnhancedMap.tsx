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
import type { TransformedHotspot } from "../types/api";
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
            radius: 30,
            blur: 40,
            maxZoom: 17,
            max: 1.0,
            minOpacity: 0.4,
            gradient: {
              0.0: "#10b981",
              0.4: "#facc15",
              0.6: "#f59e0b",
              0.8: "#ef4444",
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
}

const EnhancedMap: FC<EnhancedMapProps> = ({
  center,
  zoom,
  hotspots,
  prediction,
  selectedDistrict,
  getRiskColor,
}) => {
  const [mapLayer, setMapLayer] = useState<string>("satellite");
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
          {(["satellite", "hybrid", "terrain", "dark"] as const).map(
            (layer) => (
              <button
                key={layer}
                className={`map-btn ${mapLayer === layer ? "active" : ""}`}
                onClick={() => setMapLayer(layer)}
              >
                {layer === "satellite"
                  ? "🛰️ Satellite"
                  : layer === "hybrid"
                    ? "🗺️ Hybrid"
                    : layer === "terrain"
                      ? "⛰️ Terrain"
                      : "🌙 Dark"}
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

          {showHeatmap && <HeatmapLayer points={heatmapPoints} />}

          {prediction && (
            <>
              <PulsingMarker
                center={center}
                radius={15}
                color={getRiskColor(prediction.risk_level)}
              />

              <CircleMarker
                center={center}
                radius={show3D ? 28 : 22}
                pathOptions={{
                  color: getRiskColor(prediction.risk_level),
                  fillColor: getRiskColor(prediction.risk_level),
                  fillOpacity: show3D ? 0.25 : 0.15,
                  weight: 2,
                  dashArray: "4, 4" as unknown as [number, number],
                }}
              >
                <Popup className="premium-popup">
                  <div className="pop-desc">
                    <h4>{selectedDistrict.toUpperCase()} CENTER</h4>
                    <div className="pop-divider"></div>
                    <p>
                      Weekly Forecast:{" "}
                      <strong>
                        {Math.round(prediction.predicted_cases_1w)} Cases
                      </strong>
                    </p>
                    <p>
                      Risk Level:{" "}
                      <span
                        style={{ color: getRiskColor(prediction.risk_level) }}
                      >
                        {prediction.risk_level.toUpperCase()}
                      </span>
                    </p>
                    <p>
                      Temperature:{" "}
                      <strong>
                        {prediction.climate?.temperature.toFixed(1) ?? "N/A"}°C
                      </strong>
                    </p>
                    <p>
                      Rainfall:{" "}
                      <strong>
                        {prediction.climate?.rainfall.toFixed(0) ?? "N/A"}mm
                      </strong>
                    </p>
                    <p>
                      NDVI:{" "}
                      <strong>
                        {prediction.climate?.ndvi.toFixed(2) ?? "N/A"}
                      </strong>
                    </p>
                  </div>
                </Popup>
              </CircleMarker>
            </>
          )}

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
      </div>
    </div>
  );
};

export default EnhancedMap;
