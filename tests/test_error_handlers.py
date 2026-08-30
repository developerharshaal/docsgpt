from unittest.mock import patch

import httpx
from anthropic import APIError
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from auth import API_KEY
from main import app

client = TestClient(app)
headers = {"X-API-Key": API_KEY}

def test_ask_returns_502_on_anthropic_error():
    fake_response = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    with patch("main.answer_question", side_effect=APIError("boom", request=fake_response, body=None)):
        response = client.post("/ask", headers=headers, json={"question": "test"})
    assert response.status_code == 502
    assert response.json() == {"detail": "Upstream AI service unavailable"}

def test_search_returns_503_on_sql_error():
    with patch("main.search_chunks", side_effect=SQLAlchemyError("boom")):
        response = client.post("/search", json={"query": "test"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}