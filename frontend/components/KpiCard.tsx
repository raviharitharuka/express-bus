import type { LucideIcon } from "lucide-react";

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  progress,
  accent = "indigo",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  /** 0–100; renders a progress bar under the value. */
  progress?: number;
  accent?: "indigo" | "emerald" | "sky" | "violet" | "amber" | "rose";
}) {
  const accents = {
    indigo: { icon: "bg-indigo-50 text-indigo-600", bar: "bg-indigo-500" },
    emerald: { icon: "bg-emerald-50 text-emerald-600", bar: "bg-emerald-500" },
    sky: { icon: "bg-sky-50 text-sky-600", bar: "bg-sky-500" },
    violet: { icon: "bg-violet-50 text-violet-600", bar: "bg-violet-500" },
    amber: { icon: "bg-amber-50 text-amber-600", bar: "bg-amber-500" },
    rose: { icon: "bg-rose-50 text-rose-600", bar: "bg-rose-500" },
  }[accent];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <div className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${accents.icon}`}>
          <Icon className="size-4" />
        </div>
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</p>
      {progress !== undefined && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className={`h-full rounded-full ${accents.bar}`} style={{ width: `${progress}%` }} />
        </div>
      )}
      {hint && <p className="mt-2 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
