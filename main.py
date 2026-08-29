import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import answer_with_agent
from gate import answer_gated
from rag import answer_question
from search import search_chunks

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"]
)

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

@app.post("/ask-agent")
def ask_agent(request: AskRequest):
    logger.info("POST /ask-agent question=%r", request.question)
    result = answer_with_agent(question=request.question)
    return {"answer": result["answer"], "sources": result["sources"]}

@app.post("/ask-smart")
def ask_smart(request: AskRequest):
    logger.info("POST /ask-smart question=%r", request.question)
    result = answer_gated(question=request.question)
    return {"answer": result["answer"], "sources": result["sources"], "route": result["route"]}
