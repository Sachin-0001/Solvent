"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Landmark, Receipt, Sparkles, TrendingUp, X } from "lucide-react";
import { api, type ToolCallTrace } from "@/lib/api";
import { AnswerMarkdown } from "@/components/ui/AnswerMarkdown";
import { ToolCallLog } from "@/components/ui/ToolCallLog";

interface Message {
  role: "user" | "assistant";
  content: string;
  trace?: ToolCallTrace[];
  failed?: boolean;
}

/** Grouped starters - shows the range of what the agent can actually answer. */
const STARTER_GROUPS = [
  {
    icon: Landmark,
    label: "Cash & forecast",
    questions: [
      "What's my projected cash position for tomorrow?",
      "How much cash should I expect over the next 7 days?",
    ],
  },
  {
    icon: Receipt,
    label: "Reconciliation",
    questions: [
      "What's my current reconciliation match rate?",
      "Which transactions are unresolved and why?",
    ],
  },
  {
    icon: TrendingUp,
    label: "Transactions & tax",
    questions: [
      "Give me a full audit report of my settlements",
      "Which transactions had a refund?",
    ],
  },
];

const TOOL_NAMES = [
  "search_payments",
  "search_settlements",
  "search_invoices",
  "find_relation",
  "generate_audit_report",
];

export function AskWidget({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Keeps the effect below from depending on `onClose`'s identity - it's a
  // fresh inline function on every DashboardPage re-render (every poll
  // tick), which would otherwise tear down and re-attach the Escape
  // listener/scroll-lock/focus on each one while the drawer is open.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    requestAnimationFrame(() => inputRef.current?.focus());

    function onKeydown(e: KeyboardEvent) {
      if (e.key === "Escape") onCloseRef.current();
    }
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, [open]);

  function scrollToBottom() {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }

  async function send(question: string) {
    if (!question.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    scrollToBottom();
    try {
      const { answer, trace } = await api.askQuestion(question);
      setMessages((m) => [...m, { role: "assistant", content: answer, trace }]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Couldn't reach the Q&A agent - is the API server running on :8000?",
          failed: true,
        },
      ]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  }

  if (!open) return null;

  return (
    <>
      {/* Scrim - click to dismiss. */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden
      />

      {/* Right-side drawer: sits beside the dashboard instead of covering it. */}
      <aside
        role="dialog"
        aria-label="Solvent AI"
        className="drawer-in fixed top-0 right-0 z-50 flex h-screen w-full max-w-[480px] flex-col border-l border-rule-strong bg-bg-sidebar shadow-2xl"
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-rule px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-[var(--radius-control)] bg-accent">
              <Sparkles size={12} className="text-white" />
            </span>
            <div>
              <div className="text-[13px] font-semibold text-fg">
                <span className="wordmark">Solvent</span> AI
              </div>
              <div className="text-[11px] text-fg-faint">
                Reads your live reconciliation, tax &amp; cash data
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-[var(--radius-control)] p-1.5 text-fg-faint transition-colors hover:bg-card-hover hover:text-fg"
          >
            <X size={15} />
          </button>
        </div>

        {/* Transcript */}
        <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {messages.length === 0 && (
            <div className="space-y-4">
              <div>
                <p className="text-[13px] text-fg">
                  Ask anything about your settlements. I&apos;ll pull the real numbers before
                  answering - never estimated.
                </p>
              </div>

              <div className="space-y-3">
                {STARTER_GROUPS.map((group) => {
                  const Icon = group.icon;
                  return (
                    <div key={group.label}>
                      <div className="mb-1.5 flex items-center gap-1.5">
                        <Icon size={11} className="text-fg-faint" />
                        <span className="text-[11px] font-medium uppercase tracking-wider text-fg-faint">
                          {group.label}
                        </span>
                      </div>
                      <div className="flex flex-col gap-1">
                        {group.questions.map((q) => (
                          <button
                            key={q}
                            onClick={() => send(q)}
                            className="rounded-[var(--radius-control)] border border-rule bg-card px-2.5 py-2 text-left text-[12px] text-fg-muted transition-colors hover:border-accent/40 hover:bg-accent-dim hover:text-fg"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Capability disclosure - makes the agent's reach legible. */}
              <div className="rounded-[var(--radius-control)] border border-rule bg-card px-3 py-2.5">
                <div className="text-[11px] font-medium uppercase tracking-wider text-fg-faint">
                  Tools available
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {TOOL_NAMES.map((t) => (
                    <span
                      key={t}
                      className="figure rounded-full border border-rule px-1.5 py-0.5 text-[10px] text-fg-muted"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="fade-in-up flex justify-end">
                <div className="max-w-[85%] rounded-[var(--radius-card)] rounded-br-sm bg-accent px-3 py-2 text-[13px] leading-relaxed text-white">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={i} className="fade-in-up flex gap-2.5">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-dim">
                  <Sparkles size={10} className="text-accent" />
                </span>
                <div className="min-w-0 flex-1">
                  {m.trace && m.trace.length > 0 && <ToolCallLog trace={m.trace} />}
                  {m.failed ? (
                    <div className="rounded-[var(--radius-control)] border border-accent-red/30 bg-accent-red-dim px-2.5 py-2 text-[12px] text-accent-red">
                      {m.content}
                    </div>
                  ) : (
                    <AnswerMarkdown content={m.content} />
                  )}
                </div>
              </div>
            )
          )}

          {loading && (
            <div className="flex gap-2.5">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-dim">
                <Sparkles size={10} className="text-accent" />
              </span>
              <div className="flex items-center gap-2 pt-0.5">
                <span className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent" />
                </span>
                <span className="text-[11px] text-fg-faint">
                  looking up your data&hellip;
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="shrink-0 border-t border-rule p-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex items-end gap-2 rounded-[var(--radius-control)] border border-border-strong bg-card px-2.5 py-2 transition-colors focus-within:border-accent"
          >
            <textarea
              ref={inputRef}
              value={input}
              rows={1}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Ask about settlements, exceptions, or cash…"
              className="max-h-28 min-h-[20px] flex-1 resize-none bg-transparent text-[13px] text-fg placeholder:text-fg-faint focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              aria-label="Send"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-opacity hover:bg-accent-hover disabled:opacity-25"
            >
              <ArrowUp size={13} />
            </button>
          </form>
          <div className="mt-1.5 px-0.5 text-[10px] text-fg-faint">
            Figures come from deterministic backend functions - the model explains them, it
            doesn&apos;t calculate them.
          </div>
        </div>
      </aside>
    </>
  );
}
