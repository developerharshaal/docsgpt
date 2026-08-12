from fastapi import FastAPI
from pydantic import BaseModel
from search import search_chunks
from rag import answer_question

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
    result = answer_question(question=request.question)
    return {"answer": result["answer"], "sources": result["sources"]}