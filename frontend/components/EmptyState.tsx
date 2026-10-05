import type { LucideIcon } from "lucide-react";
import { tone as tones, type Tone } from "@/components/theme";

// The action button matches the page's primary action: rose for incidents, indigo otherwise.
const BUTTON = {
  critical: "bg-rose-600 hover:bg-rose-500 focus-visible:ring-rose-500",
  default: "bg-indigo-600 hover:bg-indigo-500 focus-visible:ring-indigo-500",
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  tone = "brand",
  compact = false,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  tone?: Tone;
  /** Smaller variant for use inside a card. */
  compact?: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${
        compact ? "py-10" : "rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16"
      }`}
    >
      <div className={`flex items-center justify-center rounded-full ring-8 ring-slate-50 ${tones[tone].icon} ${compact ? "size-10" : "size-14"}`}>
        <Icon className={compact ? "size-5" : "size-7"} />
      </div>
      <h2 className={`font-semibold text-slate-900 ${compact ? "mt-4 text-sm" : "mt-5 text-base"}`}>{title}</h2>
      <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className={`mt-6 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none ${tone === "critical" ? BUTTON.critical : BUTTON.default}`}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
