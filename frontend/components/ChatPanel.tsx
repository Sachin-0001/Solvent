"use client";

import { Send, Sparkles } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "@/lib/api";

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

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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
    <div className="flex h-[520px] flex-col rounded-xl border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-5 py-4">
        <Sparkles size={14} className="text-accent-green" />
        <div className="text-xs font-medium uppercase tracking-wider text-fg-muted">
          Settlement Q&A
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-fg-faint">Ask about reconciliation, tax, or forecasts.</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-border-strong px-3 py-1.5 text-xs text-fg-muted transition-colors hover:border-accent-green/40 hover:text-accent-green"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`fade-in-up max-w-[85%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${
              m.role === "user"
                ? "ml-auto bg-accent-blue/15 text-fg"
                : "border border-border bg-bg-elevated text-fg-muted"
            }`}
          >
            {m.content}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-1.5 rounded-lg border border-border bg-bg-elevated px-3.5 py-2.5 w-fit">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-green [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-green [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-green" />
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 border-t border-border p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your settlements..."
          className="flex-1 rounded-lg border border-border-strong bg-bg-elevated px-3 py-2 text-sm text-fg placeholder:text-fg-faint focus:border-accent-green/50 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-green text-bg transition-opacity disabled:opacity-30"
        >
          <Send size={15} />
        </button>
      </form>
    </div>
  );
}
