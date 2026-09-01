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

export const api = {
  health: () => request("/health"),
  systemInfo: (signal) => request("/system/info", { signal }),
  stats: (signal) => request("/stats", { signal }),
  listComplaints: (limit = 50, skip = 0, q = "", signal) =>
    request(`/complaints?limit=${limit}&skip=${skip}${q ? `&q=${encodeURIComponent(q)}` : ""}`, { signal }),
  countComplaints: (q = "", signal) => request(`/complaints/count${q ? `?q=${encodeURIComponent(q)}` : ""}`, { signal }),
  getComplaint: (id, signal) => request(`/complaints/${id}`, { signal }),
  createComplaint: (payload) =>
    request("/complaints", { method: "POST", body: JSON.stringify(payload) }),
  predict: (id, signal) => request(`/predict/${id}`, { method: "POST", signal }),
  explain: (id, withdrawalPointId, signal) =>
    request(`/explain/${id}${withdrawalPointId ? `?withdrawal_point_id=${withdrawalPointId}` : ""}`, { signal }),
  related: (id, signal) => request(`/related/${id}`, { signal }),
  graph: (id, hops = 2, signal) => request(`/graph/${id}?hops=${hops}`, { signal }),
  brief: (id, signal) => request(`/brief/${id}`, { signal }),
  evaluation: (signal) => request("/evaluation", { signal }),
  rings: (limit = 50, signal) => request(`/rings?limit=${limit}`, { signal }),
  predictionsFeed: (limit = 40, signal) => request(`/feed/predictions?limit=${limit}`, { signal }),
  alertsFeed: (limit = 40, signal) => request(`/feed/alerts?limit=${limit}`, { signal }),
  triggerNext: () => request("/stream/trigger-next", { method: "POST" }),
  resetStream: () => request("/stream/reset", { method: "POST" }),
};
