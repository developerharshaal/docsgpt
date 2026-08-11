from sqlalchemy.orm import Session
from sqlalchemy import delete, select
from db import engine
from models import Document, Chunk
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert
import json
import logging
from embeddings import get_embedding

logger = logging.getLogger(__name__)


def save_document(url: str, title: str, text: str, engine=engine):
    with Session(engine) as session:
        stmt = insert(Document).values(
            url=url,
            title=title,
            size=len(text),
            text=text
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=['url'])
        session.execute(stmt)
        session.commit()
    logger.info("Saved document url=%s title=%s size=%d", url, title, len(text))

def fetch_document(url: str):
    logger.info("Fetching document url=%s", url)
    text = httpx.get(url).text
    logger.info("Fetched document url=%s bytes=%d", url, len(text))
    return text

def parse_document(doc: str):
    parsed_doc = BeautifulSoup(markup=doc, features="html.parser")
    clean_text = parsed_doc.get_text(separator=" ", strip=True)
    logger.info("Parsed document: %d chars of clean text", len(clean_text))
    return clean_text

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50):
    chunks = []
    start= 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append((start, chunk))
        start += chunk_size - overlap
    logger.info("Chunked text into %d chunks (size=%d overlap=%d)", len(chunks), chunk_size, overlap)
    return chunks

def save_chunks(doc_id: int, text: str, engine=engine):
    chunks = chunk_text(text=text)
    with Session(engine) as session:
        deleted = session.execute(delete(Chunk).where(Chunk.doc_id == doc_id)).rowcount
        logger.info("Deleted %d existing chunks for doc_id=%d", deleted, doc_id)
        for offset, chunk in chunks:
            embedding = get_embedding(chunk)
            session.add(Chunk(doc_id=doc_id,
                              text=chunk,
                              offset=offset,
                              embeddings=embedding))
        session.commit()
    logger.info("Saved %d chunks for doc_id=%d", len(chunks), doc_id)


if __name__=="__main__":
    logging.basicConfig(
        filename="logs.log",
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    with open("sources.json", "r") as f:
        sources = json.load(f)
    logger.info("Starting ingestion of %d sources", len(sources))

    for source in sources:
        url = source["url"]
        title = source["title"]
        try:
            doc = fetch_document(url=url)
            parsed_doc = parse_document(doc=doc)
            save_document(url=url, title=title, text=parsed_doc)
            with Session(engine) as session:
                doc_id = session.scalar(select(Document.id).where(Document.url == url))
            save_chunks(doc_id=doc_id, text=parsed_doc)
        except Exception:
            logger.exception("Failed to ingest url=%s", url)

    logger.info("Ingestion complete")
