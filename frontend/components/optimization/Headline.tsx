import { ArrowRight, CircleCheck, TriangleAlert } from "lucide-react";
import type { OptimizeResult } from "@/lib/types";

/** "E1", "E1 & E3", "E1, E2 & E3" */
function joinRoutes(routes: string[]) {
  return routes.length <= 1 ? routes.join("") : `${routes.slice(0, -1).join(", ")} & ${routes.at(-1)}`;
}

function drivers(n: number) {
  return `${n} additional driver${n === 1 ? "" : "s"}`;
}

/** The one-line answer to "can we launch express service without hiring?" */
export function Headline({ result }: { result: OptimizeResult }) {
  const launch = result.recommendations.filter((r) => result.recommended.includes(r.route));
  const others = result.recommendations.filter((r) => !result.recommended.includes(r.route));

  if (launch.length === 0) {
    const closest = [...result.recommendations].sort((a, b) => a.newDriversRequired - b.newDriversRequired)[0];
    return (
      <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900 shadow-sm">
        <p className="flex items-center gap-2 text-xs font-semibold tracking-wide text-amber-700 uppercase">
          <TriangleAlert className="size-4" /> Optimization result
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          No express line can launch without new drivers
        </h2>
        {closest && (
          <p className="mt-2 text-sm text-amber-800">
            Closest option: {closest.route} ({closest.name}) needs {drivers(closest.newDriversRequired)}.
          </p>
        )}
      </section>
    );
  }

  const gain = Math.round((result.optimizedUtilization - result.currentUtilization) * 10) / 10;

  return (
    <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-600 to-emerald-700 p-6 text-white shadow-md">
      <div className="pointer-events-none absolute -top-16 -right-16 size-56 rounded-full bg-white/10" />
      <div className="relative grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs font-semibold tracking-wide text-emerald-100 uppercase">
            <CircleCheck className="size-4" /> Optimization result · {result.date}
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
            Express line{launch.length > 1 ? "s" : ""} {joinRoutes(launch.map((r) => r.route))}: 0 additional drivers
            needed
          </h2>
          <ul className="mt-4 flex flex-wrap gap-2">
            {launch.map((r) => (
              <li key={r.route} className="rounded-lg bg-white/15 px-3 py-1.5 text-sm ring-1 ring-white/20">
                <span className="font-mono font-semibold">{r.route}</span>
                <span className="text-emerald-50">
                  {" "}
                  · {r.startStation} → {r.endStation} · {r.reason}
                </span>
              </li>
            ))}
          </ul>
          {others.length > 0 && (
            <p className="mt-3 text-sm text-emerald-100">
              Not recommended:{" "}
              {others.map((r) => `${r.route} needs ${drivers(r.newDriversRequired)}`).join("; ")}.
            </p>
          )}
        </div>

        <div className="rounded-xl bg-white/10 px-5 py-4 ring-1 ring-white/20 sm:w-fit">
          <p className="text-xs text-emerald-100">Driver utilization</p>
          <p className="mt-1 flex items-center gap-2 text-2xl font-semibold tabular-nums">
            {result.currentUtilization}% <ArrowRight className="size-5 text-emerald-200" /> {result.optimizedUtilization}%
          </p>
          <p className="mt-1 text-xs text-emerald-100">
            +{gain} pts · {result.totalIdleHoursUsed} idle h used
            {result.overtimeHoursUsed > 0 ? ` · ${result.overtimeHoursUsed} overtime h` : ""}
          </p>
        </div>
      </div>
    </section>
  );
}
