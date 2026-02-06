import os

from sqlalchemy import create_engine
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()


DATABASE_URL = os.environ["STOCK_ANALYSIS_DB"]


engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3500,
)


@contextmanager
def get_connection():
    """Get a connection from the pool for this task"""
    conn = engine.connect()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()  # Returns connection to pool, doesn't actually close it
