from sqlalchemy.orm import Session
from sqlalchemy import select
from db import engine
from models import Chunk, Document
from embeddings import get_embedding

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
    return results

