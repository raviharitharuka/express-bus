// One semantic palette for the whole app. Pick a tone by meaning, not by look:
//   brand    – primary actions and neutral metrics (indigo)
//   positive – feasible, available, resolved (emerald)
//   warning  – needs attention: new drivers needed, maintenance (amber)
//   critical – incidents and errors (rose)
//   info     – informational alerts only (sky)
//   ai       – Lotse and AI recommendations (indigo → violet)
//   neutral  – baselines and secondary values (slate)

export type Tone = "brand" | "positive" | "warning" | "critical" | "info" | "ai" | "neutral";

export const tone: Record<
  Tone,
  { icon: string; bar: string; badge: string; soft: string; text: string; dot: string }
> = {
  brand: {
    icon: "bg-indigo-50 text-indigo-600",
    bar: "bg-indigo-500",
    badge: "bg-indigo-50 text-indigo-700 ring-indigo-200",
    soft: "border-indigo-200 bg-indigo-50 text-indigo-800",
    text: "text-indigo-700",
    dot: "bg-indigo-500",
  },
  positive: {
    icon: "bg-emerald-50 text-emerald-600",
    bar: "bg-emerald-500",
    badge: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    soft: "border-emerald-200 bg-emerald-50 text-emerald-800",
    text: "text-emerald-700",
    dot: "bg-emerald-500",
  },
  warning: {
    icon: "bg-amber-50 text-amber-600",
    bar: "bg-amber-500",
    badge: "bg-amber-50 text-amber-800 ring-amber-200",
    soft: "border-amber-200 bg-amber-50 text-amber-800",
    text: "text-amber-700",
    dot: "bg-amber-400",
  },
  critical: {
    icon: "bg-rose-50 text-rose-600",
    bar: "bg-rose-500",
    badge: "bg-rose-50 text-rose-700 ring-rose-200",
    soft: "border-rose-200 bg-rose-50 text-rose-700",
    text: "text-rose-700",
    dot: "bg-rose-500",
  },
  info: {
    icon: "bg-sky-50 text-sky-600",
    bar: "bg-sky-500",
    badge: "bg-sky-50 text-sky-700 ring-sky-200",
    soft: "border-sky-200 bg-sky-50 text-sky-700",
    text: "text-sky-700",
    dot: "bg-sky-500",
  },
  ai: {
    icon: "bg-gradient-to-br from-indigo-600 to-violet-600 text-white",
    bar: "bg-violet-500",
    badge: "bg-violet-50 text-violet-700 ring-violet-200",
    soft: "border-violet-200 bg-violet-50 text-violet-800",
    text: "text-violet-700",
    dot: "bg-violet-500",
  },
  neutral: {
    icon: "bg-slate-100 text-slate-500",
    bar: "bg-slate-400",
    badge: "bg-slate-100 text-slate-700 ring-slate-200",
    soft: "border-slate-200 bg-slate-50 text-slate-700",
    text: "text-slate-600",
    dot: "bg-slate-400",
  },
};

/** Hex values for Recharts and SVG, matching the Tailwind tones above. */
export const chartColor = {
  brand: "#6366f1", // indigo-500
  positive: "#10b981", // emerald-500
  warning: "#f59e0b", // amber-500
  critical: "#f43f5e", // rose-500
  neutral: "#94a3b8", // slate-400
};

// Shared Recharts styling so every chart in the app looks the same.
export const tooltipStyle = {
  borderRadius: 8,
  border: "1px solid #e2e8f0",
  boxShadow: "0 4px 12px rgb(15 23 42 / 0.08)",
  fontSize: 12,
};
export const axisTick = { fill: "#64748b", fontSize: 12 };
export const axisTickMuted = { fill: "#94a3b8", fontSize: 12 };
export const gridStroke = "#f1f5f9";
export const cursorFill = "#f8fafc";
