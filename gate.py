import logging

from search import search_chunks
from classify import classify_intent, MessageType
from rag import CONFIG_BY_INTENT, _generate_answer
from agent import answer_with_agent

logger = logging.getLogger(__name__)

# Empirically set (see logs.log confidence-gating notes / PLAN.md), NOT a clean
# separator. Sampled best_distance on 5 covered + 5 off-corpus FastAPI questions
# plus one fully out-of-domain question:
#   covered: 0.1451-0.2166   missing: 0.1875-0.4755
# There is a genuine gray zone ~0.19-0.22 where a covered question (e.g. "how
# do I run my first FastAPI app?", 0.2166) scores WORSE than an actually-missing
# one (OAuth2, 0.1875) — bge-small's cosine distance separates topic vocabulary,
# not corpus coverage. 0.22 is chosen to draw the line above every covered
# sample in this set, biasing toward "never escalate a real hit" over "always
# catch a real gap" — escalation costs ~5x tokens (PLAN.md Phase 5 A/B), so a
# false escalation is expensive; a false negative just falls back to /ask's
# existing "couldn't find that in the documentation" fallback instead of the
# agent's flag_gap. Revisit once a Phase 6+ eval set attests it with more than a
# handful of hand-picked queries.
CONFIDENCE_THRESHOLD = 0.22


def answer_gated(question: str):
    """Route a question to the cheap one-shot path or escalate to the agent.

    Reuses intent classification + one retrieval pass (rag.py's CONFIG_BY_INTENT)
    to decide, then either finishes with rag._generate_answer or hands the
    question to agent.answer_with_agent, which re-retrieves and can additionally
    fetch a full page or flag a genuine gap. The re-retrieval on escalation is a
    deliberate simplification: embedding + a local pgvector query cost no API
    tokens, so discarding the first pass is cheap next to the complexity of
    threading pre-fetched chunks into the tool runner.
    """
    message_type = classify_intent(question)

    if message_type == MessageType.greeting:
        logger.info("gate route=greeting (short-circuit, no retrieval)")
        return {
            "answer": "Hello! How can I assist you with FastAPI documentation today?",
            "sources": [],
            "route": "greeting",
        }

    use_model, use_k = CONFIG_BY_INTENT[message_type]
    chunks = search_chunks(query=question, top_k=use_k)
    best_distance = chunks[0].distance if chunks else None

    if best_distance is None or best_distance > CONFIDENCE_THRESHOLD:
        logger.info(
            "gate route=agent intent=%s best_distance=%s threshold=%.4f",
            message_type.value,
            f"{best_distance:.4f}" if best_distance is not None else "n/a",
            CONFIDENCE_THRESHOLD,
        )
        result = answer_with_agent(question)
        result["route"] = "agent"
        return result

    logger.info(
        "gate route=rag intent=%s model=%s k=%d best_distance=%.4f",
        message_type.value, use_model, use_k, best_distance,
    )
    result = _generate_answer(question, chunks, use_model)
    result["route"] = "rag"
    return result
