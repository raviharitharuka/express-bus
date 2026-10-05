"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, CircleAlert, Loader2, RotateCw, SendHorizontal, User } from "lucide-react";
import { api } from "@/lib/api";
import type { LotseResult } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { ResponseCard } from "./ResponseCard";

const SUGGESTIONS = [
  "Can we launch a new route tomorrow?",
  "Which drivers are idle?",
  "Bus B021 broke down.",
  "Which station needs more buses?",
];

type Message =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; question: string; status: "loading" }
  | { id: number; role: "assistant"; question: string; status: "done"; result: LotseResult }
  | { id: number; role: "assistant"; question: string; status: "error"; error: string };

export function LotseChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const nextId = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const busy = messages.some((m) => m.role === "assistant" && m.status === "loading");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function answer(id: number, question: string) {
    try {
      const result = await api.askLotse(question);
      setMessages((ms) => ms.map((m) => (m.id === id ? { id, role: "assistant", question, status: "done", result } : m)));
    } catch (e) {
      const error = (e as Error).message;
      setMessages((ms) => ms.map((m) => (m.id === id ? { id, role: "assistant", question, status: "error", error } : m)));
    }
  }

  function ask(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    const userId = nextId.current++;
    const replyId = nextId.current++;
    setMessages((ms) => [
      ...ms,
      { id: userId, role: "user", text: question },
      { id: replyId, role: "assistant", question, status: "loading" },
    ]);
    setInput("");
    answer(replyId, question);
  }

  function retry(id: number, question: string) {
    setMessages((ms) => ms.map((m) => (m.id === id ? { id, role: "assistant", question, status: "loading" } : m)));
    answer(id, question);
  }

  return (
    <>
      <PageHeader title="Ask Lotse" description="Ask about idle capacity, new express routes and disruptions." />

      <div className="flex h-[calc(100dvh-17rem)] min-h-[28rem] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm md:h-[calc(100dvh-12rem)]">
        <header className="flex items-center gap-3 border-b border-slate-100 px-4 py-3 sm:px-6">
          <BotAvatar />
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              Ask Lotse
              <span className="flex items-center gap-1 text-xs font-normal text-emerald-700">
                <span className="size-2 rounded-full bg-emerald-500 ring-2 ring-emerald-100" /> online
              </span>
            </h2>
            <p className="text-xs text-slate-500">AI dispatch assistant</p>
          </div>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          {messages.length === 0 ? (
            <Welcome onPick={ask} />
          ) : (
            <div className="space-y-5">
              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="flex justify-end gap-3">
                    <p className="max-w-[80%] rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-sm">
                      {m.text}
                    </p>
                    <UserAvatar />
                  </div>
                ) : (
                  <div key={m.id} className="flex gap-3">
                    <BotAvatar />
                    {m.status === "loading" && (
                      <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                        <Loader2 className="size-4 animate-spin text-indigo-500" /> Lotse is thinking...
                      </div>
                    )}
                    {m.status === "done" && <ResponseCard result={m.result} onFollowUp={ask} disabled={busy} />}
                    {m.status === "error" && (
                      <div className="flex max-w-2xl items-start gap-3 rounded-2xl rounded-tl-sm border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                        <CircleAlert className="mt-0.5 size-4 shrink-0" />
                        <div>
                          <p className="font-medium">Lotse couldn&apos;t answer that</p>
                          <p className="mt-0.5 text-rose-600">{m.error}</p>
                          <button
                            onClick={() => retry(m.id, m.question)}
                            disabled={busy}
                            className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-rose-700 hover:text-rose-800 disabled:opacity-60"
                          >
                            <RotateCw className="size-3.5" /> Try again
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ),
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="border-t border-slate-100 bg-white p-3 sm:p-4">
          {messages.length > 0 && (
            <div className="mb-3 flex gap-2 overflow-x-auto pb-1" aria-label="Suggested prompts">
              {SUGGESTIONS.map((s) => (
                <Chip key={s} label={s} onClick={() => ask(s)} disabled={busy} />
              ))}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
            className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 py-1.5 pr-1.5 pl-4 focus-within:border-indigo-300 focus-within:bg-white focus-within:ring-2 focus-within:ring-indigo-100"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Lotse about idle capacity, new routes or disruptions..."
              aria-label="Ask Lotse"
              className="min-w-0 flex-1 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              aria-label="Send"
              className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {busy ? <Loader2 className="size-4 animate-spin" /> : <SendHorizontal className="size-4" />}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}

function Welcome({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="flex size-14 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-md">
        <Bot className="size-7" />
      </div>
      <h2 className="mt-4 max-w-md text-base font-semibold text-slate-900">
        Hi, I&apos;m Lotse, your AI dispatch assistant. What would you like to know?
      </h2>
      <p className="mt-6 text-xs font-medium text-slate-500">Suggested prompts</p>
      <div className="mt-2 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition-colors hover:border-indigo-200 hover:bg-indigo-50/50 hover:text-indigo-700"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function Chip({ label, onClick, disabled }: { label: string; onClick: () => void; disabled: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs whitespace-nowrap text-slate-600 transition-colors hover:border-indigo-200 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {label}
    </button>
  );
}

function BotAvatar() {
  return (
    <span
      role="img"
      aria-label="Lotse"
      className="flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-sm"
    >
      <Bot className="size-4" />
    </span>
  );
}

function UserAvatar() {
  return (
    <span
      role="img"
      aria-label="You"
      className="flex size-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500 ring-1 ring-slate-200"
    >
      <User className="size-4" />
    </span>
  );
}
