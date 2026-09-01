/**
 * Plain-language labels for the model's feature columns. The backend (SHAP)
 * speaks in column names like `community_geo_density`; investigators and
 * judges watching a demo shouldn't have to parse that. The technical name
 * is kept alongside for anyone who wants to verify it (tooltip/title attr).
 */
export const FEATURE_LABELS = {
  amount_lost: { label: "Amount lost", tooltip: "How much money the victim reported losing." },
  hour_of_day: { label: "Time of day filed", tooltip: "The hour the complaint was filed." },
  bank_match: { label: "Same bank as withdrawal point", tooltip: "Whether the candidate location shares a bank with the complaint." },
  global_geo_density: { label: "General cash-out hotspot nearby", tooltip: "How often money has been withdrawn near this location historically, across all cases." },
  chain_depth: { label: "Money trail known so far", tooltip: "How many hops of the fund-flow chain are already traced." },
  recency_decay: { label: "How fresh the trail is", tooltip: "Recency-weighted signal since the last known movement of funds (a simplified Hawkes-process kernel)." },
  degree_centrality_global: { label: "Account's network activity", tooltip: "How connected this account is within the overall transaction graph." },
  community_size: { label: "Size of linked account network", tooltip: "Number of accounts discovered (via Louvain community detection) to be part of the same cluster." },
  local_betweenness: { label: "Role as a hub in this network", tooltip: "Whether this account sits in the middle of many fund-flow paths within its cluster." },
  community_num_complaints: { label: "Other complaints linked to this network", tooltip: "How many other complaints touch the same discovered account cluster -- the cross-complaint ring signal." },
  community_geo_density: { label: "This network's usual cash-out pattern nearby", tooltip: "How often accounts in the same discovered cluster have historically cashed out near this location." },
};

export function friendlyFeature(name) {
  return FEATURE_LABELS[name] || { label: name, tooltip: name };
}

/** Parses explain.py's "name=value (impact +0.123)" strings into structured parts. */
export function parseTopFeature(entry) {
  const match = entry.match(/^([a-zA-Z0-9_]+)=([^ ]+) \(impact ([+-][\d.]+)\)$/);
  if (!match) return { label: entry, value: "", impact: 0 };
  const [, name, value, impact] = match;
  return { ...friendlyFeature(name), technicalName: name, value, impact: parseFloat(impact) };
}

// Full plain-English sentences for each direction of each feature -- for a
// reader with no ML background, "community_geo_density=5.82 (impact +2.098)"
// says nothing. A complete sentence does. Chosen wording avoids numbers
// where the sign alone carries the meaning; the raw technical line is still
// available (title attr / expandable detail) for anyone who wants to verify it.
const FEATURE_SENTENCES = {
  amount_lost: {
    positive: "The amount involved matches a pattern this model has seen before in similar cash-outs.",
    negative: "The amount involved is somewhat unusual for this kind of cash-out.",
  },
  hour_of_day: {
    positive: "The complaint was filed at a time of day this network is typically active.",
    negative: "The complaint was filed outside this network's usual active hours.",
  },
  bank_match: {
    positive: "This location shares a bank with the complaint, a pattern seen in this network before.",
    negative: "This location uses a different bank than the complaint.",
  },
  global_geo_density: {
    positive: "This is a cash-out hotspot in general, across many unrelated cases.",
    negative: "This location doesn't see much cash-out activity in general.",
  },
  chain_depth: {
    positive: "A meaningful part of the money trail is already traced, making this a confident read.",
    negative: "Only an early part of the money trail is traced so far, so this is a less certain read.",
  },
  recency_decay: {
    positive: "The network's activity here is recent, not historical.",
    negative: "The network's activity here is comparatively old.",
  },
  degree_centrality_global: {
    positive: "This account is unusually well-connected across the wider transaction network.",
    negative: "This account has limited connections across the wider transaction network.",
  },
  community_size: {
    positive: "This is a large, multi-account network -- a hallmark of an organized ring rather than a one-off.",
    negative: "This is a small network, which usually means a weaker signal.",
  },
  local_betweenness: {
    positive: "This account sits at the center of the network, funneling money from several sources.",
    negative: "This account is on the edge of the network, not a central hub.",
  },
  community_num_complaints: {
    positive: "Multiple other victims have already reported ties to this same network.",
    negative: "Few other complaints are tied to this network so far.",
  },
  community_geo_density: {
    positive: "This network has a track record of cashing out near this exact location.",
    negative: "This network doesn't usually cash out near this location.",
  },
};

/**
 * Turns explain.py's raw SHAP strings into complete, readable sentences
 * ranked by how much each one mattered, for a reader with no ML background.
 */
export function explainToSentences(topFeatures) {
  return (topFeatures || []).map((entry) => {
    const parsed = parseTopFeature(entry);
    const direction = parsed.impact >= 0 ? "positive" : "negative";
    const sentences = FEATURE_SENTENCES[parsed.technicalName];
    const text = sentences ? sentences[direction] : `${parsed.label}: ${parsed.value}`;
    return { ...parsed, direction, text };
  });
}
