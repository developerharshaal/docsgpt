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
- [x] **Phase 3 — Chunking, embeddings & vector search** (Days 6–8) — done
  - [x] Chunking — `chunk_text` fixed-size sliding window (char size+overlap), returns `(offset, text)` tuples; unit-tested
  - [x] Embeddings — `embeddings.py` owns `SentenceTransformer` (bge-small, 384-dim) loaded once at module
    level + `get_embedding(text)`; `HF_HUB_OFFLINE=1` set before import to use local cache
  - [x] Store chunks + vectors — `save_chunks(doc_id, text)` chunks → embeds → delete-then-reinsert
    (choice: always-fresh over `ON CONFLICT`, so re-ingest reflects source changes); logging → `logs.log`
    (filemode="w", rewritten each run); main loop wired: fetch→parse→save_document→lookup doc_id→save_chunks
  - [x] `POST /search` (cosine similarity) — `search.py` `search_chunks(query, k)` (embed query →
    `Chunk.embeddings.cosine_distance(query_vec)` → order_by ascending → limit k); wired into `main.py`
  - [x] pgvector HNSW index on `chunks.embeddings` (`vector_cosine_ops`) — matches the `<=>` query operator
  - _Deferred optimizations (revisit after basics work):_
    - Heading/structure-aware chunking — needs `parse_document` to preserve structure (currently
      `get_text()` strips all HTML → flat text with no headings to split on); ALSO strips nav/TOC menus into
      chunks → junk chunks waste retrieval slots (seen live in Phase 4 debugging)
    - Tune chunk size + overlap once we can eyeball real search results
    - Batch-embed chunks (perf) instead of one-at-a-time
    - Vector index tuning (IVFFlat/HNSW params) once corpus is larger
- [x] **Phase 4 — RAG answer pipeline with Claude** (Days 9–12) — done
  - [x] Anthropic SDK setup — `pip install anthropic`; API key from `ANTHROPIC_API_KEY` via `.env`
    (`python-dotenv` `load_dotenv()`; `.env` gitignored); auth verified with throwaway `hello_claude.py`
  - [x] `rag.py` `answer_question(question, k)` — retrieve (`search_chunks`) → stitch excerpts → grounded
    prompt (system: answer ONLY from excerpts, else "couldn't find in docs" fallback) → `claude-opus-4-8`
    generate → return answer text. Wired into `main.py` `POST /ask` (Pydantic `AskRequest`)
  - [x] Learned live: "not found" was correct behavior — query-params page wasn't ingested (corpus-coverage
    gap, not a bug). Fix: expanded `sources.json` (query-params, body) + re-ingest. Lesson: RAG quality is
    dominated by retrieval/corpus, not the LLM — debug by printing retrieved context first
  - [x] Citations — `search_chunks` now JOINs `documents` (INNER via `Chunk.doc_id == Document.id`) and
    selects `url`/`title`; switched call sites from positional unpacking to by-name `Row` access. `answer_question`
    numbers excerpts (`enumerate(start=1)` → `[n] text` in prompt) + builds parallel `sources` list; system prompt
    asks Claude to cite `[n]`; returns `{"answer", "sources"}`. Both callers updated (`/search`, `/ask`). Verified
    live: `/ask` returns bracketed cites + n→url/title map. Decision: kept SQLAlchemy Rows w/ labeled cols (by-name
    access) over a class — promote to Pydantic model in Phase 5 if fields keep growing
  - [x] Classify intent — `classify.py` `classify_intent()` (haiku, structured outputs via `messages.parse` +
    `output_format=ClassifyRequest` Pydantic model; `MessageType` enum greeting/factual/broad). Wired into
    `rag.py`: greeting short-circuits (0 retrieval), `CONFIG_BY_INTENT` routes factual→sonnet/k=5, broad→opus/k=10.
    Verified live on server: source count is the fingerprint of which branch fired (0/5/10). Noted: broad topics
    (e.g. "how does dependency injection work") retrieve but answer-model hedges → corpus gap (DI pages not in
    `sources.json`), consistent with the "retrieval dominates RAG quality" lesson — not a classify bug
  - [x] Cost logging — logging was never configured for the server (only in `injest.py` `__main__`), so
    added `basicConfig` to `main.py` (filemode="a"). Shared `usage.py` `log_usage(logger, model, usage)` logs
    `in/out/cache_read/cache_write` tokens at BOTH Claude calls (classify haiku + answer sonnet/opus). Also added
    a meaningful one-line-per-decision trace: `POST /ask|/search` (main), `classify message_type=` +
    `route intent/model/k` (rag), `search hits/best_distance` (search — high best_distance = corpus-gap tell).
    Logged tokens not dollars on purpose (prices go stale in code; multiply offline). Verified live via `logs.log`
  - [x] Prompt caching — wired `cache_control={"type":"ephemeral"}` on the `system` block (as content-block list)
    in both `rag.py` and `classify.py`. Deliberate measured no-op today: system prompts are ~80/130 tokens, below
    the cache minimum (~1024, ~2048 for Haiku), so it declines silently and `cache_read/write` stay 0 — confirmed
    via the usage logs. Correct mechanics are in place; caching starts paying off on a large stable prefix (Phase 5
    agent tool schemas). Lesson: caching fails silently below the minimum — check prefix token size first
  - _Deferred (after planned steps): overview open-knowledge formats (e.g. structured/open knowledge
    representations) that could improve RAG quality — evaluate once the core pipeline + citations are done_
