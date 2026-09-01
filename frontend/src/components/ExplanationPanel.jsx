import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { friendlyFeature } from "../utils/featureLabels";

// SHAP impact is a polarity value (pushes toward vs. away from this
// prediction), so it's colored as a DIVERGING pair, not a categorical set --
// blue for positive, red for negative, per the dataviz palette.
const POSITIVE = "#3987e5";
const NEGATIVE = "#e66767";

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="max-w-xs rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-xs">
      <p className="font-semibold text-ink-primary">{row.label}</p>
      <p className="mt-0.5 text-ink-muted">{row.tooltip}</p>
      <p className="mt-1 font-medium" style={{ color: row.impact >= 0 ? POSITIVE : NEGATIVE }}>
        Impact on confidence: {row.impact >= 0 ? "+" : ""}{row.impact.toFixed(3)}
      </p>
    </div>
  );
}

export default function ExplanationPanel({ explanation, height = 280 }) {
  if (!explanation) return null;

  const rows = Object.entries(explanation.shap_values)
    .map(([name, impact]) => ({ name, ...friendlyFeature(name), impact }))
    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
    .slice(0, 8);

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2c2c2a" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11, fill: "#898781" }} stroke="#383835" />
          <YAxis type="category" dataKey="label" width={190} tick={{ fontSize: 12, fill: "#c3c2b7" }} stroke="#383835" />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
            {rows.map((row) => (
              <Cell key={row.name} fill={row.impact >= 0 ? POSITIVE : NEGATIVE} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 flex items-center gap-4 text-xs text-ink-muted">
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: POSITIVE }} /> Pushes toward this location</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: NEGATIVE }} /> Pushes away from it</span>
      </div>
    </div>
  );
}
