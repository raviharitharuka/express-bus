import { CircleAlert } from "lucide-react";

export function ErrorBanner({
  title,
  message,
  children,
}: {
  title: string;
  message: string;
  /** Optional actions, e.g. a retry button. */
  children?: React.ReactNode;
}) {
  return (
    <div role="alert" className="flex gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      <CircleAlert className="mt-0.5 size-4 shrink-0" />
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-0.5 text-rose-600">{message}</p>
        {children && <div className="mt-3 flex flex-wrap gap-2">{children}</div>}
      </div>
    </div>
  );
}

export function BannerButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-md bg-white px-2.5 py-1 text-xs font-medium text-rose-700 shadow-sm ring-1 ring-rose-200 hover:bg-rose-100"
    >
      {children}
    </button>
  );
}
