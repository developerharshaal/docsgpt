from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import contextvars
import logging

import anthropic
from anthropic import beta_tool
from sqlalchemy.orm import Session
from sqlalchemy import select

from db import engine
from models import Document
from search import search_chunks
from usage import log_usage

client = anthropic.Anthropic()
logger = logging.getLogger(__name__)

# search_docs runs *inside* the tool runner, so answer_with_agent never sees the
# retrieved rows directly. Each request stashes its sources here so we can return
# them alongside the answer (same shape as rag.answer_question). A ContextVar --
# not a module global -- because FastAPI runs sync endpoints in a threadpool, and
# each request gets its own copy of this var (no cross-request bleed).
_request_sources: contextvars.ContextVar[list] = contextvars.ContextVar(
    "request_sources", default=None
)

SYSTEM_PROMPT = """You are a documentation assistant for FastAPI. Answer questions \
using ONLY the FastAPI documentation, which you reach through your tools. Never answer \
from your own prior knowledge.

Your workflow for every question:
1. Call search_docs to retrieve relevant excerpts. If the first results are thin or \
off-topic, rephrase and search again before giving up.
2. If the excerpts are too short or cut off mid-thought, call fetch_doc_page with a URL \
from the search results to read the full page.
3. If, after searching, the documentation genuinely does not cover the topic, call \
flag_gap with a short description of what's missing, then tell the user plainly that \
the docs don't cover it. Do not invent an answer.

When you have enough to answer, write a clear response grounded in what you retrieved. \
After each claim, cite the excerpt number(s) in brackets, e.g. [1], [2], using only the \
numbers shown in the search results."""


@beta_tool
def search_docs(query: str) -> str:
    """
    Search the documentation for a given query.

    Args:
        query (str): The search query.

    Returns:
        str: A string containing the top_k search results.
    """
    rows = search_chunks(query=query, top_k=5)

    # Claude can't read SQLAlchemy Row objects — hand it back plain text.
    # Number the excerpts and label each with its source so Claude can cite it.
    if not rows:
        return "No matching documentation found."

    # Number GLOBALLY across every search in this request. Claude may call
    # search_docs more than once; if each call restarted at [1], the citations in
    # the final answer would collide. Continue from however many sources we've
    # already recorded, and register each number -> source so answer_with_agent
    # can return the same {n, url, title} list rag.answer_question produces.
    sources = _request_sources.get()
    start = len(sources) + 1 if sources is not None else 1

    excerpts = []
    for offset, row in enumerate(rows):
        n = start + offset
        if sources is not None:
            sources.append({"n": n, "url": row.url, "title": row.title})
        excerpts.append(f"[{n}] (source: {row.title} — {row.url})\n{row.text}")
    return "\n\n---\n\n".join(excerpts)


@beta_tool
def fetch_doc_page(url: str) -> str:
    """
    Fetch the full text of a single documentation page by its URL.

    Call this when the search excerpts are too short or lack the context you
    need — the full page gives you surrounding detail the chunks leave out.
    Use a URL that appeared as a source in a previous search result.

    Args:
        url (str): The exact page URL to fetch.

    Returns:
        str: The full stored text of the page, or a not-found message.
    """
    stmt = select(Document.text).where(Document.url == url)
    with Session(engine) as session:
        text = session.execute(stmt).scalar_one_or_none()

    if text is None:
        return f"No page found for URL: {url}"
    return text


@beta_tool
def flag_gap(topic: str) -> str:
    """
    Record that the documentation does not cover a topic.

    Call this when the docs genuinely lack information to answer the user's
    question, instead of guessing or answering from outside knowledge.

    Args:
        topic (str): A short description of the missing topic.

    Returns:
        str: A confirmation that the gap was logged.
    """
    logger.warning("documentation gap flagged: %s", topic)
    return f"Logged documentation gap: {topic}"


MODEL = "claude-opus-4-8"

# The tool runner needs the decorated functions themselves — it reads their
# generated schemas, and executes them for us as Claude requests each call.
TOOLS = [search_docs, fetch_doc_page, flag_gap]


def answer_with_agent(question: str) -> dict:
    """Answer a question by letting Claude drive the doc-search tools itself.

    Returns the same shape as rag.answer_question: {"answer", "sources"}, where
    sources is every excerpt search_docs surfaced this request, globally numbered
    to match the [n] citations in the answer.
    """
    # Fresh, empty list for this request. search_docs appends to this exact list
    # object (it reads the same ContextVar), so after the loop it holds every
    # source Claude was shown. Set here so each request starts clean.
    _request_sources.set([])

    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=1024,
        # Render order is tools -> system -> messages. The tool schemas + this
        # frozen prompt form a large, stable prefix, so caching finally pays off
        # here (unlike the tiny prompts in classify.py / rag.py). Keep this text
        # constant across requests — any edit invalidates the cached prefix.
        system=[
            {"type": "text", "text": SYSTEM_PROMPT,
             "cache_control": {"type": "ephemeral"}},
        ],
        tools=TOOLS,
        messages=[{"role": "user", "content": question}],
    )

    # The runner executes each requested tool and loops for us. Every iteration
    # yields one assistant message; the last one (stop_reason != tool_use) holds
    # the final text answer. Log token usage per turn as we go.
    final = None
    for message in runner:
        log_usage(logger, MODEL, message.usage)
        final = message

    answer = next(block.text for block in final.content if block.type == "text")
    return {"answer": answer, "sources": _request_sources.get()}


if __name__ == "__main__":
    import sys

    # Standalone smoke test: run the agent against one question and watch the
    # tool-call loop fire. main.py configures logging for the server; this block
    # does its own so the per-turn usage trace (usage.py) and any flag_gap
    # warnings print to the console while we watch. Pass a question on the
    # command line, or fall back to a default.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    question = " ".join(sys.argv[1:]) or "How do I declare a query parameter in FastAPI?"
    print(f"Q: {question}\n")
    result = answer_with_agent(question)
    print(result["answer"])
    print("\nSources:")
    for s in result["sources"]:
        print(f"  [{s['n']}] {s['title']} — {s['url']}")

