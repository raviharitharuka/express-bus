"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, BusFront, LayoutDashboard, Route, Siren, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { DataSourceBadge } from "@/components/DataSource";

const NAV: { href: string; label: string; icon: LucideIcon; subtitle?: string; tooltip?: string }[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/optimization", label: "Optimization", icon: Route },
  { href: "/emergency", label: "Emergency Recovery", icon: Siren },
  {
    href: "/lotse",
    label: "Ask Lotse",
    icon: Bot,
    subtitle: "AI dispatch assistant",
    tooltip: "Ask Lotse – AI dispatch assistant",
  },
  { href: "/admin", label: "Admin", icon: SlidersHorizontal, subtitle: "Data and manual changes" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 z-10 flex shrink-0 flex-col border-b border-slate-200 bg-white md:h-screen md:w-64 md:border-r md:border-b-0">
      <div className="flex items-center gap-2.5 px-5 py-4 md:py-6">
        <div className="flex size-9 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-sm">
          <BusFront className="size-5" />
        </div>
        <div className="leading-tight">
          <div className="font-semibold text-slate-900">ExpressBus AI</div>
          <div className="text-xs text-slate-500">Nuremberg Operations</div>
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
        {NAV.map(({ href, label, icon: Icon, subtitle, tooltip }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              title={tooltip}
              className={`flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-indigo-50 text-indigo-700"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <Icon className={`size-4 shrink-0 ${active ? "text-indigo-600" : "text-slate-400"}`} />
              <span className="leading-tight">
                {label}
                {subtitle && (
                  <span className={`hidden text-xs font-normal md:block ${active ? "text-indigo-500" : "text-slate-400"}`}>
                    {subtitle}
                  </span>
                )}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto hidden p-4 md:block">
        <DataSourceBadge />
      </div>
    </aside>
  );
}
