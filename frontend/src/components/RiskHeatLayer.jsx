import L from "leaflet";
import "leaflet.heat";
import { useEffect } from "react";
import { useMap } from "react-leaflet";

// A true GIS density surface (leaflet.heat), not discrete markers -- the
// PS's own "Risk Heatmap Dashboard" deliverable specifically asks for a
// heat layer, and CashOutMap.jsx's Circle/CircleMarker pins are a
// different, complementary view (exact ranked points), not this. Weight
// per point is the real predicted confidence for that case's top cash-out
// location -- a case the model is more sure about contributes more heat,
// not every point counted equally.
export default function RiskHeatLayer({ points }) {
  const map = useMap();

  useEffect(() => {
    if (!points || points.length === 0) return undefined;
    const heatPoints = points.map((p) => [p.lat, p.lon, Math.max(p.weight, 0.05)]);
    const layer = L.heatLayer(heatPoints, {
      radius: 34,
      blur: 26,
      maxZoom: 15,
      minOpacity: 0.35,
      // Same status-tier language as the rest of the app (URGENCY_COLOR in
      // CashOutMap.jsx) -- cool blue/green for low-density risk, warm
      // amber/red where cases cluster, not an arbitrary rainbow.
      gradient: { 0.2: "#3987e5", 0.45: "#199e70", 0.7: "#fab219", 1.0: "#e66767" },
    }).addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, points]);

  return null;
}
