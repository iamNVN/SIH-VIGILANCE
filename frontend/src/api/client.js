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
  stats: (signal) => request("/stats", { signal }),
  listComplaints: (limit = 50, skip = 0, signal) => request(`/complaints?limit=${limit}&skip=${skip}`, { signal }),
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
  triggerNext: () => request("/stream/trigger-next", { method: "POST" }),
  resetStream: () => request("/stream/reset", { method: "POST" }),
};
