import threading
from datetime import UTC, datetime

from dotenv import load_dotenv
from fastapi import Depends, HTTPException

from auth import api_key_scheme

load_dotenv()

RATE_LIMITTER = {}

_lock = threading.Lock()

def check_rate_limit(api: str = Depends(api_key_scheme), limit: int = 10):
    with _lock:
        now = datetime.now(UTC).timestamp()
        for key, value in RATE_LIMITTER.items():
            RATE_LIMITTER[key] = [t for t in value if now - t <= 60]

        if api not in RATE_LIMITTER:
            RATE_LIMITTER[api] = []

        if len(RATE_LIMITTER[api]) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        RATE_LIMITTER[api].append(now)