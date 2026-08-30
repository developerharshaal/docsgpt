from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_ask_without_api_key_return_401():
    response = client.post("/ask", json={"question":"test"})
    assert response.status_code == 401

def test_ask_with_wrong_api_key_return_401():
    response = client.post("/ask",headers={"X-API-Key":"wrong"}, json={"question":"test"})
    assert response.status_code == 401