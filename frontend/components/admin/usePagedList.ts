"use client";

import { useCallback, useEffect, useState } from "react";
import type { AdminListQuery, AdminPage } from "@/lib/types";

export const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

/** One searchable, paginated admin list. `fetchPage` must be stable (e.g. an `api.*` function). */
export function usePagedList<T>(fetchPage: (query: AdminListQuery) => Promise<AdminPage<T>>) {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AdminPage<T> | null>(null);
  const [reloads, setReloads] = useState(0);
  // Which request finished last, and how. Loading = the current request hasn't finished yet.
  const key = `${q}\u0000${page}\u0000${reloads}`;
  const [done, setDone] = useState<{ key: string; error: string | null } | null>(null);
  const loading = done?.key !== key;
  const error = done?.key === key ? done.error : null;

  // Search after the user stops typing; a new search starts at page 1.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let current = true;
    fetchPage({ q, page, pageSize: PAGE_SIZE }).then(
      (result) => {
        if (!current) return;
        setData(result);
        setDone({ key, error: null });
      },
      (e: Error) => {
        if (current) setDone({ key, error: e.message });
      },
    );
    return () => {
      current = false;
    };
  }, [fetchPage, q, page, key]);

  const reload = useCallback(() => setReloads((n) => n + 1), []);

  /** Swap in the server's copy of an edited row without refetching the page. */
  const replaceItem = useCallback((matches: (item: T) => boolean, next: T) => {
    setData((d) => (d ? { ...d, items: d.items?.map((item) => (matches(item) ? next : item)) } : d));
  }, []);

  return { search, setSearch, q, page, setPage, data, error, loading, reload, replaceItem };
}
