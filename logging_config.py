import contextvars
import logging
import os

# Set by main.py's request middleware for the duration of one request; every
# logger.* call anywhere in the call stack (search.py, rag.py, agent.py, ...)
# picks it up through RequestIdFilter, so grepping logs.log for one request_id
# gives you every line that request produced, in order.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    """Configure the root logger once, at server startup.

    Level is read from LOG_LEVEL (default INFO) so it can be turned up for
    local debugging or down for production without a code change.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = logging.getLevelNamesMapping().get(level_name, logging.INFO)

    handler = logging.FileHandler("logs.log")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s"
    ))
    handler.addFilter(RequestIdFilter())

    logging.basicConfig(level=level, handlers=[handler])