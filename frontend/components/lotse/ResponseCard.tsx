"use client";

import { useState } from "react";
import { Bot, Braces } from "lucide-react";
import type { LotseResult } from "@/lib/types";

function confidenceTone(confidence: number) {
  if (confidence >= 80) return { bar: "bg-emerald-500", text: "text-emerald-700" };
  if (confidence >= 50) return { bar: "bg-amber-500", text: "text-amber-700" };
  return { bar: "bg-rose-500", text: "text-rose-700" };
}

export function ResponseCard({
  result,
  onFollowUp,
  disabled,
}: {
  result: LotseResult;
  onFollowUp: (question: string) => void;
  disabled: boolean;
}) {
  const [showJson, setShowJson] = useState(false);
  const tone = confidenceTone(result.confidence);

  return (
    <div className="w-full max-w-2xl overflow-hidden rounded-2xl rounded-tl-sm border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-2.5">
        <span className="flex items-center gap-1.5 text-xs font-medium whitespace-nowrap text-indigo-700">
          <Bot className="size-3.5" /> Lotse
        </span>
        <div className="flex items-center gap-2" title="Model confidence">
          <div className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-slate-100 sm:block">
            <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${result.confidence}%` }} />
          </div>
          <span className={`text-xs font-medium whitespace-nowrap tabular-nums ${tone.text}`}>{result.confidence}% confident</span>
        </div>
      </div>

      <p className="px-4 py-3 text-sm leading-relaxed text-slate-800">{result.answer}</p>

      {result.followUps.length > 0 && (
        <div className="border-t border-slate-100 px-4 py-3">
          <p className="mb-2 text-xs font-medium text-slate-500">Suggested follow-ups</p>
          <div className="flex flex-wrap gap-2">
            {result.followUps.map((q) => (
              <button
                key={q}
                onClick={() => onFollowUp(q)}
                disabled={disabled}
                className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-left text-xs text-indigo-700 transition-colors hover:border-indigo-200 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-2">
        <button
          onClick={() => setShowJson((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700"
        >
          <Braces className="size-3.5" /> {showJson ? "Hide" : "View"} raw response
        </button>
        {showJson && (
          <pre className="mt-2 max-h-64 overflow-auto rounded-lg break-words whitespace-pre-wrap bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
