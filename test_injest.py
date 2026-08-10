from injest import parse_document, fetch_document, save_document
from unittest.mock import patch, MagicMock
from models import Base, Document
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import pytest

TEST_DB_URL = "postgresql+psycopg://docsgpt:docsgpt@localhost:5432/docsgpt_test"
test_engine = create_engine(TEST_DB_URL)

def test_parse_document():
    doc = "<h1>Hello</h1>  <p>World</p>"
    result = parse_document(doc=doc)
    assert result == "Hello World"

def test_fetch_document():
    fake_response = MagicMock()
    fake_response.text = "<html>fake page</html>"

    with patch("injest.httpx.get", return_value=fake_response) as mock_get:
        result = fetch_document(url="http://fakeurl.com")

    assert result == "<html>fake page</html>"

    mock_get.assert_called_once_with("http://fakeurl.com")

@pytest.fixture
def db_engine():
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)

def test_save_document(db_engine):
    save_document(url="http://testurl.com", title="Test Title", text="Test content", engine=db_engine)
    with Session(db_engine) as session:
        rows = session.scalars(select(Document)).all()

    assert len(rows) == 1
    assert rows[0].url == "http://testurl.com"
    assert rows[0].size == len("Test content")