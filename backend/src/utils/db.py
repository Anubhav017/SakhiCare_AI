from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from src.utils.settings import settings

Base = declarative_base()

engine = create_engine(settings.DB_CONNECTION)

Session = sessionmaker(bind=engine)

def initialize_tables() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=connection)


def get_db():
    session = Session()
    try:
        yield session
    finally:
        session.close()