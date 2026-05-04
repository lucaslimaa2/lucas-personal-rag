# CLAUDE.md — Project context for Claude Code

This file is auto-loaded by Claude Code whenever a session opens this folder. It tells Claude what this project is, what's been done, and how Lucas wants to work.

---

## What this project is

A Retrieval-Augmented Generation (RAG) chatbot — "Chat with Lucas's resume + VEGA's work."

Visitors ask questions about Lucas Lima's career, skills, and the projects he worked on at VEGA; the chatbot answers grounded in his real professional content. This is project #1 of his AI portfolio, intended both as a learning exercise and as a public demo embedded/linked from [lucaslima.xyz](https://lucaslima.xyz).

## Who Lucas is

Growth + Data + AI professional based in Brazil. Co-founded **VEGA**, a Web3 growth agency for protocols (Wormhole, Ripple, Monad, Pyth, etc.). Previously at Coca-Cola in HR data analytics. Web3 event experience: Ethereum Brasil, Hack-a-TON, Monad Blitz, Ripple Hackathons, Wormhole events.

## Stack (locked in)

| Component | Choice |
|---|---|
| Runtime | **Python 3.12** managed by **uv** |
| Embeddings | **OpenAI** `text-embedding-3-small` (dim 1536) |
| Vector DB | **Pinecone** (serverless, free starter tier) |
| LLM | **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) — env var lets us flip to Sonnet for comparison |
| UI | **Streamlit** |
| Deploy | **Railway** (Vercel doesn't fit a long-running Streamlit process) |
| Budget | **~$25/mo cap** on Anthropic prepaid credits, auto-reload OFF; OpenAI hard limit ~$5/mo |

## How Lucas wants to work — IMPORTANT

Lucas is a non-coder learner, not a client. His **#1 goal is to LEARN**, not to ship fast. Concretely:

- **Before each phase:** explain what we're about to build, why this approach, what alternatives exist (with tradeoffs).
- **After writing code:** walk through it conceptually — what each block does, why it's structured that way.
- **Don't dump big code blocks** without teaching scaffolding.
- **Maintain `LEARNINGS.md`** — append a new section per phase capturing concepts (chunking, embeddings, retrieval strategy, etc.).
- He **can read code but can't write much from scratch** — assume basics, explain anything domain-specific.

For pure execution tasks ("rename this file", "run this command") skip the teaching scaffolding — match the request.

## Roadmap (10 phases)

```
Phase 0   Setup                          ✅ DONE
Phase 1   Knowledge base prep           ← NEXT
Phase 2   Chunking
Phase 3   Embedding & indexing          (Pinecone first used here)
Phase 4   Retrieval
Phase 5   Generation (full RAG in CLI)
Phase 6   Streamlit UI
Phase 7   Cost & safety hardening       (prompt caching, rate limiting)
Phase 8   Eval (small Q&A test set)
Phase 9   Deploy to Railway             (Railway first used here)
Phase 10  Polish & writeup
```

## Current status (as of Phase 0 completion)

- `pyproject.toml` + `uv.lock` — deps installed: `openai`, `anthropic`, `pinecone`, `streamlit`, `python-dotenv`
- `.env` — has working OpenAI + Anthropic keys (Pinecone key still placeholder; will fill before Phase 3)
- `.env.example` — placeholders only (cleaned, safe to commit)
- `.gitignore` — ignores `.env`, `.venv`, build artifacts
- `.python-version` — pins Python 3.12
- `scripts/hello_check.py` — Phase 0 sanity check; **currently passing** (OpenAI dim 1536, Anthropic returns "PONG")
- `data/raw/` — empty, awaits Phase 1 content (resume.md, vega-<protocol>.md, coca-cola-role.md, events.md)
- `LEARNINGS.md` — seeded with architecture diagram + Phase 0 concepts

## Key commands

```bash
# Run any Python script through the project's venv
python -m uv run scripts/hello_check.py

# Add a new dependency
python -m uv add <package>

# (Note: bare `uv` isn't on PATH on this Windows install — use `python -m uv` everywhere)
```

## Do / don't

- **Do** edit files with absolute paths, since the shell cwd resets between Bash calls in this environment.
- **Do** keep secrets in `.env` only. Never paste real keys into `.env.example`, code, commits, or chat.
- **Don't** introduce TypeScript/Node tooling — Lucas explicitly doesn't want to learn it for this project.
- **Don't** push to GitHub or deploy until Phases 9–10. Local development only until then.
- **Don't** create new memory files in `~/.claude/projects/.../memory/` — they're per-project-folder and don't follow this project. Persistent context lives in **this file** and `LEARNINGS.md`.
