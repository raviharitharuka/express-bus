import type { LucideIcon } from "lucide-react";
import { tone as tones, type Tone } from "@/components/theme";

export function StatusBadge({ tone, icon: Icon, children }: { tone: Tone; icon?: LucideIcon; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset ${tones[tone].badge}`}
    >
      {Icon && <Icon className="size-3.5" />}
      {children}
    </span>
  );
}
