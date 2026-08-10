from sqlalchemy.orm import Session
from db import engine
from models import Document
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.dialects.postgresql import insert
import json

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

def fetch_document(url: str):
    return httpx.get(url).text

def parse_document(doc: str):
    parsed_doc = BeautifulSoup(markup=doc, features="html.parser")
    clean_text = parsed_doc.get_text(separator=" ", strip=True)
    return clean_text

if __name__=="__main__":
    with open("sources.json", "r") as f:
        sources = json.load(f)
    for source in sources:
        url = source["url"]
        title = source["title"]
        doc = fetch_document(url=url)
        parsed_doc = parse_document(doc=doc)
        save_document(url=url, title=title, text=parsed_doc)