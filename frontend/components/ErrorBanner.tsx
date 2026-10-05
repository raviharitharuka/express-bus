import { CircleAlert } from "lucide-react";

export function ErrorBanner({ title, message }: { title: string; message: string }) {
  return (
    <div role="alert" className="flex gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      <CircleAlert className="mt-0.5 size-4 shrink-0" />
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-0.5 text-rose-600">{message}</p>
      </div>
    </div>
  );
}
