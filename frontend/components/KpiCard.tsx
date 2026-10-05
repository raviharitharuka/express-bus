import type { LucideIcon } from "lucide-react";
import { tone as tones, type Tone } from "@/components/theme";

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  progress,
  tone = "brand",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  /** 0–100; renders a progress bar under the value. */
  progress?: number;
  tone?: Tone;
}) {
  const t = tones[tone];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <div className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${t.icon}`}>
          <Icon className="size-4" />
        </div>
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</p>
      {progress !== undefined && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className={`h-full rounded-full ${t.bar}`} style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} />
        </div>
      )}
      {hint && <p className="mt-2 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
