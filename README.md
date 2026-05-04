# Lucas Resume & VEGA RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that answers questions about Lucas Lima's career, skills, and the work he did at VEGA — grounded in his actual resume, case studies, and event experience.

This is project #1 of Lucas's AI portfolio, intended both as a learning exercise and as a public demo embedded from [lucaslima.xyz](https://lucaslima.xyz).

## Stack

- **Python 3.12** (managed by [uv](https://docs.astral.sh/uv/))
- **Embeddings:** OpenAI `text-embedding-3-small`
- **Vector DB:** Pinecone (serverless)
- **LLM:** Anthropic Claude Haiku 4.5 (with prompt caching)
- **UI:** Streamlit
- **Deploy:** Railway


## Quick start (once keys are in place)

```bash
# 1. Copy the env template and fill in your keys
cp .env.example .env

# 2. Verify the keys work (Phase 0 sanity check)
uv run scripts/hello_check.py
```

Subsequent phases will add `chunker.py`, `index.py`, `retrieve.py`, `chat.py`, and `app.py` (Streamlit UI).
