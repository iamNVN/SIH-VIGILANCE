import L from "leaflet";
import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import RiskHeatLayer from "./RiskHeatLayer";

delete L.Icon.Default.prototype._getIconUrl;

// Same zero-size-container bug and fix as CashOutMap.jsx's MapResizeFix --
// see that file's docstring for why `pan:false` + the rAF debounce
// specifically. Duplicated rather than imported: this is a different map
// (heat surface, not markers) living in its own file, same as CashOutMap's
// own copy is not shared elsewhere in this codebase.
function MapResizeFix() {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    map.invalidateSize({ animate: false, pan: false });

    let frame = null;
    const observer = new ResizeObserver(() => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => map.invalidateSize({ animate: false, pan: false }));
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [map]);

  return null;
}

function FitBounds({ points }) {
  const map = useMap();

  useEffect(() => {
    if (!points || points.length === 0) return;
    if (points.length === 1) {
      map.setView([points[0].lat, points[0].lon], 12, { animate: false });
      return;
    }
    const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lon]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13, animate: false });
  }, [map, points]);

  return null;
}

export default function RiskHeatmapMap({ points, height = 640 }) {
  const center = useMemo(() => {
    if (!points || points.length === 0) return [20.5937, 78.9629]; // India centroid fallback
    return [points[0].lat, points[0].lon];
  }, [points]);

  if (!points || points.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-dashed border-white/10 text-sm text-ink-muted"
        style={{ height }}
      >
        No cases match these filters.
      </div>
    );
  }

  return (
    <div className="dark-tiles relative overflow-hidden rounded-md border border-surface-border" style={{ height }}>
      <MapContainer center={center} zoom={11} style={{ height: "100%", width: "100%" }}>
        <MapResizeFix />
        <FitBounds points={points} />
        <TileLayer
          attribution="Esri, HERE, Garmin, &copy; OpenStreetMap contributors, and the GIS community"
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
          maxZoom={16}
        />
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
          maxZoom={16}
        />
        <RiskHeatLayer points={points} />
      </MapContainer>
    </div>
  );
}
