# Lucas Lima · Resume RAG Chatbot

A retrieval-augmented chatbot that answers questions about my professional background: resume, VEGA case studies, Coca-Cola Analytics Engineering work, languages, education, and more.

**Live demo:** [chat.lucaslima.xyz](https://chat.lucaslima.xyz)

Project #1 of my AI portfolio at [lucaslima.xyz/ai-portfolio](https://lucaslima.xyz/ai-portfolio).

---

## How it works

```
              Notion (knowledge base)
                       │
                       ▼   load + group by H2 sections
              loaders/notion.py
                       │
                       ▼   ~300-token chunks
              chunker.py
                       │
                       ▼   embed (OpenAI) + upsert (Pinecone)
              indexer.py  ─────────────────►  Pinecone (dev / prod)
                                                    │
                                                    │ top-K cosine search
              api/chat.py  ◄────  retriever.py  ◄───┘
                  │   ▲
   POST /api/chat │   │
                  ▼   │
              chat.py (Claude Haiku 4.5, with prompt caching)
                  │
                  ▼
              Vanilla JS chat UI (index.html, chat.js)
```

The full RAG pipeline:

1. **Source content** lives in a Notion database. Pages are tagged with `Doc Type` (Resume / Case Study / Role / Overview) and `Status` (Ready / Draft).
2. **Indexer** fetches Ready pages, chunks them along H2 section boundaries, embeds via OpenAI, and upserts to Pinecone with stable IDs derived from `(page_id, section_index, slice_index)`.
3. **Retriever** embeds the user question with the same model used for chunks, queries Pinecone for the top-K most similar vectors, and returns chunks with their metadata.
4. **Generator** builds a prompt with strict grounding rules, attaches retrieved chunks as labeled context, includes the multi-turn conversation history, and calls Claude Haiku 4.5.
5. **Frontend** is a vanilla HTML/CSS/JS chat UI served from Vercel alongside a Python serverless function (`api/chat.py`) that wraps the chat logic.

## Stack and choices

| Layer | Tool | Why |
|---|---|---|
| Knowledge source | Notion | Already where I keep career notes. Single place to edit. Structured properties become Pinecone metadata. |
| Chunker | Custom (heading-aware, paragraph-aware fallback) | Markdown from Notion has H2 boundaries that already define topical chunks. Owning the chunker means owning the metadata + debug story. |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dim) | Cost-balanced default. Same model on both sides (critical). |
| Vector DB | Pinecone (cosine similarity, dev / prod namespaces) | Managed, industry-standard. Free tier handles this corpus easily. |
| LLM | Claude Haiku 4.5 with prompt caching | Cost-efficient, strong instruction following on grounding rules. |
| Frontend | Vanilla HTML / JS / CSS | Matches my portfolio's tech. ~120 lines of JS, no framework overhead. |
| Hosting | Vercel (static + Python serverless function) | Single deploy, zero infrastructure to manage. |

### Production-grade touches

- **Hash-based incremental indexing.** Re-indexing only re-embeds chunks whose text actually changed. The chunk's text hash is stored in Pinecone metadata; on each run, hashes are compared and unchanged chunks are skipped.
- **Reconciliation.** After upsert, IDs in Pinecone that aren't in the current upsert set are deleted. Pages flipped from `Ready` to `Draft` (or removed entirely) lose their orphan vectors automatically.
- **Per-IP rate limiting** at 30 questions/hour, in-memory. Caps abuse without shared infrastructure.
- **Anthropic prompt caching** on the system prompt. Cached input tokens cost ~10% of normal price.
- **Structured request logging.** Every call logs IP, question prefix, latency, and remaining-window quota to Vercel function logs.
- **Loader interface (adapter pattern).** `loaders/base.py` defines the contract. `NotionLoader` is the first implementation. Adding Confluence, Drive, etc. would be a new file with no downstream changes.

## Repo layout

```
api/
  chat.py              HTTP wrapper around chat.answer() (Vercel serverless function)
loaders/
  base.py              Document dataclass + Loader interface
  notion.py            NotionLoader: fetch pages, group blocks into H2 sections
chat.py                Prompt construction + Claude call + multi-turn history
chunker.py             Heading-aware chunker, paragraph-fallback, tiktoken sizing
indexer.py             Embed + upsert + hash-based incremental skip + reconcile
retriever.py           Embed query, Pinecone top-K search

scripts/
  pinecone_setup.py    Create the Pinecone index (run once)
  index_run.py         End-to-end indexer (run on content changes)
  retrieve_test.py     Interactive REPL for retrieval debugging
  chat_cli.py          CLI chatbot for local testing
  chunk_preview.py     Print chunks for inspection

index.html             Chat UI page
chat.js                Chat client logic (in-memory history, typing indicator)
style.css              Styling, matches portfolio aesthetic

requirements.txt       Python deps for the Vercel function
vercel.json            Vercel config (framework override, function settings)
.vercelignore          Excludes uv files and indexing-only modules from the deploy
pyproject.toml + uv.lock   Local dev (uv-managed Python 3.12 environment)
```

## Local setup

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), a Notion integration with access to your knowledge-base database, plus OpenAI / Anthropic / Pinecone keys.

```bash
# 1. Configure secrets
cp .env.example .env   # then fill in your keys

# 2. Install deps
python -m uv sync

# 3. One-time: create the Pinecone index
python -m uv run scripts/pinecone_setup.py

# 4. Index your Notion content
python -m uv run scripts/index_run.py

# 5. Test the chat in the terminal
python -m uv run scripts/chat_cli.py
```

For the web frontend (Vercel local dev):

```bash
npx vercel dev
```

## Design decisions worth highlighting

A few non-obvious choices a reader might want context on.

**Chunker built from scratch, not LangChain.** The corpus is small and well-structured. A heading-aware chunker is ~80 lines. Pulling in LangChain would be cargo-culting and introduce dependency churn for no real benefit. If the corpus grew past ~10K chunks, I'd revisit.

**Notion as source of truth, not committed Markdown.** This mirrors how production teams actually work: content lives in the system that owns it, the pipeline ingests on demand. The adapter pattern in `loaders/` makes it cheap to swap sources later.

**K=10 retrieval, no reranking.** For a small corpus, larger K compensates for any single retrieval miss without paying for reranking. If retrieval quality degrades as the corpus grows, the next move is hybrid search or a Cohere reranker, not bigger K.

**Vanilla JS frontend, no framework.** Matches my existing portfolio's tech (lucaslima.xyz is plain HTML/JS too). The chat client is ~120 lines of readable JS with in-memory history. Trading off "polish" for "maintainable by anyone, including me in six months."

**Two-repo architecture.** This RAG project is its own deployable unit on `chat.lucaslima.xyz`. The personal portfolio at `lucaslima.xyz` links to it via a card on the AI portfolio page. Each repo can be shared with recruiters independently. No monorepo, no submodules.

## License

This repository's code is MIT-licensed. The content (resume, case studies) is reserved.
