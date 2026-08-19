interface BarDatum {
  label: string;
  value: number | null;
  highlight?: boolean;
}

const CHART_HEIGHT_PX = 112;

export function BarChart({ data, valueFormatter }: { data: BarDatum[]; valueFormatter?: (v: number) => string }) {
  const max = Math.max(0.0001, ...data.map((d) => d.value ?? 0));

  return (
    <div className="flex items-end gap-1" style={{ height: CHART_HEIGHT_PX + 20 }}>
      {data.map((d, i) => {
        const heightPx = d.value ? Math.max(3, (d.value / max) * CHART_HEIGHT_PX) : 2;
        return (
          <div key={i} className="group relative flex flex-1 flex-col items-center justify-end self-stretch">
            <div className="pointer-events-none absolute -top-8 z-10 hidden whitespace-nowrap rounded bg-stone-900 px-2 py-1 text-[11px] text-stone-50 group-hover:block">
              {d.label}: {d.value !== null ? (valueFormatter ? valueFormatter(d.value) : d.value) : "—"}
            </div>
            <div
              className={`w-full rounded-t-sm transition-colors ${
                d.highlight ? "bg-accent" : "bg-stone-300 group-hover:bg-stone-500"
              }`}
              style={{ height: `${heightPx}px` }}
            />
            <span className="mt-1.5 text-[10px] text-stone-400">{d.label}</span>
          </div>
        );
      })}
    </div>
  );
}
