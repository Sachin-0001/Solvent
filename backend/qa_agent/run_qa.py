"""
Step 5 CLI entry point. Run with:
  python -m backend.qa_agent.run_qa "How much of my GST-on-fee revenue is unmatched?"

Prints the agent's answer. There's no frontend yet (that's step 6) so this is
how to exercise/validate the Q&A agent directly.
"""

from __future__ import annotations

import sys

from backend.qa_agent.agent import answer_question


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m backend.qa_agent.run_qa "<question>"')
        raise SystemExit(1)
    question = " ".join(sys.argv[1:])
    print(f"Q: {question}\n")
    answer, trace = answer_question(question)
    if trace:
        print("Tool calls:")
        for t in trace:
            marker = "OK" if t["status"] == "success" else "FAIL"
            print(f"  [{marker}] {t['name']}({t['arguments']}) -> {t['result_summary']} ({t['duration_ms']}ms)")
        print()
    print(f"A: {answer}")


if __name__ == "__main__":
    main()
