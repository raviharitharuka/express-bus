"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { PencilLine } from "lucide-react";
import { adminStatusStore, api, refreshAdminStatus } from "@/lib/api";
import { tone } from "@/components/theme";

/** Shown above every page while admin edits or emergency changes affect the results. */
export function OverridesBanner() {
  const status = useSyncExternalStore(adminStatusStore.subscribe, adminStatusStore.get, () => null);
  const pathname = usePathname();
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(refreshAdminStatus, [pathname]);

  const changes = status?.overridesActive ?? 0;
  if (changes <= 0) return null;

  async function reset() {
    setResetting(true);
    setError(null);
    try {
      await api.resetAdmin();
      window.location.reload(); // every number on the page was computed with the changes
    } catch (e) {
      setError((e as Error).message);
      setResetting(false);
    }
  }

  return (
    <div role="status" className={`mb-6 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border px-4 py-3 text-sm ${tone.warning.soft}`}>
      <PencilLine className="size-4 shrink-0" />
      <p>
        <span className="font-medium">
          {changes} manual change{changes === 1 ? "" : "s"} active,
        </span>{" "}
        results reflect them.
      </p>
      <span className="flex items-center gap-3">
        <button onClick={reset} disabled={resetting} className="font-medium underline underline-offset-2 hover:no-underline disabled:opacity-60">
          {resetting ? "Resetting…" : "Reset all changes"}
        </button>
        {pathname !== "/admin" && (
          <Link href="/admin#drivers" className="underline underline-offset-2 hover:no-underline">
            Review
          </Link>
        )}
      </span>
      {error && <p className="basis-full text-rose-700">{error}</p>}
    </div>
  );
}
