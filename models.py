from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass

class Document(Base):
    __tablename__="documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    size: Mapped[int]
    text: Mapped[str]

class Chunk(Base):
    __tablename__="chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    text: Mapped[str]
    offset: Mapped[int]
    embeddings: Mapped[list[float]] = mapped_column(Vector(384))