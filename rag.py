from dotenv import load_dotenv
load_dotenv()

import anthropic
from search import search_chunks

client = anthropic.Anthropic()

SYSTEM_PROPMT = """You are a helpful assistant that answers questions about FastAPI \
using ONLY the documentation excerpts provided in the user's message. \
If the excerpts do not contain enough information to answer, say \
"I couldn't find that in the documentation." Do not use outside knowledge.
After each claim, cite the excerpt number(s) in brackets, e.g. [1], [2]. Use only the number provided """

def answer_question(question: str, k: int = 5):
    chunks = search_chunks(query=question, top_k=k)

    numbered = []
    sources = []
    for n, row in enumerate(chunks, start=1):
        numbered.append(f"[{n}] {row.text}")
        sources.append({"n": n, "url": row.url, "title": row.title})

    context = "\n\n---\n\n".join(numbered)
    user_messsage = f"""Documentation excerpts:
    {context}
Question: {question}"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=SYSTEM_PROPMT,
        messages=[{"role": "user", "content": user_messsage}],
    )

    answer = next(block.text for block in response.content if block.type == "text")
    return {"answer": answer, "sources": sources}