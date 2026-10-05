// Loading placeholders shaped like the content they stand in for.

export function Skeleton({ className = "", style }: { className?: string; style?: React.CSSProperties }) {
  // Default rounding unless the caller sets its own (e.g. rounded-full for a donut).
  const rounding = className.includes("rounded") ? "" : "rounded-md";
  return <div aria-hidden className={`animate-pulse bg-slate-200/70 ${rounding} ${className}`} style={style} />;
}

export function KpiSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="size-8 rounded-lg" />
      </div>
      <Skeleton className="mt-3 h-8 w-20" />
      <Skeleton className="mt-4 h-1.5 w-full rounded-full" />
      <Skeleton className="mt-3 h-3 w-32" />
    </div>
  );
}

export function CardSkeleton({ className = "", body = "chart" }: { className?: string; body?: "chart" | "rows" }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-2 h-3 w-56" />
      {body === "chart" ? (
        <div className="mt-6 flex h-56 items-end gap-4 px-2">
          {[55, 80, 40, 70, 50].map((h, i) => (
            <Skeleton key={i} className="flex-1 rounded-t-md rounded-b-none" style={{ height: `${h}%` }} />
          ))}
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="size-7 shrink-0" />
              <Skeleton className="h-3 flex-1" />
              <Skeleton className="h-3 w-12" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
