import logging
import time
import uuid

from anthropic import APIError
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from agent import answer_with_agent
from auth import verify_api_key
from gate import answer_gated
from logging_config import configure_logging, request_id_var
from rag import answer_question
from rate_limit import check_rate_limit
from search import search_chunks

# Configure logging for the whole app when the server imports this module.
# (injest.py configures its own logging for the ingestion CLI run.)
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # A short id shared by every log line this request produces (see
    # logging_config.RequestIdFilter), so `grep <id> logs.log` reconstructs
    # the full trace of one call across search.py/rag.py/agent.py/etc.
    token = request_id_var.set(uuid.uuid4().hex[:8])
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request method=%s path=%s status=%d duration_ms=%.1f",
            request.method, request.url.path, response.status_code, duration_ms,
        )
        return response
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "request method=%s path=%s duration_ms=%.1f unhandled_error",
            request.method, request.url.path, duration_ms,
        )
        raise
    finally:
        request_id_var.reset(token)

@app.exception_handler(APIError)
async def anthropic_error_handler(request: Request, exc: APIError):
    logger.exception("Anthropic API call failed")
    return JSONResponse(status_code=502, content={"detail": "Upstream AI service unavailable"})

@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database operation failed")
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

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

@app.post("/ask", dependencies=[Depends(verify_api_key), Depends(check_rate_limit)])
def ask(request: AskRequest):
    logger.info("POST /ask question=%r", request.question)
    result = answer_question(question=request.question)
    return {"answer": result["answer"], "sources": result["sources"]}

@app.post("/ask-agent", dependencies=[Depends(verify_api_key), Depends(check_rate_limit)])
def ask_agent(request: AskRequest):
    logger.info("POST /ask-agent question=%r", request.question)
    result = answer_with_agent(question=request.question)
    return {"answer": result["answer"], "sources": result["sources"]}

@app.post("/ask-smart", dependencies=[Depends(verify_api_key), Depends(check_rate_limit)])
def ask_smart(request: AskRequest):
    logger.info("POST /ask-smart question=%r", request.question)
    result = answer_gated(question=request.question)
    return {"answer": result["answer"], "sources": result["sources"], "route": result["route"]}
