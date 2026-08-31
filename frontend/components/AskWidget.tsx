"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal, X } from "lucide-react";
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

export function AskWidget({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Keeps the effect below from depending on `onClose`'s identity — it's a
  // fresh inline function on every DashboardPage re-render (every poll
  // tick), which would otherwise tear down and re-attach the Escape
  // listener/scroll-lock/focus on each one while the modal is open.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    requestAnimationFrame(() => inputRef.current?.focus());

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function onKeydown(e: KeyboardEvent) {
      if (e.key === "Escape") onCloseRef.current();
    }
    window.addEventListener("keydown", onKeydown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeydown);
    };
  }, [open]);

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

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="modal-in flex h-[min(640px,85vh)] w-full max-w-xl flex-col border border-rule-strong bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-rule px-4 py-3.5">
          <div className="flex items-center gap-2">
            <Terminal size={13} className="text-accent-green" />
            <div className="text-xs font-medium uppercase tracking-wider text-fg-muted">
              Settlement Q&amp;A
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-sm p-1 text-fg-faint transition-colors hover:bg-card-hover hover:text-fg"
          >
            <X size={15} />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {messages.length === 0 && (
            <div className="space-y-2">
              <p className="text-[13px] text-fg-faint">Ask about reconciliation, tax, or forecasts.</p>
              <div className="flex flex-col gap-1.5">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-sm border border-border-strong px-2.5 py-1.5 text-left text-xs text-fg-muted transition-colors hover:border-accent-green/40 hover:text-accent-green"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className="fade-in-up text-[13px] leading-relaxed">
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
            className="figure flex-1 border border-border-strong bg-bg-elevated px-2.5 py-1.5 text-[13px] text-fg placeholder:font-sans placeholder:text-fg-faint focus:border-accent-green/50 focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="border border-accent-green/40 px-2.5 py-1.5 text-xs text-accent-green transition-opacity disabled:opacity-30"
          >
            Ask
          </button>
        </form>
      </div>
    </div>
  );
}
