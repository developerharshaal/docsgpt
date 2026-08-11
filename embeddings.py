import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from sentence_transformers import SentenceTransformer

model = SentenceTransformer('BAAI/bge-small-en-v1.5')
def get_embedding(text: str):
    embedding = model.encode(text)
    return embedding