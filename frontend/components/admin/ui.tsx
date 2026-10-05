"use client";

import { useEffect } from "react";
import { ChevronLeft, ChevronRight, LoaderCircle, Search, X } from "lucide-react";
import { Skeleton } from "@/components/Skeleton";
import { PAGE_SIZE } from "./usePagedList";

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <label className="relative block w-full sm:w-72">
      <span className="sr-only">{placeholder}</span>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-slate-200 bg-white py-2 pr-3 pl-9 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 focus:outline-none"
      />
    </label>
  );
}

export function Pagination({
  page,
  total,
  onPage,
  disabled,
}: {
  page: number;
  total: number;
  onPage: (page: number) => void;
  disabled?: boolean;
}) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const first = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(total, page * PAGE_SIZE);
  const button =
    "inline-flex size-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
  return (
    <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-500">
      <span className="tabular-nums">
        {first}–{last} of {total}
      </span>
      <div className="flex items-center gap-2">
        <button className={button} aria-label="Previous page" disabled={disabled || page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft className="size-4" />
        </button>
        <span className="tabular-nums">
          Page {page} of {pages}
        </span>
        <button className={button} aria-label="Next page" disabled={disabled || page >= pages} onClick={() => onPage(page + 1)}>
          <ChevronRight className="size-4" />
        </button>
      </div>
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
  danger,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  /** Accessible name, e.g. "Overtime for D001". */
  label: string;
  disabled?: boolean;
  /** Red when on (e.g. "unavailable"), instead of indigo. */
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? (danger ? "bg-rose-500" : "bg-indigo-600") : "bg-slate-200"
      }`}
    >
      <span className={`inline-block size-4 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4.5" : "translate-x-0.5"}`} />
    </button>
  );
}

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  busy,
  error,
  danger,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  busy?: boolean;
  error?: string | null;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={() => !busy && onCancel()}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 id="confirm-title" className="text-base font-semibold text-slate-900">
            {title}
          </h2>
          <button onClick={onCancel} disabled={busy} aria-label="Close" className="text-slate-400 hover:text-slate-600 disabled:opacity-50">
            <X className="size-4" />
          </button>
        </div>
        <div className="mt-2 text-sm text-slate-600">{children}</div>
        {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={busy}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-70 ${
              danger ? "bg-rose-600 hover:bg-rose-500" : "bg-indigo-600 hover:bg-indigo-500"
            }`}
          >
            {busy && <LoaderCircle className="size-4 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export const th = "px-3 py-2 text-left text-xs font-medium tracking-wide text-slate-500 uppercase";
export const td = "px-3 py-2.5 text-sm text-slate-700";

/** Table frame: skeleton rows on first load, dimmed while refetching, message when empty. */
export function AdminTable({
  head,
  loading,
  hasData,
  empty,
  children,
}: {
  head: React.ReactNode;
  loading: boolean;
  hasData: boolean;
  empty: string | null;
  children: React.ReactNode;
}) {
  if (!hasData) {
    return (
      <div className="space-y-3 py-2" aria-busy="true">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }
  return (
    <div className={`overflow-x-auto transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
      <table className="min-w-full divide-y divide-slate-200">
        <thead>
          <tr>{head}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
      {empty && <p className="py-10 text-center text-sm text-slate-500">{empty}</p>}
    </div>
  );
}

export function EditedBadge() {
  return (
    <span className="ml-2 rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 ring-1 ring-amber-200 ring-inset">
      edited
    </span>
  );
}

export const show = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? "—" : v);
