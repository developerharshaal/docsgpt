from sqlalchemy import create_engine

from models import Base

engine = create_engine("postgresql+psycopg://docsgpt:docsgpt@localhost:5432/docsgpt")

if __name__ == "__main__":
    Base.metadata.create_all(engine)