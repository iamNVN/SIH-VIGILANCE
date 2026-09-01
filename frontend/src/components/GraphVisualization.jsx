import { useEffect, useMemo, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";

// Node color = identity (account role / withdrawal point) -- a fixed
// categorical assignment, never reassigned per-render. Whether a node sits
// on this case's traced chain is a SEPARATE channel (a ring around the
// node), not folded into the fill color, so both "what kind of node" and
// "is this part of the traced path" can be read at once.
const FILL = {
  mule: "#d95926", // series-2 orange
  victim: "#3987e5", // series-1 blue
  normal: "#6b6a66", // muted -- de-emphasized "other account"
  withdrawal_point: "#199e70", // series-3 aqua
};

const LINK_COLOR = { transfer: "rgba(137,135,129,0.35)", withdrawal: "rgba(25,158,112,0.45)" };

function fillFor(node) {
  if (node.node_kind === "withdrawal_point") return FILL.withdrawal_point;
  return FILL[node.account_type] || FILL.normal;
}

function labelFor(node) {
  if (node.node_kind === "withdrawal_point") return `${node.name || node.city + " withdrawal point"}`;
  const role = node.account_type ? `${node.account_type} account` : "account";
  return node.is_center ? `${role} — this case's traced account` : node.in_chain ? `${role} — on the traced path` : role;
}

function linkLabel(link) {
  const amount = `₹${Math.round(link.amount || 0).toLocaleString("en-IN")}`;
  const times = link.count > 1 ? ` across ${link.count} transactions` : "";
  return link.kind === "withdrawal" ? `Cash withdrawal, ${amount}${times}` : `Transfer, ${amount}${times}`;
}

export default function GraphVisualization({ graphData, height = 420 }) {
  const containerRef = useRef(null);
  const fgRef = useRef(null);

  const data = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    // Many parallel edges exist between the same two accounts (one per
    // historical transaction) -- drawn individually they're most of what
    // made this view unreadable. Collapsed into one link per (source,
    // target, kind) pair, with count/total kept for the tooltip.
    const merged = new Map();
    for (const e of graphData.edges) {
      const key = `${e.source}->${e.target}->${e.kind}`;
      const existing = merged.get(key);
      if (existing) {
        existing.count += 1;
        existing.amount += e.amount || 0;
      } else {
        merged.set(key, { ...e, count: 1 });
      }
    }
    return {
      nodes: graphData.nodes.map((n) => ({ ...n })),
      links: Array.from(merged.values()),
    };
  }, [graphData]);

  useEffect(() => {
    if (fgRef.current && data.nodes.length > 0) {
      setTimeout(() => fgRef.current.zoomToFit(400, 50), 300);
    }
  }, [data]);

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-md border border-dashed border-white/10 text-sm text-ink-muted">
        No graph data available for this case yet.
      </div>
    );
  }

  return (
    <div ref={containerRef} className="overflow-hidden rounded-md border border-surface-border" style={{ height }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={data}
        width={containerRef.current?.clientWidth || 600}
        height={height}
        backgroundColor="#1a1a19"
        nodeRelSize={5}
        nodeLabel={labelFor}
        linkLabel={linkLabel}
        linkColor={(l) => LINK_COLOR[l.kind] || LINK_COLOR.transfer}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkWidth={(l) => Math.min(1 + Math.log2(l.count || 1), 4)}
        dagMode="lr"
        dagLevelDistance={90}
        cooldownTicks={80}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const baseR = node.is_center ? 9 : node.node_kind === "withdrawal_point" ? 6.5 : node.in_chain ? 6.5 : 4.5;
          ctx.beginPath();
          ctx.arc(node.x, node.y, baseR, 0, 2 * Math.PI, false);
          ctx.fillStyle = fillFor(node);
          ctx.fill();

          if (node.in_chain || node.is_center) {
            ctx.lineWidth = (node.is_center ? 2.5 : 1.5) / globalScale;
            ctx.strokeStyle = node.is_center ? "#ffffff" : "rgba(255,255,255,0.7)";
            ctx.stroke();
          }
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          const baseR = node.is_center ? 9 : node.node_kind === "withdrawal_point" ? 6.5 : node.in_chain ? 6.5 : 4.5;
          ctx.beginPath();
          ctx.arc(node.x, node.y, baseR + 2, 0, 2 * Math.PI, false);
          ctx.fillStyle = color;
          ctx.fill();
        }}
      />
    </div>
  );
}

export function GraphLegend() {
  const items = [
    { color: FILL.victim, label: "Victim account" },
    { color: FILL.mule, label: "Mule account" },
    { color: FILL.normal, label: "Other account" },
    { color: FILL.withdrawal_point, label: "Withdrawal point" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-muted">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-full ring-2 ring-white/70" style={{ background: FILL.mule }} />
        Traced path for this case
      </span>
    </div>
  );
}
