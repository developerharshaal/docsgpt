import logging


def log_usage(logger: logging.Logger, model: str, usage) -> None:
    """Log the token 'receipt' from a Claude response.

    input_tokens / output_tokens are what we sent / got back. The cache_* fields
    are None until prompt caching is enabled, so we coalesce them to 0 — once
    caching is on, cache_read climbing (and cache_write dropping to 0 on repeats)
    is how you prove it's working.
    """
    logger.info(
        "usage model=%s in=%d out=%d cache_read=%d cache_write=%d",
        model,
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_input_tokens or 0,
        usage.cache_creation_input_tokens or 0,
    )
