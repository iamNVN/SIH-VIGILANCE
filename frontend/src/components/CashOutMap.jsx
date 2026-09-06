import L from "leaflet";
import { Fragment, useEffect, useMemo } from "react";
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { ConfidenceBadge, UrgencyBadge } from "./Badges";

// Leaflet's default marker icon assets don't resolve correctly through
// Vite's bundler; this app only uses CircleMarker/Circle, so the default
// icon is never actually needed, but importing leaflet still probes for it.
delete L.Icon.Default.prototype._getIconUrl;

// Leaflet measures its container's size once at creation time. Inside a
// flex/grid layout (every map on this app), that measurement can happen
// before the layout has settled, so Leaflet permanently thinks the map is a
// tiny/zero-size box -- it loads exactly one tile and never asks for more,
// no matter how long you wait. A ResizeObserver + `invalidateSize()` is the
// standard fix -- but `invalidateSize()`'s default `pan: true` re-centers the
// view by the measured size delta, and a ResizeObserver firing several times
// while the layout is still settling (fonts loading, flex reflow) compounds
// that pan each time it fires. Verified: this is exactly what was pushing
// tiles and markers thousands of pixels below the visible container (in
// clean multiples of one tile-row height) -- not a rendering/screenshot
// quirk. `pan: false` stops the drift; the rAF debounce collapses the burst
// of resize events into one settle-triggered call instead of several.
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

// Urgency is a state, not an identity, so it wears the status palette
// (reserved meaning) rather than a categorical series color.
export const URGENCY_COLOR = { HIGH: "#e66767", MEDIUM: "#fab219", LOW: "#898781" };

// A fixed center+zoom13 only ever framed predictions[0] -- every other
// marker could land off-screen depending on how spread out that batch's
// cash-out points are. fitBounds derives the view from every point actually
// being shown, so "zoomed out to fit all the predictions" holds regardless
// of how many there are or how far apart.
function FitBounds({ predictions }) {
  const map = useMap();

  useEffect(() => {
    if (!predictions || predictions.length === 0) return;
    if (predictions.length === 1) {
      map.setView([predictions[0].lat, predictions[0].lon], 14, { animate: false });
      return;
    }
    const bounds = L.latLngBounds(predictions.map((p) => [p.lat, p.lon]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15, animate: false });
  }, [map, predictions]);

  return null;
}

export default function CashOutMap({ predictions, height = 420, hideLegend = false }) {
  const center = useMemo(() => {
    if (!predictions || predictions.length === 0) return [20.5937, 78.9629]; // India centroid fallback
    return [predictions[0].lat, predictions[0].lon];
  }, [predictions]);

  if (!predictions || predictions.length === 0) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-md border border-dashed border-white/10 text-sm text-ink-muted">
        No predictions yet.
      </div>
    );
  }

  return (
    <div className="dark-tiles relative overflow-hidden rounded-md border border-surface-border" style={{ height }}>
      <MapContainer center={center} zoom={13} style={{ height: "100%", width: "100%" }}>
        <MapResizeFix />
        <FitBounds predictions={predictions} />
        {/* Esri's public World_Dark_Gray tile services -- no API key, no
            rate-limit block (unlike OSM's volunteer server, which flags
            embedded apps) and no key-gate (unlike CartoDB's basemaps, which
            now silently return a 200 "API key required" placeholder image
            instead of a real tile -- verified by inspecting actual tile
            pixels, not just the HTTP status). Two layers: a muted base plus
            a separate labels/roads reference layer on top, per Esri's
            standard dark-canvas pairing. */}
        <TileLayer
          attribution="Esri, HERE, Garmin, &copy; OpenStreetMap contributors, and the GIS community"
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
          maxZoom={16}
        />
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
          maxZoom={16}
        />
        {predictions.map((p) => (
          <Fragment key={p.withdrawal_point_id}>
            <Circle
              center={[p.lat, p.lon]}
              radius={80}
              pathOptions={{ color: URGENCY_COLOR[p.urgency] || "#898781", fillOpacity: 0.1, weight: 1 }}
            />
            <CircleMarker
              center={[p.lat, p.lon]}
              radius={8 + (5 - p.rank) * 3}
              pathOptions={{
                color: "#1a1a19",
                weight: 2,
                fillColor: URGENCY_COLOR[p.urgency] || "#898781",
                fillOpacity: 0.9,
              }}
            >
              <Tooltip permanent direction="top" offset={[0, -6]} className="cashout-label">
                {Math.round(p.confidence * 100)}%
              </Tooltip>
              <Popup>
                <div className="min-w-[200px] space-y-1">
                  <p className="font-semibold">#{p.rank} · {p.name}</p>
                  <ConfidenceBadge confidence={p.confidence} compact />
                  <UrgencyBadge urgency={p.urgency} />
                  <p className="text-xs text-ink-muted">{p.explanation.narrative}</p>
                </div>
              </Popup>
            </CircleMarker>
          </Fragment>
        ))}
      </MapContainer>
      {!hideLegend && <MapLegend />}
    </div>
  );
}

// A floating control anchored inside the map itself (matches how real GIS
// tools place a legend), not a separate list living below it -- so it's
// visible on every map that uses this component (a case's own Cash-out Map
// tab, the case workspace's inline map), not just the one place a caller
// remembered to render a below-map list. Command Center's hotspots panel
// opts out (`hideLegend`) and renders `CashOutMapLegend` below the map
// instead -- that map is short and narrow enough that the floating box
// overlapped its own percentage labels.
function MapLegend() {
  const items = [
    { color: URGENCY_COLOR.HIGH, label: "High risk" },
    { color: URGENCY_COLOR.MEDIUM, label: "Medium risk" },
    { color: URGENCY_COLOR.LOW, label: "Low risk" },
  ];
  return (
    <div className="pointer-events-none absolute bottom-2 left-2 z-[1000] rounded-md border border-white/10 bg-[#161615]/90 px-2.5 py-2 text-[11px] text-ink-muted shadow-lg backdrop-blur-sm">
      <div className="space-y-1">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: item.color }} />
            {item.label}
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 border-t border-white/10 pt-1.5">
        <span className="id-tag rounded-sm bg-white/10 px-1 text-[10px] font-semibold text-ink-secondary">%</span>
        <span>share of cases picking this spot</span>
      </div>
    </div>
  );
}

// A below-map, horizontal presentation of the same legend -- for callers
// like Command Center's hotspots panel that opt out of the floating
// in-map version (`hideLegend`) because their map is too small/narrow for
// it not to overlap the map's own percentage labels.
export function CashOutMapLegend() {
  const items = [
    { color: URGENCY_COLOR.HIGH, label: "High risk" },
    { color: URGENCY_COLOR.MEDIUM, label: "Medium risk" },
    { color: URGENCY_COLOR.LOW, label: "Low risk" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-muted">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <span className="id-tag rounded-sm bg-white/10 px-1 text-[10px] font-semibold text-ink-secondary">%</span>
        of cases picking this spot
      </span>
    </div>
  );
}
