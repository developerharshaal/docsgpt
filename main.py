from fastapi import FastAPI
from pydantic import BaseModel
from search import search_chunks

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
    return {"results": [{"text": text, "distance": float(distance)} for text, distance in results]}