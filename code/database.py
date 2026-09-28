import os
from contextvars import ContextVar
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL missing. Create code/.env with DATABASE_URL=...")

engine = create_engine(DATABASE_URL, pool_pre_ping=True) # using SQLAlchemy to create a database engine
db_session_basede26 = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# one counter per HTTP request, set by the middleware in main.py
sql_counter: ContextVar[list | None] = ContextVar("sql_counter", default=None)


@event.listens_for(engine, "before_cursor_execute")
def count_sql(conn, cursor, statement, parameters, context, executemany):
    counter = sql_counter.get()
    if counter is not None:
        counter[0] += 1


def get_db():
    db = db_session_basede26()
    try:
        yield db
    finally:
        db.close()
