# DocsGPT — Project Plan & Progress

> Living roadmap. We tick items off as we go. Full mentor-mode contract is in this file
> (see "How we'll work"). Auto-saved backup also lives at
> `C:\Users\harshaal\.claude\plans\sunny-foraging-gosling.md`.

## Progress tracker

- [~] **Phase 1 — Foundations & scaffold** (Days 1–2) — mostly done
  - [x] Python venv + FastAPI/uvicorn installed
  - [x] `main.py` with `GET /health` (+ `GET /`), running locally via uvicorn
  - [x] Git repo + `.gitignore` + first commit + GitHub remote (pushed to github.com/developerharshaal/docsgpt)
  - [x] `docker-compose.yml` — Postgres 16 + pgvector container running (`docker compose up -d`); pgvector verified via psql
  - [ ] app `Dockerfile` (containerize the FastAPI app) — deferred, do near deploy
  - [ ] `.env.example` (deferred → add with the API key in Phase 4)
  - [ ] GitHub Actions CI stub (ruff + pytest) — pairs with first tests in Phase 2
- [x] **Phase 2 — Data model & ingestion pipeline** (Days 3–5) — done
  - [x] `models.py` — SQLAlchemy 2.0 models `Document` (`documents`: id, url (unique), title, size, text) and
    `Chunk` (`chunks`: id, doc_id FK→documents.id, text, offset, embeddings `Vector(384)`)
  - [x] `db.py` — sync engine + `Base.metadata.create_all()`; tables verified live via
    `docker compose exec db psql -U docsgpt -d docsgpt -c "\dt"`
  - [ ] Alembic migration (deferred — using `create_all` for now; will also codify `CREATE EXTENSION vector`)
  - [x] `injest.py` — fetch (httpx) → parse (BeautifulSoup `get_text` clean) → save; config-driven
    URL list in `sources.json`; idempotent via `url` UNIQUE + `ON CONFLICT DO NOTHING` upsert
  - [x] pytest tests for ingestion (`test_injest.py`) — unit: `parse_document` (pure, exact-match) &
    `fetch_document` (mocked `httpx.get` w/ spy); integration: `save_document` against separate
    `docsgpt_test` DB via engine dependency-injection + fixture create_all/drop_all teardown
- [~] **Phase 3 — Chunking, embeddings & vector search** (Days 6–8)  ← *we are here*
  - [x] Chunking — `chunk_text` fixed-size sliding window (char size+overlap), returns `(offset, text)` tuples; unit-tested
  - [x] Embeddings — `embeddings.py` owns `SentenceTransformer` (bge-small, 384-dim) loaded once at module
    level + `get_embedding(text)`; `HF_HUB_OFFLINE=1` set before import to use local cache
  - [x] Store chunks + vectors — `save_chunks(doc_id, text)` chunks → embeds → delete-then-reinsert
    (choice: always-fresh over `ON CONFLICT`, so re-ingest reflects source changes); logging → `logs.log`
    (filemode="w", rewritten each run); main loop wired: fetch→parse→save_document→lookup doc_id→save_chunks
  - [~] `POST /search` (cosine similarity) — `search.py` `search_chunks(query, k)` drafted (embed query →
    `Chunk.embeddings.cosine_distance(query_vec)` → order_by ascending → limit k); ← *next: write & test it, then wire endpoint*
  - [ ] pgvector index (IVFFlat/HNSW) — add after search works (brute-force seq-scan fine for now)
  - _Deferred optimizations (revisit after basics work):_
    - Heading/structure-aware chunking — needs `parse_document` to preserve structure (currently
      `get_text()` strips all HTML → flat text with no headings to split on)
    - Tune chunk size + overlap once we can eyeball real search results
    - Batch-embed chunks (perf) instead of one-at-a-time
    - Vector index tuning (IVFFlat/HNSW params) once corpus is larger
- [ ] **Phase 4 — RAG answer pipeline with Claude** (Days 9–12)
- [ ] **Phase 5 — Agentic layer** (Days 13–15)
- [ ] **Phase 6 — Frontend (React + Vite)** (Days 16–17)
- [ ] **Phase 7 — Harden** (Days 18–19)
- [ ] **Phase 8 — Deploy & document** (Day 20)

**Environment status:** Python 3.12.3 ✅ · Git 2.45.1 ✅ · Docker ✅ (Desktop running, pgvector container up) · Node ❌ (needed Phase 6)

