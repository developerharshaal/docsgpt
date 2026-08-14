import logging

from fastapi import FastAPI
from pydantic import BaseModel
from search import search_chunks
from rag import answer_question

# Configure logging for the whole app when the server imports this module.
# (injest.py configures its own logging for the ingestion CLI run.) filemode="a"
# so restarts/reloads append to the trace instead of wiping it.
logging.basicConfig(
    filename="logs.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status":"ok"}

@app.get("/")
def root_check():
    return {"message":"hello"}

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

@app.post("/search")
def search(request: SearchRequest):
    logger.info("POST /search top_k=%d query=%r", request.top_k, request.query)
    results = search_chunks(query=request.query, top_k=request.top_k)
    return {"results": [
        {
            "text": row.text,
            "distance": float(row.distance),
            "url": row.url,
            "title": row.title
        } for row in results
    ]}

class AskRequest(BaseModel):
    question: str

@app.post("/ask")
def ask(request: AskRequest):
    logger.info("POST /ask question=%r", request.question)
    result = answer_question(question=request.question)
    return {"answer": result["answer"], "sources": result["sources"]}