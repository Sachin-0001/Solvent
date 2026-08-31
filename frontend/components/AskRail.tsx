"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal } from "lucide-react";
import { api } from "@/lib/api";
import { AnswerMarkdown } from "@/components/ui/AnswerMarkdown";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "What's my current reconciliation match rate?",
  "Which transactions are unresolved and why?",
  "How much cash should I expect over the next 7 days?",
  "Which transactions had a refund?",
];

export function AskRail() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKeydown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, []);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    try {
      const answer = await api.askQuestion(question);
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Couldn't reach the Q&A agent — is the API server running?" },
      ]);
    } finally {
      setLoading(false);
      requestAnimationFrame(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
      });
    }
  }

  return (
    <div className="flex h-full flex-col border border-rule bg-card">
      <div className="flex items-center gap-2 border-b border-rule px-4 py-3.5">
        <Terminal size={13} className="text-accent-green" />
        <div className="text-[11px] font-medium uppercase tracking-wider text-fg-muted">
          Settlement Q&amp;A
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs text-fg-faint">Ask about reconciliation, tax, or forecasts.</p>
            <div className="flex flex-col gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-sm border border-border-strong px-2.5 py-1.5 text-left text-[11px] text-fg-muted transition-colors hover:border-accent-green/40 hover:text-accent-green"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className="fade-in-up text-xs leading-relaxed">
            {m.role === "user" ? (
              <div className="figure text-fg-muted">
                <span className="text-accent-green">{">"}</span> {m.content}
              </div>
            ) : (
              <div className="mt-1 border-l border-rule pl-2.5">
                <AnswerMarkdown content={m.content} />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-1.5 pl-2.5">
            <span className="h-1 w-1 animate-bounce rounded-full bg-accent-green [animation-delay:-0.3s]" />
            <span className="h-1 w-1 animate-bounce rounded-full bg-accent-green [animation-delay:-0.15s]" />
            <span className="h-1 w-1 animate-bounce rounded-full bg-accent-green" />
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 border-t border-rule p-2.5"
      >
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your settlements…"
          className="figure flex-1 border border-border-strong bg-bg-elevated px-2.5 py-1.5 text-xs text-fg placeholder:font-sans placeholder:text-fg-faint focus:border-accent-green/50 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="border border-accent-green/40 px-2.5 py-1.5 text-[11px] text-accent-green transition-opacity disabled:opacity-30"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
