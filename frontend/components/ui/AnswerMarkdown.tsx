import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/cn";

/**
 * Renders the Q&A agent's Groq-generated answer — which regularly comes back
 * as real markdown (bold, bullet/numbered lists, GFM tables, horizontal
 * rules) — as styled React elements. react-markdown never injects raw HTML
 * unless rehype-raw is added (it isn't here), so LLM-sourced content stays
 * safe from injection the same way plain-text JSX already was.
 */
export function AnswerMarkdown({ content }: { content: string }) {
  return (
    <div className="space-y-2 text-xs leading-relaxed text-fg [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-1.5">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-fg">{children}</strong>,
          em: ({ children }) => <em className="text-fg-muted not-italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="my-1.5 list-disc space-y-0.5 pl-4 marker:text-fg-faint">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-1.5 list-decimal space-y-0.5 pl-4 marker:text-fg-faint">{children}</ol>
          ),
          li: ({ children }) => <li className="pl-0.5">{children}</li>,
          hr: () => <hr className="my-2.5 border-rule" />,
          code: ({ children }) => (
            <code className="figure rounded-sm bg-bg-elevated px-1 py-0.5 text-[11px] text-accent-green">
              {children}
            </code>
          ),
          h1: ({ children }) => <p className="mt-2 font-semibold text-fg">{children}</p>,
          h2: ({ children }) => <p className="mt-2 font-semibold text-fg">{children}</p>,
          h3: ({ children }) => <p className="mt-2 font-semibold text-fg">{children}</p>,
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="text-accent-blue underline underline-offset-2"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto rounded-sm border border-rule">
              <table className="w-full border-collapse text-[11px]">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-bg-elevated">{children}</thead>,
          th: ({ children, style }) => (
            <th
              className={cn(
                "border-b border-rule px-2 py-1.5 text-left font-medium uppercase tracking-wide text-fg-muted",
                style?.textAlign === "right" && "text-right",
                style?.textAlign === "center" && "text-center"
              )}
              style={style}
            >
              {children}
            </th>
          ),
          td: ({ children, style }) => (
            <td
              className={cn(
                "figure border-b border-rule px-2 py-1.5 text-fg",
                style?.textAlign === "right" && "text-right",
                style?.textAlign === "center" && "text-center"
              )}
              style={style}
            >
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
