import logging

from sqlalchemy.orm import Session
from sqlalchemy import select
from db import engine
from models import Chunk, Document
from embeddings import get_embedding

logger = logging.getLogger(__name__)

def search_chunks(query: str, top_k: int = 5):
    query_vec = get_embedding(query)
    stmt = (
        select(
            Chunk.text,
            Chunk.embeddings.cosine_distance(query_vec).label("distance"),
            Document.url,
            Document.title,
        )
        .join(Document, Chunk.doc_id == Document.id)
        .order_by("distance")
        .limit(top_k)
    )
    with Session(engine) as session:
        results = session.execute(stmt).all()
    # best_distance is the top hit's cosine distance (lower = closer). A high
    # value here is the tell-tale of a corpus/retrieval gap even when hits>0.
    best_distance = f"{results[0].distance:.4f}" if results else "n/a"
    logger.info(
        "search hits=%d top_k=%d best_distance=%s query=%r",
        len(results), top_k, best_distance, query,
    )
    return results

