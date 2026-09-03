// A colored tick mark beside every section title -- a cheap, consistent way
// to give scanning eyes a second (non-text) channel to latch onto, and to
// tie a section back to its tab's identity color.
const BAR_COLOR = {
  "series-1": "bg-series-1",
  "series-7": "bg-series-7",
  "series-2": "bg-series-2",
  "series-6": "bg-series-6",
};

export default function SectionHeader({ color = "series-1", children, action }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h3 className="flex items-center text-sm font-semibold text-ink-primary">
        {children}
      </h3>
      {action}
    </div>
  );
}