---

## Context

Harshaal is a Commvault test engineer (Python automation) moving into an **AI/LLM
app-dev role elsewhere**. This is a **learning** build over ~20 days (target ~2026-08-19).
**Hard constraint: only public/open data — no company or private data.**

**Project:** "DocsGPT" — an AI assistant that answers questions over an open-source
project's **public documentation** ("chat with the docs"). Default corpus: the **FastAPI
docs** (public, MIT-licensed, and teaches the framework we build with).

**Flow:** ingest public docs → chunk + embed → store vectors → user asks → classify intent
→ retrieve relevant chunks (vector search) → Claude answers **with inline citations** →
agent layer can search again / fetch a page / flag a gap → thin web UI shows answer + sources.

## How we'll work together — LEARNING MODE (operating contract)

Not a delivery — a learning project. **Claude will not just build it.** Every step:
1. **Concept first** — what it is, *why* it exists, plain language + small example.
2. **Show the pattern** — a minimal annotated example, not the finished feature.
3. **You write the code** — you type it; Claude guides/reviews. Claude writes only when
   you ask or to unblock after you've tried.
4. **Run & verify together** — run it, read errors together, explain the output.
5. **Check understanding** — a question or prediction before advancing.
6. **Recap** — "what you learned" + an interview talking point.

Pace is yours; ask "why" freely; say "slow down / I don't get X" anytime.

## Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Web framework | FastAPI (async) + Pydantic v2 |
| DB + vectors | PostgreSQL + pgvector |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic |
| LLM | Anthropic Claude — `claude-haiku-4-5` (classify), `claude-opus-4-8` (generate), `tool_runner` (agent) |
| Embeddings | local `sentence-transformers` (bge-small) for $0 while learning → Voyage AI later |
| Ingestion | `httpx` + `beautifulsoup4` / Markdown parser |
| Frontend | Minimal React + Vite (TS) — fallback HTMX |
| Container | Docker + docker-compose |
| CI/CD | GitHub Actions (ruff + pytest) |
| Deploy | Render or Fly.io |
| Tests | pytest + httpx AsyncClient |

> No Opus 5 exists. `claude-opus-4-8` = top Opus; `claude-haiku-4-5` = cheap/fast tier.
> Never hardcode API keys — read `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` from the environment.

## Phases (each run in Learning-Mode)

1. **Foundations & scaffold** — venv, FastAPI `/health`, Git+GitHub, Docker/compose, CI stub.
   Concepts: web framework/ASGI, sync vs async, containers, CI.
2. **Data model & ingestion** — SQLAlchemy `documents`/`chunks`, Alembic migration, ingest
   FastAPI docs markdown, pytest. Concepts: ORM vs SQL, migrations, schema design, testing.
3. **Chunking, embeddings & vector search** — chunk by heading, embed, pgvector index,
   `POST /search`. Concepts: embeddings, cosine similarity, chunking, vector index.
4. **RAG answer pipeline** — `POST /ask`: classify (haiku, structured outputs) → retrieve →
   answer (opus) grounded w/ inline citations + "not found" fallback; prompt caching; cost
   logging. Concepts: RAG, grounding vs hallucination, structured outputs, caching, model choice.
5. **Agentic layer** — tool runner w/ `search_docs`, `fetch_doc_page`, `flag_gap`; confidence
   gating. Concepts: the tool-call loop, tool schemas, when agents help.
6. **Frontend** — React+Vite chat UI: question → answer + clickable sources + feedback.
   Concepts: client↔API split, CORS, streaming, UX.
7. **Harden** — auth, rate limiting, structured logging, error handling, more tests, CI green.
   Concepts: auth, observability, prototype vs production.
8. **Deploy & document** — Render/Fly + managed Postgres, secrets, README + diagram + demo.
   Concepts: deploy, secrets, telling the story to a hiring manager.

## Verification

- Local: `docker-compose up` → `curl /health`; `pytest`; ingestion fills pgvector;
  `POST /search` returns ranked hits w/ URLs.
- RAG: `POST /ask` returns grounded answer + citations; out-of-scope → "not found in docs".
- Agent: vague question triggers a `search_docs` refinement.
- CI: branch push → GitHub Actions ruff + pytest green.
- Deployed: public URL, ask via UI, see answer + sources.
- You: at each checkpoint, can explain in your own words what we built and why.
