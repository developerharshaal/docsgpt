from dotenv import load_dotenv
load_dotenv()

import logging
from enum import Enum
from pydantic import BaseModel
import anthropic

from usage import log_usage

client = anthropic.Anthropic()
logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """You classify a user's message to route it in a docs Q&A system.

- greeting: social/chit-chat with no question to answer (e.g. "hi", "thanks!").
- factual: a specific, narrow question answered by one part of the docs
  (e.g. "How do I set a default value for a query parameter?").
- broad: a wide or overview question needing synthesis across many sections
  (e.g. "How does dependency injection work in FastAPI?").

Choose exactly one."""

class MessageType(str, Enum):
    greeting = "greeting"
    factual = "factual"
    broad = "broad"

class ClassifyRequest(BaseModel):
    message_type : MessageType

def classify_intent(message: str) -> MessageType:
    # Same cacheable-prefix marker as rag.py. Haiku's cache minimum is ~2048
    # tokens and this prompt is ~130, so expect cache_read/cache_write to stay 0.
    response = client.messages.parse(
        model = MODEL,
        max_tokens = 64,
        system=[
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": message}],
        output_format=ClassifyRequest
    )
    result = response.parsed_output
    logger.info("classify message_type=%s", result.message_type.value)
    log_usage(logger, MODEL, response.usage)
    return result.message_type
