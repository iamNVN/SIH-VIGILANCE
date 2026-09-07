const BASE_URL = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // no JSON body
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

function qs(params) {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export const api = {
  health: () => request("/health"),
  systemInfo: (signal) => request("/system/info", { signal }),
  // `city` scopes every one of these to an investigator's jurisdiction --
  // enforced server-side (see backend/app/api/*.py), not just a display
  // filter. `null`/omitted city (administrators) means unrestricted.
  stats: (city, signal) => request(`/stats${qs({ city })}`, { signal }),
  statsTimeseries: (days = 7, city, signal) => request(`/stats/timeseries${qs({ days, city })}`, { signal }),
  statsHotspots: (limit = 5, city, signal) => request(`/stats/hotspots${qs({ limit, city })}`, { signal }),
  statsHeatmap: (city, days, category, signal) => request(`/stats/heatmap${qs({ city, days, category })}`, { signal }),
  listComplaints: (limit = 50, skip = 0, q = "", city, signal, sort, status, revealed) =>
    request(`/complaints${qs({ limit, skip, q, city, sort, status, revealed })}`, { signal }),
  countComplaints: (q = "", city, signal, status, revealed) =>
    request(`/complaints/count${qs({ q, city, status, revealed })}`, { signal }),
  getComplaint: (id, signal) => request(`/complaints/${id}`, { signal }),
  createComplaint: (payload) =>
    request("/complaints", { method: "POST", body: JSON.stringify(payload) }),
  decideComplaint: (id, decision) =>
    request(`/complaints/${id}/decision`, { method: "POST", body: JSON.stringify({ decision }) }),
  predict: (id, signal) => request(`/predict/${id}`, { method: "POST", signal }),
  explain: (id, withdrawalPointId, signal) =>
    request(`/explain/${id}${withdrawalPointId ? `?withdrawal_point_id=${withdrawalPointId}` : ""}`, { signal }),
  related: (id, signal) => request(`/related/${id}`, { signal }),
  graph: (id, hops = 2, signal) => request(`/graph/${id}?hops=${hops}`, { signal }),
  brief: (id, signal) => request(`/brief/${id}`, { signal }),
  evaluation: (signal) => request("/evaluation", { signal }),
  rings: (limit = 50, city, signal) => request(`/rings${qs({ limit, city })}`, { signal }),
  ringDetail: (communityId, signal) => request(`/rings/${communityId}`, { signal }),
  predictionsFeed: (limit = 40, city, signal) => request(`/feed/predictions${qs({ limit, city })}`, { signal }),
  alertsFeed: (limit = 40, city, signal, sort) => request(`/feed/alerts${qs({ limit, city, sort })}`, { signal }),
  events: (city, limit = 20, signal, eventType) => request(`/events${qs({ city, limit, event_type: eventType })}`, { signal }),
  triggerNext: (city) => request(`/stream/trigger-next${qs({ city })}`, { method: "POST" }),
  resetStream: () => request("/stream/reset", { method: "POST" }),
  streamStatus: (city, signal) => request(`/stream/status${qs({ city })}`, { signal }),
  getInjectLiveCases: (signal) => request("/settings/inject-live-cases", { signal }),
  setInjectLiveCases: (enabled) =>
    request("/settings/inject-live-cases", { method: "POST", body: JSON.stringify({ enabled }) }),
  feedbackSummary: (signal) => request("/feedback/summary", { signal }),
  retrainStatus: (signal) => request("/feedback/retrain/status", { signal }),
  triggerRetrain: () => request("/feedback/retrain/trigger", { method: "POST" }),
};
