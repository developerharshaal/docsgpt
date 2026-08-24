from dotenv import load_dotenv
load_dotenv()

import logging

import anthropic
from search import search_chunks
from classify import classify_intent, MessageType
from usage import log_usage

client = anthropic.Anthropic()
logger = logging.getLogger(__name__)

SYSTEM_PROPMT = """You are a helpful assistant that answers questions about FastAPI \
using ONLY the documentation excerpts provided in the user's message. \
If the excerpts do not contain enough information to answer, say \
"I couldn't find that in the documentation." Do not use outside knowledge.
After each claim, cite the excerpt number(s) in brackets, e.g. [1], [2]. Use only the number provided """

CONFIG_BY_INTENT = {
    MessageType.factual: ("claude-sonnet-5", 5),
    MessageType.broad: ("claude-opus-4-8", 10)
}


def _generate_answer(question: str, chunks, model: str):
    """Grounded one-shot answer from already-retrieved chunks.

    Split out of answer_question so gate.py's confidence-gated path can reuse
    the exact same generation step after deciding retrieval was good enough —
    without duplicating the prompt/cache/usage-logging code.
    """
    numbered = []
    sources = []
    for n, row in enumerate(chunks, start=1):
        numbered.append(f"[{n}] {row.text}")
        sources.append({"n": n, "url": row.url, "title": row.title})

    context = "\n\n---\n\n".join(numbered)
    user_messsage = f"""Documentation excerpts:
    {context}
Question: {question}"""

    # cache_control marks this block as a cacheable prefix. NOTE: caching only
    # kicks in above a minimum prefix length (~1024 tokens; ~2048 for Haiku).
    # This system prompt is ~80 tokens, so today this is a deliberate no-op —
    # cache_read/cache_write stay 0. It starts paying off once the stable prefix
    # gets large (many-shot examples, or the tool schemas in the Phase 5 agent).
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {"type": "text", "text": SYSTEM_PROPMT, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user_messsage}],
    )
    log_usage(logger, model, response.usage)

    answer = next(block.text for block in response.content if block.type == "text")
    return {"answer": answer, "sources": sources}


def answer_question(question: str):

    message_type = classify_intent(question)

    if message_type == MessageType.greeting:
        logger.info("route intent=greeting (short-circuit, no retrieval)")
        return {"answer": "Hello! How can I assist you with FastAPI documentation today?", "sources": []}

    use_model, use_k = CONFIG_BY_INTENT[message_type]
    logger.info("route intent=%s model=%s k=%d", message_type.value, use_model, use_k)

    chunks = search_chunks(query=question, top_k=use_k)
    return _generate_answer(question, chunks, use_model)