- [x] **Phase 5 — Agentic layer** (Days 13–15) — done
  - [x] Tool runner — `agent.py` uses `client.beta.messages.tool_runner` (SDK drives the
    request→execute→loop cycle) with three `@beta_tool` functions: `search_docs(query)` (calls
    `search_chunks`, returns numbered+sourced excerpts), `fetch_doc_page(url)` (selects `Document.text`
    for a full page when excerpts are too thin), `flag_gap(topic)` (logs a warning when the docs genuinely
    don't cover it). `answer_with_agent(question)` iterates the runner, logs per-turn usage, returns text.
    System prompt: answer ONLY from retrieved docs, cite `[n]`, else flag the gap — never invent
  - [x] Sources in agent output — problem: retrieval happens *inside* `search_docs`, so `answer_with_agent`
    never sees the rows (unlike `rag.py`). Fix: a `contextvars.ContextVar` (`_request_sources`) per request
    (not a module global — FastAPI runs sync endpoints in a threadpool). `search_docs` appends each
    `{n, url, title}`, numbered **globally** across all searches in the request (so multiple search calls
    don't collide on `[1]`). `answer_with_agent` now returns `{"answer", "sources"}` — same shape as
    `rag.answer_question`, so endpoints are interchangeable
  - [x] Wired `POST /ask-agent` in `main.py` (mirrors `/ask` but routes to the agent). Kept `/ask` on
    `rag.py` on purpose → live A/B of one-shot RAG vs. agent on the same question. (Bug caught at run time,
    not import time: `result["amswer"]` typo → `KeyError`/500; lesson to test the request, not trust the import)
  - [x] Verified live — corpus before/after: agent asked "how to add middleware", couldn't retrieve it,
    correctly `flag_gap`'d instead of hallucinating (middleware page wasn't in `sources.json`). Added the URL +
    re-ingested → *same code, same query* flipped to a full-page-grounded cited answer. Proof the agent's
    honesty is real and the failure was upstream (corpus coverage), not the agent. Also re-confirmed the
    nav-chrome noise (get_text pulls the site nav sidebar into chunks) — deferred fix in Phase 3 notes
  - [x] Prompt caching finally engages here — the tool schemas + frozen system prompt form a large stable
    prefix (cache_write went 0→2196 once excerpts bulked the prefix past the ~4096 Opus minimum), unlike the
    tiny prompts in `rag.py`/`classify.py`
  - [x] Live cost A/B (same middleware question): `/ask` = 2 cheap calls (haiku classify + sonnet answer),
    1 search, ~1.5K in / 172 out, ~11.7s. `/ask-agent` = 3 Opus calls (search → fetch full page → answer),
    ~8.6K in / 940 out, ~14.7s. Agent produced a richer full-page-grounded answer but at ~5× tokens on the
    priciest tier — overkill for a simple "how do I" Q. This is the empirical motivation for confidence gating
  - [x] **Confidence gating** — resolved: `best_distance` from the existing retrieval pass, not intent class
    or a separate pre-check (it's already computed free by `search.py`, and it measures whether retrieval
    *succeeded*, which is exactly what the agent's re-search/fetch-page/flag-gap abilities address — intent
    class only predicts question *shape*). New `gate.py::answer_gated`, wired at `POST /ask-smart`; kept
    `/ask` and `/ask-agent` untouched so the A/B comparison above still stands on its own
  - [x] Sampled best_distance on 5 in-corpus + 5 out-of-corpus FastAPI questions + 1 fully off-topic one:
    covered 0.1451–0.2166, missing 0.1875–0.4755. **Finding: not a clean separator** — a genuinely-missing
    OAuth2 question (0.1875) scored *better* than a genuinely-covered "first steps" question (0.2166). Only
    the fully off-domain query (pizza toppings, 0.4755) separated cleanly. `CONFIDENCE_THRESHOLD = 0.22` is
    set above every covered sample here, biasing toward "never escalate a real hit" since escalation costs
    ~5× tokens (see the A/B above) — accepting that a handful of borderline real gaps (like OAuth2) will
    fall through to `/ask`'s "couldn't find that in the documentation" fallback instead of the agent's
    `flag_gap`. Revisit with a real eval set, not 11 hand-picked queries, before trusting the number
  - [x] Refactored `rag.py`: pulled the model-call/prompt/cache/usage-logging block out of `answer_question`
    into `_generate_answer(question, chunks, model)` so `gate.py` reuses the exact same generation step
    after deciding retrieval was good enough, instead of duplicating it
  - [x] Escalation is discard-and-re-search, not seed-the-agent — `gate.py` decides on one retrieval pass,
    then on escalation `agent.answer_with_agent` retrieves again from scratch inside its own tool loop.
    Deliberate simplification: the discarded pass is a local embed + pgvector query, $0 in API tokens, so
    it's cheap next to threading pre-fetched chunks through the tool-runner's contract
  - [x] Verified live end-to-end via a real server (all three routes): "hi there" → `route=greeting`
    short-circuit; "how do I add middleware" → `route=rag`, sonnet answered from excerpts; "how do I use
    WebSockets" → `route=agent` (`best_distance=0.2361` > threshold), escalated, and hit a genuine gap —
    WebSockets was never in `sources.json` in the first place, so the agent's honest "couldn't retrieve
    it, don't want to invent it" answer was the *correct* outcome, not a fluke. Log line confirms the
    decision: `gate: gate route=agent intent=broad best_distance=0.2361 threshold=0.2200`
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
