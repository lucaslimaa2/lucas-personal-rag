"""
Chat — generate a grounded answer to a question, using retrieved chunks as
the only allowed source of facts.

Public API:
  answer(question, history=None) -> (assistant_text, updated_history, retrieved_results)

Multi-turn: the caller stores `updated_history` and passes it back next turn.
Bare question/answer pairs go in history (no context bloat); fresh context
is retrieved per turn for the new question.
"""

from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic

from retriever import RetrievalResult, retrieve


CHAT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = 800
TEMPERATURE = 0.2
DEFAULT_K = 10


SYSTEM_PROMPT = """\
You are an assistant that answers questions about Antonio Lucas Lima — \
a Growth + Data + AI professional based in Brazil, co-founder of VEGA \
(a Web3 growth and go-to-market agency).

Rules:
1. Use ONLY the retrieved CONTEXT in the user's message to answer. Do not \
use general knowledge or invent facts.
2. If the context does not contain the answer, reply: "I don't have that \
information about Lucas." Do not guess.
3. Speak about Lucas in third person.
4. Be concise — answer the question directly. Do not repeat the question. \
Do not pad with filler.
5. Use plain prose. Do not use markdown bold (**word**) or italic (*word*) \
syntax — write everything in plain text.
6. Do not include inline source citations. Only mention which page a fact \
came from if the user explicitly asks where the information is from.
"""


# --------------------------------------------------------------- public API


def answer(
    question: str,
    history: list[dict[str, Any]] | None = None,
    k: int = DEFAULT_K,
    namespace: str = "dev",
) -> tuple[str, list[dict[str, Any]], list[RetrievalResult]]:
    """Generate a grounded answer.

    Returns:
      (assistant_text, updated_history, retrieved_results)

    `updated_history` contains the bare question + assistant answer for this
    turn — pass it back next turn for multi-turn continuity.
    """
    history = list(history or [])

    # 1. Retrieve fresh context for this question
    results = retrieve(question, k=k, namespace=namespace)

    # 2. Build the user message containing the context + the question
    user_msg_text = _build_user_message(question, results)

    # 3. Compose messages: prior bare history + current context-rich user msg
    messages = history + [{"role": "user", "content": user_msg_text}]

    # 4. Call Claude
    client = Anthropic()
    resp = client.messages.create(
        model=CHAT_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    assistant_text = resp.content[0].text.strip() if resp.content else ""

    # 5. Update history with the BARE question + answer (no context bloat)
    updated_history = history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": assistant_text},
    ]

    return assistant_text, updated_history, results


# --------------------------------------------------------------- internals


def _build_user_message(question: str, results: list[RetrievalResult]) -> str:
    """Format retrieved chunks as labeled context, followed by the question."""
    if not results:
        context_str = "(no relevant context found)"
    else:
        blocks = []
        for r in results:
            title = r.metadata.get("title", "?")
            section = r.metadata.get("section_heading", "?")
            label = f"[Source: {title} — {section}]"
            blocks.append(f"{label}\n{r.text}")
        context_str = "\n\n---\n\n".join(blocks)

    return f"CONTEXT:\n{context_str}\n\nQUESTION: {question}"
