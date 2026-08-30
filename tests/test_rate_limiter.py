import pytest
from fastapi import HTTPException

from rate_limit import check_rate_limit


def test_rate_limit_blocks_after_limit():
    key = "test-key-1"
    for _ in range(3):
        check_rate_limit(api=key, limit=3)

    with pytest.raises(HTTPException) as exec_info:
        check_rate_limit(api=key, limit=3)
    assert exec_info.value.status_code == 429

def test_rate_limit_allows_before_limit():
    key = "test-key-2"
    for _ in range(2):
        check_rate_limit(api=key, limit=3)