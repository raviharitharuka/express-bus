import type { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-20 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-indigo-50">
        <Icon className="size-6 text-indigo-600" />
      </div>
      <h2 className="mt-4 text-sm font-semibold text-slate-900">{title}</h2>
      <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>
      <button onClick={onAction} className="mt-5 text-sm font-medium text-indigo-600 hover:text-indigo-500">
        {actionLabel} →
      </button>
    </div>
  );
}
